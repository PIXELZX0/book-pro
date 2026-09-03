import contextlib
import logging
import os
import re
import tempfile
import zlib
import zipfile
from collections.abc import Iterator
from pathlib import Path

from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, epub

from app.models import BookContent, Chapter

logger = logging.getLogger("uvicorn.error")

_WHITESPACE_RE = re.compile(r"\s+")
_SUSPECT_ENCODED_TOKEN_RE = re.compile(r"[A-Za-z0-9+/=]{72,}")
_ZIP_READ_CHUNK_SIZE = 8192


def _normalize_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _is_encoded_noise_token(token: str) -> bool:
    if not token:
        return False
    if not _SUSPECT_ENCODED_TOKEN_RE.fullmatch(token):
        return False
    has_upper = any(ch.isupper() for ch in token)
    has_lower = any(ch.islower() for ch in token)
    has_digit = any(ch.isdigit() for ch in token)
    return has_upper and has_lower and has_digit


def _strip_encoded_noise_tokens(text: str) -> str:
    if not text:
        return ""

    def _replace(match: re.Match[str]) -> str:
        token = match.group(0)
        return "" if _is_encoded_noise_token(token) else token

    return _SUSPECT_ENCODED_TOKEN_RE.sub(_replace, text)


def _sanitize_extracted_text(text: str) -> str:
    return _normalize_text(_strip_encoded_noise_tokens(text))


def _extract_title(soup: BeautifulSoup, fallback: str) -> str:
    for tag_name in ("h1", "h2", "h3", "title"):
        tag = soup.find(tag_name)
        if tag:
            title = _normalize_text(tag.get_text(" ", strip=True))
            if title:
                return title
    return fallback


def _extract_readable_text(soup: BeautifulSoup) -> str:
    block_selectors = "h1,h2,h3,h4,h5,h6,p,li,blockquote,pre"
    blocks = soup.select(block_selectors)
    lines: list[str] = []

    for block in blocks:
        text = _sanitize_extracted_text(block.get_text(" ", strip=True))
        if text:
            lines.append(text)

    if lines:
        return "\n\n".join(lines)

    return _sanitize_extracted_text(soup.get_text(" ", strip=True))


def _extract_book_title_from_metadata(book: epub.EpubBook) -> str:
    candidates: list[str] = []

    # Common metadata namespace variations used in EPUB files.
    for namespace, key in (
        ("DC", "title"),
        ("dc", "title"),
        ("DCTERMS", "title"),
        ("OPF", "title"),
        ("opf", "title"),
    ):
        try:
            entries = book.get_metadata(namespace, key)
        except Exception:  # noqa: BLE001
            continue

        for entry in entries or []:
            raw = entry[0] if isinstance(entry, tuple) and entry else entry
            if isinstance(raw, str):
                normalized = _normalize_text(raw)
                if normalized:
                    candidates.append(normalized)

    metadata = getattr(book, "metadata", None)
    if isinstance(metadata, dict):
        for namespace_payload in metadata.values():
            if not isinstance(namespace_payload, dict):
                continue
            for key, entries in namespace_payload.items():
                if str(key).lower() != "title":
                    continue
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    raw = entry[0] if isinstance(entry, tuple) and entry else entry
                    if isinstance(raw, str):
                        normalized = _normalize_text(raw)
                        if normalized:
                            candidates.append(normalized)

    raw_title = getattr(book, "title", None)
    if isinstance(raw_title, str):
        normalized = _normalize_text(raw_title)
        if normalized:
            candidates.append(normalized)

    return candidates[0] if candidates else "Unknown title"


def extract_epub_metadata_title(file_path: str | Path) -> str:
    book = read_epub_book(file_path)
    return _extract_book_title_from_metadata(book)


def _read_zip_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> tuple[bytes, bool]:
    """zip 엔트리를 읽는다. CRC 오류가 있으면 읽힌 부분까지만 반환한다."""
    try:
        return archive.read(info), False
    except (zipfile.BadZipFile, zlib.error, EOFError):
        pass

    data = bytearray()
    try:
        with archive.open(info) as handle:
            while True:
                chunk = handle.read(_ZIP_READ_CHUNK_SIZE)
                if not chunk:
                    break
                data.extend(chunk)
    except (zipfile.BadZipFile, EOFError, OSError, zlib.error):
        pass

    return bytes(data), True


