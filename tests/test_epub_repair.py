import io
import zipfile
from pathlib import Path

import pytest
from ebooklib import epub

from app.epub_parser import has_corrupt_entries, parse_epub, repair_epub
from app.service import normalize_error_message
from app.storage import save_uploaded_epub

BODY = " ".join(["주인공은 오래된 도서관에서 비밀 일기를 발견했다."] * 80)
COVER_BYTES = b"\xff\xd8\xff\xe0" + b"fake-jpeg-payload" * 64


def _build_epub(path: Path, title: str = "손상 테스트 소설") -> bytes:
    book = epub.EpubBook()
    book.set_identifier("id-corrupt-test")
    book.set_title(title)
    book.set_language("ko")
    book.set_cover("Images/cover.jpg", COVER_BYTES)

    spine: list = ["nav"]
    toc: list = []
    for index in (1, 2):
        chapter = epub.EpubHtml(title=f"제{index}장", file_name=f"chap_{index}.xhtml", lang="ko")
        chapter.content = f"<h1>제{index}장</h1><p>{BODY}</p><p>사건은 눈사태처럼 커졌다.</p>"
        book.add_item(chapter)
        spine.append(chapter)
        toc.append(epub.Link(f"chap_{index}.xhtml", f"제{index}장", f"제{index}장"))

    book.spine = spine
    book.toc = tuple(toc)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(str(path), book)
    return path.read_bytes()


def _corrupt_entry(raw: bytes, entry_name: str) -> bytes:
    """엔트리를 무압축(STORED)으로 다시 쓴 뒤 첫 바이트를 뒤집어 CRC 오류를 만든다."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(buffer, "w") as output:
        for info in source.infolist():
            compress_type = (
                zipfile.ZIP_STORED if info.filename == entry_name else info.compress_type
            )
            output.writestr(info, source.read(info), compress_type=compress_type)

    patched = bytearray(buffer.getvalue())
    with zipfile.ZipFile(io.BytesIO(bytes(patched))) as probe:
        info = probe.getinfo(entry_name)
        start = info.header_offset

    name_length = int.from_bytes(patched[start + 26 : start + 28], "little")
    extra_length = int.from_bytes(patched[start + 28 : start + 30], "little")
    data_start = start + 30 + name_length + extra_length
    patched[data_start] ^= 0xFF
    return bytes(patched)


@pytest.fixture
def healthy_epub(tmp_path: Path) -> Path:
    path = tmp_path / "healthy.epub"
    _build_epub(path)
    return path


@pytest.fixture
def corrupt_epub(tmp_path: Path, healthy_epub: Path) -> Path:
    path = tmp_path / "corrupt.epub"
    path.write_bytes(_corrupt_entry(healthy_epub.read_bytes(), "EPUB/Images/cover.jpg"))
    return path


def test_healthy_epub_has_no_corrupt_entries(healthy_epub: Path) -> None:
    assert has_corrupt_entries(healthy_epub) is False


def test_corrupt_epub_is_detected(corrupt_epub: Path) -> None:
    assert has_corrupt_entries(corrupt_epub) is True

    with zipfile.ZipFile(corrupt_epub) as archive:
        with pytest.raises(zipfile.BadZipFile, match="Bad CRC-32"):
            archive.read("EPUB/Images/cover.jpg")


def test_parse_epub_recovers_from_corrupt_entry(corrupt_epub: Path) -> None:
    book = parse_epub(corrupt_epub)

    assert book.title == "손상 테스트 소설"
    assert [chapter.title for chapter in book.chapters] == ["제1장", "제2장"]
    assert "눈사태" in book.chapters[0].text


def test_repair_epub_writes_readable_archive(corrupt_epub: Path, tmp_path: Path) -> None:
    target = tmp_path / "repaired.epub"

    repair_epub(corrupt_epub, target)

    assert has_corrupt_entries(target) is False
    assert [chapter.title for chapter in parse_epub(target).chapters] == ["제1장", "제2장"]


def test_save_uploaded_epub_stores_healthy_copy(
    corrupt_epub: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path / "books"))
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        saved = save_uploaded_epub(
            "손상 테스트 소설",
            source_file_path=corrupt_epub,
            original_filename="corrupt.epub",
            root_dir=str(tmp_path / "books"),
        )
    finally:
        get_settings.cache_clear()

    assert saved.exists()
    assert has_corrupt_entries(saved) is False


def test_corrupt_zip_error_message_is_user_friendly() -> None:
    message = normalize_error_message(
        zipfile.BadZipFile("Bad CRC-32 for file '4/OEBPS/Images/cover.jpg'")
    )
    assert "손상" in message
    assert "cover.jpg" not in message