def has_corrupt_entries(file_path: str | Path) -> bool:
    """CRC가 깨진 엔트리가 있는지 확인한다. zip 자체를 열 수 없으면 False를 반환한다."""
    try:
        with zipfile.ZipFile(str(file_path)) as archive:
            return archive.testzip() is not None
    except (zipfile.BadZipFile, OSError):
        return False


def repair_epub(source_path: str | Path, target_path: str | Path) -> Path:
    """CRC 오류가 있는 엔트리를 부분 복구해 새 EPUB(zip) 파일로 저장한다.

    손상된 엔트리는 읽을 수 있는 바이트까지만 저장하므로 커버 이미지처럼
    본문 추출에 필요 없는 항목이 깨져 있어도 나머지를 그대로 사용할 수 있다.
    """
    target = Path(target_path)
    repaired: list[str] = []

    with zipfile.ZipFile(str(source_path)) as source:
        entries = source.infolist()
        mimetype_first = [info for info in entries if info.filename == "mimetype"]
        others = [info for info in entries if info.filename != "mimetype"]

        with zipfile.ZipFile(target, "w", allowZip64=True) as output:
            for info in mimetype_first + others:
                data, damaged = _read_zip_entry(source, info)
                if damaged:
                    repaired.append(info.filename)

                new_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                new_info.compress_type = (
                    zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
                )
                new_info.external_attr = info.external_attr
                new_info.create_system = info.create_system
                output.writestr(new_info, data)

    if repaired:
        logger.warning(
            "[EPUB 엔트리 부분 복구] file='%s' entries=%d (%s)",
            Path(source_path).name,
            len(repaired),
            ", ".join(repaired[:5]),
        )
    return target


@contextlib.contextmanager
def repaired_temp_epub(file_path: str | Path) -> Iterator[str]:
    """손상된 EPUB을 임시 파일로 복구해 경로를 제공한다."""
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=".epub")
    handle.close()
    try:
        repair_epub(file_path, handle.name)
        yield handle.name
    finally:
        with contextlib.suppress(OSError):
            os.remove(handle.name)


def read_epub_book(file_path: str | Path) -> epub.EpubBook:
    """EPUB을 연다. 엔트리 CRC 오류가 있으면 임시 복구본으로 다시 시도한다."""
    try:
        return epub.read_epub(str(file_path))
    except zipfile.BadZipFile:
        logger.warning("[EPUB 복구 시도] file='%s'", Path(file_path).name)
        with repaired_temp_epub(file_path) as repaired_path:
            return epub.read_epub(repaired_path)


def parse_epub(
    file_path: str | Path,
    min_words: int = 80,
    preserve_paragraphs: bool = False,
) -> BookContent:
    book = read_epub_book(file_path)
    title = _extract_book_title_from_metadata(book)

    chapters: list[Chapter] = []
    chapter_index = 1

    for item in book.get_items_of_type(ITEM_DOCUMENT):
        name = item.get_name() or f"chapter-{chapter_index}"
        if "nav" in name.lower():
            continue

        soup = BeautifulSoup(item.get_content(), "html.parser")
        if preserve_paragraphs:
            text = _extract_readable_text(soup)
            word_count = len(_normalize_text(text).split())
        else:
            text = _sanitize_extracted_text(soup.get_text(" ", strip=True))
            word_count = len(text.split())
        if not text:
            continue

        if word_count < min_words:
            continue

        chapter_title = _extract_title(soup, fallback=name)
        chapters.append(Chapter(index=chapter_index, title=chapter_title, text=text))
        chapter_index += 1

    if not chapters:
        raise ValueError("EPUB에서 분석 가능한 챕터 텍스트를 찾지 못했습니다.")

    return BookContent(title=title, chapters=chapters)
