import re
import shutil
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.epub_parser import has_corrupt_entries, parse_epub, repair_epub
from app.schemas import (
    BookSummary,
    ChapterCharacterTrait,
    CharacterEvent,
    CharacterSummary,
    ChapterSummary,
)

_INVALID_CHARS_RE = re.compile(r'[\\/:*?"<>|]')
_WHITESPACE_RE = re.compile(r"\s+")
_CHAPTER_NAME_RE = re.compile(r"^c-(?P<index>\d+)-(?P<title>.+)\.md$")
_CHAPTER_DIGEST_INDEX_FILE = ".chapter-digests.json"
_READER_PROGRESS_FILE = ".reader-progress.json"


def _slug_part(value: str, fallback: str) -> str:
    cleaned = _INVALID_CHARS_RE.sub("-", value or "")
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    cleaned = cleaned.strip(".-_")
    return cleaned or fallback


def _book_dir_name(book_title: str) -> str:
    return f"book-{_slug_part(book_title, 'unknown-book')}"


def _chapter_file_name(chapter: ChapterSummary) -> str:
    chapter_no = max(chapter.chapter_index, 1)
    chapter_title = _slug_part(chapter.chapter_title, f"chapter-{chapter_no}")
    return f"c-{chapter_no}-{chapter_title}.md"


def _character_file_name(character: CharacterSummary) -> str:
    return f"{_slug_part(character.name, 'unknown-character')}.md"


def _epub_file_name(original_filename: str, fallback_base: str) -> str:
    raw_stem = Path(original_filename or "").stem
    safe_stem = _slug_part(raw_stem, fallback_base)
    return f"{safe_stem}.epub"


def _render_character_events(rows: list[CharacterEvent]) -> str:
    if not rows:
        return "- 없음"

    lines: list[str] = []
    for row in rows:
        lines.append(f"- **인물**: {row.character}")
        lines.append(f"  - 사건: {row.event}")
        lines.append(f"  - 영향: {row.impact}")
    return "\n".join(lines)


def _render_chapter_markdown(chapter: ChapterSummary) -> str:
    events = "\n".join(f"- {event}" for event in chapter.key_events) if chapter.key_events else "- 없음"
    character_events = _render_character_events(chapter.character_events)
    character_traits = _render_character_traits(chapter.character_traits)

    return (
        f"# Chapter {chapter.chapter_index}: {chapter.chapter_title}\n\n"
        f"## 요약\n{chapter.summary}\n\n"
        f"## 핵심 사건\n{events}\n\n"
        f"## 캐릭터별 사건/영향\n{character_events}\n\n"
        f"## 캐릭터 특징 관찰(정밀 분석)\n{character_traits}\n"
    )


def _render_character_traits(rows: list[ChapterCharacterTrait]) -> str:
    if not rows:
        return "- 없음"

    lines: list[str] = []
    for row in rows:
        traits = ", ".join(row.traits) if row.traits else "없음"
        speech = ", ".join(row.speech_inferences) if row.speech_inferences else "없음"
        lines.append(f"- **인물**: {row.character}")
        lines.append(f"  - 특징: {traits}")
        lines.append(f"  - 대사 기반 추론: {speech}")
    return "\n".join(lines)


def _render_character_markdown(character: CharacterSummary) -> str:
    traits = "\n".join(f"- {trait}" for trait in character.traits) if character.traits else "- 없음"

    return (
        f"# {character.name}\n\n"
        f"- 나이: {character.age}\n"
        f"- 신상: {character.sinsang}\n"
        f"- 성장 배경: {character.growth_background}\n"
        f"- 목소리: {character.voice}\n"
        f"- 느낌: {character.feeling}\n\n"
        f"## 특징\n{traits}\n"
    )


def _render_setting_markdown(summary: BookSummary) -> str:
    world = summary.world_summary
    style = summary.writing_style
    settings = "\n".join(f"- {item}" for item in world.settings) if world.settings else "- 없음"
    rules = "\n".join(f"- {item}" for item in world.rules) if world.rules else "- 없음"
    themes = "\n".join(f"- {item}" for item in world.themes) if world.themes else "- 없음"
    style_devices = (
        "\n".join(f"- {item}" for item in style.imagery_and_devices)
        if style.imagery_and_devices
        else "- 없음"
    )
    continuation = (
        "\n".join(f"- {item}" for item in style.continuation_guidelines)
        if style.continuation_guidelines
        else "- 없음"
    )

    return (
        f"# {summary.book_title} 세계관 설정\n\n"
        f"## 세계관 요약\n{world.summary}\n\n"
        f"## 설정\n{settings}\n\n"
        f"## 규칙\n{rules}\n\n"
        f"## 테마\n{themes}\n\n"
        f"## 작가 필체 분석\n"
        f"- 핵심 요약: {style.summary}\n"
        f"- 톤: {style.tone}\n"
        f"- 문장 스타일: {style.sentence_style}\n"
        f"- 어휘 선택: {style.diction}\n"
        f"- 시점/서술 거리: {style.perspective}\n"
        f"- 전개 속도: {style.pacing}\n"
        f"- 대사 스타일: {style.dialogue_style}\n\n"
        f"## 이미지/수사 패턴\n{style_devices}\n\n"
        f"## 이어쓰기 가이드\n{continuation}\n"
    )


def _to_iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _normalize_reader_progress_record(payload: object) -> dict:
    if not isinstance(payload, dict):
        return {
            "page": 0,
            "total_pages": 1,
            "ratio": 0.0,
            "updated_at": "",
        }

    total_pages_raw = payload.get("total_pages", payload.get("totalPages", 1))
    page_raw = payload.get("page", 0)
    ratio_raw = payload.get("ratio")
    updated_at_raw = payload.get("updated_at", payload.get("updatedAt", ""))

    total_pages = int(total_pages_raw) if isinstance(total_pages_raw, (int, float)) else 1
    total_pages = max(total_pages, 1)

    page = int(page_raw) if isinstance(page_raw, (int, float)) else 0
    page = max(0, min(page, total_pages - 1))

    if isinstance(ratio_raw, (int, float)):
        ratio = max(0.0, min(float(ratio_raw), 1.0))
    else:
        ratio = 0.0 if total_pages <= 1 else page / max(total_pages - 1, 1)

    updated_at = str(updated_at_raw).strip() if isinstance(updated_at_raw, str) else ""

    return {
        "page": page,
        "total_pages": total_pages,
        "ratio": ratio,
        "updated_at": updated_at,
    }


def compute_chapter_digest(*, chapter_title: str, chapter_text: str) -> str:
    normalized_title = _WHITESPACE_RE.sub(" ", chapter_title or "").strip()
    normalized_text = _WHITESPACE_RE.sub(" ", chapter_text or "").strip()
    payload = f"{normalized_title}\n{normalized_text}".encode("utf-8", errors="ignore")
    return hashlib.sha256(payload).hexdigest()


def _book_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        [p for p in root.iterdir() if p.is_dir() and p.name.startswith("book-")],
        key=lambda p: p.name,
    )


def _latest_markdown_timestamp(book_dir: Path) -> float:
    md_files = list(book_dir.rglob("*.md"))
    if not md_files:
        return book_dir.stat().st_mtime
    return max(p.stat().st_mtime for p in md_files)


def _latest_epub_path(book_dir: Path) -> Path | None:
    epub_files = sorted(
        [p for p in book_dir.glob("*.epub") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not epub_files:
        return None
    return epub_files[0]


def _book_title_from_setting(book_dir: Path, fallback_slug: str) -> str:
    setting_path = book_dir / "setting.md"
    if setting_path.exists():
        first_line = setting_path.read_text(encoding="utf-8", errors="ignore").splitlines()[:1]
        if first_line:
            line = first_line[0].strip()
            if line.startswith("# "):
                heading = line[2:].strip()
                suffix = " 세계관 설정"
                if heading.endswith(suffix):
                    return heading[: -len(suffix)].strip() or fallback_slug
                return heading or fallback_slug
    return fallback_slug


def _display_title(book_dir: Path, fallback_slug: str) -> str:
    if is_studio_book(book_dir):
        try:
            project = json.loads((book_dir / _STUDIO_PROJECT_FILE).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            project = {}
        return project.get("book_title") or fallback_slug
    return _book_title_from_setting(book_dir, fallback_slug)


def list_books(root_dir: str | Path, *, page: int = 1, page_size: int = 10) -> dict:
    root = Path(root_dir)
    books = []
    for book_dir in _book_dirs(root):
        slug = book_dir.name
        display_title = slug[len("book-") :] if slug.startswith("book-") else slug
        chapter_count = len(list((book_dir / "chapter").glob("*.md")))
        character_count = len(list((book_dir / "character").glob("*.md")))
        is_completed = (book_dir / "setting.md").exists()
        if is_completed:
            status = "completed"
        elif chapter_count > 0 or character_count > 0:
            status = "processing"
        else:
            status = "queued"
        latest_ts = _latest_markdown_timestamp(book_dir)
        books.append(
            {
                "slug": slug,
                "book_title": _display_title(book_dir, display_title),
                "chapter_count": chapter_count,
                "character_count": character_count,
                "status": status,
                "updated_at": _to_iso_utc(latest_ts),
                "is_studio": is_studio_book(book_dir),
                "series_slug": _studio_series_slug(book_dir),
                "_latest_ts": latest_ts,
            }
        )

    books.sort(key=lambda row: row["_latest_ts"], reverse=True)
    total = len(books)

    page = max(page, 1)
    page_size = max(min(page_size, 50), 1)
    start = (page - 1) * page_size
    end = start + page_size

    page_items = []
    for row in books[start:end]:
        row.pop("_latest_ts", None)
        page_items.append(row)

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": page_items,
    }


def _safe_book_path(root: Path, slug: str) -> Path:
    if not slug or "/" in slug or "\\" in slug or ".." in slug:
        raise ValueError("유효하지 않은 책 식별자입니다.")
    book_dir = root / slug
    if not book_dir.exists() or not book_dir.is_dir():
        raise FileNotFoundError(f"책 폴더를 찾을 수 없습니다: {slug}")
    return book_dir


def _chapter_sort_key(path: Path) -> tuple[int, str]:
    match = _CHAPTER_NAME_RE.match(path.name)
    if not match:
        return (10**9, path.name)
    return (int(match.group("index")), path.name)


def read_book_detail(root_dir: str | Path, *, slug: str) -> dict:
    root = Path(root_dir)
    book_dir = _safe_book_path(root, slug)

    chapter_dir = book_dir / "chapter"
    character_dir = book_dir / "character"
    setting_path = book_dir / "setting.md"

    chapters = []
    for chapter_path in sorted(chapter_dir.glob("*.md"), key=_chapter_sort_key):
        match = _CHAPTER_NAME_RE.match(chapter_path.name)
        index = int(match.group("index")) if match else 0
        title = match.group("title") if match else chapter_path.stem
        chapters.append(
            {
                "index": index,
                "title": title,
                "file_name": chapter_path.name,
                "markdown": chapter_path.read_text(encoding="utf-8", errors="ignore"),
            }
        )

    characters = []
    for char_path in sorted(character_dir.glob("*.md"), key=lambda p: p.name):
        characters.append(
            {
                "name": char_path.stem,
                "file_name": char_path.name,
                "markdown": char_path.read_text(encoding="utf-8", errors="ignore"),
            }
        )

    setting_markdown = ""
    if setting_path.exists():
        setting_markdown = setting_path.read_text(encoding="utf-8", errors="ignore")

    latest_ts = _latest_markdown_timestamp(book_dir)
    display_title = slug[len("book-") :] if slug.startswith("book-") else slug

    return {
        "slug": slug,
        "book_title": _display_title(book_dir, display_title),
        "updated_at": _to_iso_utc(latest_ts),
        "chapter_count": len(chapters),
        "character_count": len(characters),
        "chapters": chapters,
        "characters": characters,
        "setting_markdown": setting_markdown,
        "is_studio": is_studio_book(book_dir),
    }


def read_book_reader(root_dir: str | Path, *, slug: str) -> dict:
    root = Path(root_dir)
    book_dir = _safe_book_path(root, slug)
    epub_path = _latest_epub_path(book_dir)
    if not epub_path:
        raise FileNotFoundError(f"원문 EPUB 파일을 찾을 수 없습니다: {slug}")

    book = parse_epub(epub_path, min_words=1, preserve_paragraphs=True)
    return {
        "slug": slug,
        "book_title": book.title,
        "chapter_count": len(book.chapters),
        "chapters": [
            {
                "index": chapter.index,
                "title": chapter.title,
                "text": chapter.text,
            }
            for chapter in book.chapters
        ],
    }


def read_book_reader_progress(root_dir: str | Path, *, slug: str) -> dict:
    root = Path(root_dir)
    book_dir = _safe_book_path(root, slug)
    progress_path = book_dir / _READER_PROGRESS_FILE
    if not progress_path.exists():
        record = _normalize_reader_progress_record({})
        return {"slug": slug, **record}

    try:
        payload = json.loads(progress_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        payload = {}

    record = _normalize_reader_progress_record(payload)
    return {"slug": slug, **record}


def save_book_reader_progress(
    root_dir: str | Path,
    *,
    slug: str,
    page: int,
    total_pages: int,
    ratio: float | None = None,
) -> dict:
    root = Path(root_dir)
    book_dir = _safe_book_path(root, slug)

    safe_total_pages = int(total_pages) if isinstance(total_pages, (int, float)) else 1
    safe_total_pages = max(safe_total_pages, 1)

    safe_page = int(page) if isinstance(page, (int, float)) else 0
    safe_page = max(0, min(safe_page, safe_total_pages - 1))

    if isinstance(ratio, (int, float)):
        safe_ratio = max(0.0, min(float(ratio), 1.0))
    else:
        safe_ratio = 0.0 if safe_total_pages <= 1 else safe_page / max(safe_total_pages - 1, 1)

    record = {
        "page": safe_page,
        "total_pages": safe_total_pages,
        "ratio": safe_ratio,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    progress_path = book_dir / _READER_PROGRESS_FILE
    progress_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {"slug": slug, **record}


def get_latest_epub_path(root_dir: str | Path, *, slug: str) -> Path:
    root = Path(root_dir)
    book_dir = _safe_book_path(root, slug)
    epub_path = _latest_epub_path(book_dir)
    if not epub_path:
        raise FileNotFoundError(f"원문 EPUB 파일을 찾을 수 없습니다: {slug}")
    return epub_path


def save_book_summary(summary: BookSummary, *, root_dir: str | Path = "books") -> Path:
    root = Path(root_dir)
    book_dir = root / _book_dir_name(summary.book_title)
    chapter_dir = book_dir / "chapter"
    character_dir = book_dir / "character"

    chapter_dir.mkdir(parents=True, exist_ok=True)
    character_dir.mkdir(parents=True, exist_ok=True)

    for chapter in summary.chapter_summaries:
        save_chapter_summary(summary.book_title, chapter, root_dir=root)

    for character in summary.character_summaries:
        path = character_dir / _character_file_name(character)
        path.write_text(_render_character_markdown(character), encoding="utf-8")

    setting_path = book_dir / "setting.md"
    setting_path.write_text(_render_setting_markdown(summary), encoding="utf-8")

    return book_dir


def save_chapter_summary(
    book_title: str,
    chapter: ChapterSummary,
    *,
    root_dir: str | Path = "books",
) -> Path:
    root = Path(root_dir)
    book_dir = root / _book_dir_name(book_title)
    chapter_dir = book_dir / "chapter"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    chapter_path = chapter_dir / _chapter_file_name(chapter)
    chapter_path.write_text(_render_chapter_markdown(chapter), encoding="utf-8")
    return chapter_path


def ensure_book_directories(book_title: str, *, root_dir: str | Path = "books") -> Path:
    root = Path(root_dir)
    book_dir = root / _book_dir_name(book_title)
    (book_dir / "chapter").mkdir(parents=True, exist_ok=True)
    (book_dir / "character").mkdir(parents=True, exist_ok=True)
    return book_dir


_STUDIO_PROJECT_FILE = "studio.json"
_STUDIO_CONVERSATION_FILE = "studio/conversation.json"


def is_studio_book(book_dir: Path) -> bool:
    return (book_dir / _STUDIO_PROJECT_FILE).exists()


def _studio_series_slug(book_dir: Path) -> str | None:
    project_path = book_dir / _STUDIO_PROJECT_FILE
    if not project_path.exists():
        return None
    try:
        data = json.loads(project_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data.get("series_slug")


def save_studio_project(
    book_title: str,
    *,
    premise: str,
    genre: str,
    language: str,
    root_dir: str | Path = "books",
    book_format: str = "short",
    series_slug: str | None = None,
    volume_index: int | None = None,
) -> Path:
    root = Path(root_dir)
    book_dir = root / _book_dir_name(book_title)
    if book_dir.exists():
        raise ValueError(f"이미 존재하는 책과 이름이 겹칩니다: {book_title}")

    ensure_book_directories(book_title, root_dir=root_dir)
    payload: dict[str, Any] = {
        "book_title": book_title,
        "premise": premise,
        "genre": genre,
        "language": language,
        "format": book_format,
        "created_at": _to_iso_utc(datetime.now(timezone.utc).timestamp()),
    }
    if series_slug is not None:
        payload["series_slug"] = series_slug
        payload["volume_index"] = volume_index

    project_path = book_dir / _STUDIO_PROJECT_FILE
    project_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return project_path


def read_studio_project(root_dir: str | Path, *, slug: str) -> dict:
    root = Path(root_dir)
    book_dir = _safe_book_path(root, slug)
    project_path = book_dir / _STUDIO_PROJECT_FILE
    if not project_path.exists():
        raise FileNotFoundError(f"스튜디오 프로젝트를 찾을 수 없습니다: {slug}")
    return json.loads(project_path.read_text(encoding="utf-8"))


def read_studio_conversation(root_dir: str | Path, *, slug: str) -> list[dict]:
    root = Path(root_dir)
    book_dir = _safe_book_path(root, slug)
    conversation_path = book_dir / _STUDIO_CONVERSATION_FILE
    if not conversation_path.exists():
        return []
    try:
        payload = json.loads(conversation_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return payload.get("messages", [])


def save_studio_conversation(root_dir: str | Path, *, slug: str, messages: list[dict]) -> Path:
    root = Path(root_dir)
    book_dir = _safe_book_path(root, slug)
    conversation_path = book_dir / _STUDIO_CONVERSATION_FILE
    conversation_path.parent.mkdir(parents=True, exist_ok=True)
    conversation_path.write_text(
        json.dumps({"messages": messages}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return conversation_path


def list_studio_projects(root_dir: str | Path) -> list[dict]:
    root = Path(root_dir)
    projects = []
    for book_dir in _book_dirs(root):
        studio_path = book_dir / _STUDIO_PROJECT_FILE
        if not studio_path.exists():
            continue
        try:
            data = json.loads(studio_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        chapter_count = len(list((book_dir / "chapter").glob("*.md")))
        projects.append({"slug": book_dir.name, "chapter_count": chapter_count, **data})
    projects.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return projects


def update_studio_project(
    root_dir: str | Path,
    *,
    slug: str,
    premise: str | None = None,
    genre: str | None = None,
    language: str | None = None,
) -> dict:
    root = Path(root_dir)
    project_path = _safe_book_path(root, slug) / _STUDIO_PROJECT_FILE
    if not project_path.exists():
        raise FileNotFoundError(f"스튜디오 프로젝트를 찾을 수 없습니다: {slug}")
    data = json.loads(project_path.read_text(encoding="utf-8"))
    if premise is not None:
        data["premise"] = premise.strip()
    if genre is not None:
        data["genre"] = genre.strip()
    if language is not None:
        data["language"] = language.strip() or "ko"
    project_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return data


def update_series_meta(
    root_dir: str | Path,
    *,
    slug: str,
    premise: str | None = None,
    genre: str | None = None,
    language: str | None = None,
) -> dict:
    root = Path(root_dir)
    series_path = _safe_book_path(root, slug) / "series.json"
    if not series_path.exists():
        raise FileNotFoundError(f"시리즈를 찾을 수 없습니다: {slug}")
    data = json.loads(series_path.read_text(encoding="utf-8"))
    if premise is not None:
        data["premise"] = premise.strip()
    if genre is not None:
        data["genre"] = genre.strip()
    if language is not None:
        data["language"] = language.strip() or "ko"
    series_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return data


def move_container_to_trash(root_dir: str | Path, *, slug: str) -> Path:
    root = Path(root_dir)
    container_dir = _safe_book_path(root, slug)
    trash_root = root / ".trash"
    trash_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = trash_root / f"{slug}-{stamp}"
    while target.exists():
        target = trash_root / f"{slug}-{stamp}-{uuid4().hex[:8]}"
    shutil.move(str(container_dir), str(target))
    return target


def detach_series_volumes(root_dir: str | Path, *, series_slug: str) -> list[str]:
    root = Path(root_dir)
    detached = []
    for book_dir in _book_dirs(root):
        studio_path = book_dir / _STUDIO_PROJECT_FILE
        if not studio_path.exists():
            continue
        try:
            data = json.loads(studio_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("series_slug") != series_slug:
            continue
        data.pop("series_slug", None)
        data.pop("volume_index", None)
        studio_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        detached.append(book_dir.name)
    return detached


def remove_chapter_files(
    book_title: str,
    chapter_index: int,
    *,
    root_dir: str | Path = "books",
) -> list[str]:
    chapter_dir = Path(root_dir) / _book_dir_name(book_title) / "chapter"
    if not chapter_dir.exists():
        return []
    prefix = f"c-{max(int(chapter_index), 1)}-"
    removed = []
    for path in sorted(chapter_dir.glob(f"{prefix}*.md")):
        path.unlink(missing_ok=True)
        removed.append(path.name)
    return removed


def delete_chapter_files_by_index(
    root_dir: str | Path,
    *,
    slug: str,
    chapter_index: int,
) -> list[str]:
    root = Path(root_dir)
    chapter_dir = _safe_book_path(root, slug) / "chapter"
    prefix = f"c-{max(int(chapter_index), 1)}-"
    removed = []
    for path in sorted(chapter_dir.glob(f"{prefix}*.md")):
        path.unlink(missing_ok=True)
        removed.append(path.name)
    if not removed:
        raise FileNotFoundError(f"챕터를 찾을 수 없습니다: {chapter_index}장")
    return removed


def _series_dir_name(series_title: str) -> str:
    return f"series-{_slug_part(series_title, 'unknown-series')}"


def save_series(
    series_title: str,
    *,
    premise: str,
    genre: str,
    language: str,
    root_dir: str | Path = "books",
) -> Path:
    root = Path(root_dir)
    series_dir = root / _series_dir_name(series_title)
    if series_dir.exists():
        raise ValueError(f"이미 존재하는 시리즈와 이름이 겹칩니다: {series_title}")

    series_dir.mkdir(parents=True, exist_ok=True)
    (series_dir / "character").mkdir(parents=True, exist_ok=True)
    series_path = series_dir / "series.json"
    series_path.write_text(
        json.dumps(
            {
                "series_title": series_title,
                "premise": premise,
                "genre": genre,
                "language": language,
                "created_at": _to_iso_utc(datetime.now(timezone.utc).timestamp()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return series_path


def read_series(root_dir: str | Path, *, slug: str) -> dict:
    root = Path(root_dir)
    series_dir = _safe_book_path(root, slug)
    series_path = series_dir / "series.json"
    if not series_path.exists():
        raise FileNotFoundError(f"시리즈를 찾을 수 없습니다: {slug}")
    return json.loads(series_path.read_text(encoding="utf-8"))


def list_series(root_dir: str | Path) -> list[dict]:
    root = Path(root_dir)
    if not root.exists():
        return []
    series_list = []
    for series_dir in sorted(root.iterdir(), key=lambda p: p.name):
        if not series_dir.is_dir() or not series_dir.name.startswith("series-"):
            continue
        series_path = series_dir / "series.json"
        if not series_path.exists():
            continue
        try:
            data = json.loads(series_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        slug = series_dir.name
        series_list.append(
            {
                "slug": slug,
                "series_title": data.get("series_title", slug),
                "premise": data.get("premise", ""),
                "genre": data.get("genre", ""),
                "language": data.get("language", "ko"),
                "created_at": data.get("created_at", ""),
                "volumes": list_series_volumes(root_dir, series_slug=slug),
            }
        )
    return series_list


def list_series_volumes(root_dir: str | Path, *, series_slug: str) -> list[dict]:
    root = Path(root_dir)
    volumes = []
    for book_dir in _book_dirs(root):
        studio_path = book_dir / _STUDIO_PROJECT_FILE
        if not studio_path.exists():
            continue
        try:
            data = json.loads(studio_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("series_slug") != series_slug:
            continue
        volumes.append(
            {
                "slug": book_dir.name,
                "volume_index": data.get("volume_index") or 0,
                "book_title": data.get("book_title", book_dir.name),
                "chapter_count": len(list((book_dir / "chapter").glob("*.md"))),
            }
        )
    volumes.sort(key=lambda volume: volume["volume_index"])
    return volumes


_BIBLE_CONVERSATION_FILE = "studio/bible-conversation.json"
_BIBLE_FILE = "studio/bible.json"


def read_bible_conversation(root_dir: str | Path, *, slug: str) -> list[dict]:
    root = Path(root_dir)
    container_dir = _safe_book_path(root, slug)
    path = container_dir / _BIBLE_CONVERSATION_FILE
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return payload.get("messages", [])


def save_bible_conversation(root_dir: str | Path, *, slug: str, messages: list[dict]) -> Path:
    root = Path(root_dir)
    container_dir = _safe_book_path(root, slug)
    path = container_dir / _BIBLE_CONVERSATION_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"messages": messages}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _read_bible_payload(container_dir: Path) -> dict[str, Any] | None:
    path = container_dir / _BIBLE_FILE
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def read_bible(root_dir: str | Path, *, slug: str) -> dict:
    root = Path(root_dir)
    container_dir = _safe_book_path(root, slug)

    payload = _read_bible_payload(container_dir)
    if payload is not None:
        characters = [
            {
                "name": str(character.get("name", "")),
                "markdown": str(character.get("markdown", "")),
            }
            for character in payload.get("characters", [])
            if isinstance(character, dict)
        ]
        return {
            "setting_markdown": str(payload.get("setting_markdown", "")),
            "characters": characters,
        }

    setting_path = container_dir / "setting.md"
    setting_markdown = (
        setting_path.read_text(encoding="utf-8", errors="ignore") if setting_path.exists() else ""
    )
    character_dir = container_dir / "character"
    characters = []
    if character_dir.exists():
        for char_path in sorted(character_dir.glob("*.md"), key=lambda p: p.name):
            characters.append(
                {
                    "name": char_path.stem,
                    "markdown": char_path.read_text(encoding="utf-8", errors="ignore"),
                }
            )
    return {"setting_markdown": setting_markdown, "characters": characters}


def save_bible(
    root_dir: str | Path,
    *,
    slug: str,
    setting_markdown: str,
    characters: list[dict],
) -> None:
    root = Path(root_dir)
    container_dir = _safe_book_path(root, slug)

    previous = _read_bible_payload(container_dir)
    synced_before = {
        name
        for name in (previous or {}).get("synced_character_files", [])
        if isinstance(name, str)
    }

    (container_dir / "setting.md").write_text(setting_markdown, encoding="utf-8")

    character_dir = container_dir / "character"
    character_dir.mkdir(parents=True, exist_ok=True)

    synced: dict[str, dict] = {}
    for character in characters:
        name = (character.get("name") or "").strip() or "이름없음"
        file_name = f"{_slug_part(name, 'character')}.md"
        synced[file_name] = {"name": name, "markdown": character.get("markdown", "")}

    for file_name, character in synced.items():
        (character_dir / file_name).write_text(character["markdown"], encoding="utf-8")
    for stale_name in synced_before - set(synced):
        (character_dir / stale_name).unlink(missing_ok=True)

    bible_path = container_dir / _BIBLE_FILE
    bible_path.parent.mkdir(parents=True, exist_ok=True)
    bible_path.write_text(
        json.dumps(
            {
                "setting_markdown": setting_markdown,
                "characters": list(synced.values()),
                "synced_character_files": list(synced),
                "updated_at": _to_iso_utc(datetime.now(timezone.utc).timestamp()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def clear_book_summary_outputs(book_title: str, *, root_dir: str | Path = "books") -> Path:
    book_dir = ensure_book_directories(book_title, root_dir=root_dir)
    chapter_dir = book_dir / "chapter"
    character_dir = book_dir / "character"
    setting_path = book_dir / "setting.md"

    for path in chapter_dir.glob("*.md"):
        path.unlink(missing_ok=True)
    for path in character_dir.glob("*.md"):
        path.unlink(missing_ok=True)
    setting_path.unlink(missing_ok=True)
    (book_dir / _CHAPTER_DIGEST_INDEX_FILE).unlink(missing_ok=True)
    return book_dir


def save_uploaded_epub(
    book_title: str,
    *,
    source_file_path: str | Path,
    original_filename: str,
    root_dir: str | Path = "books",
) -> Path:
    book_dir = ensure_book_directories(book_title, root_dir=root_dir)
    target_name = _epub_file_name(original_filename, fallback_base=book_title or "book")
    target_path = book_dir / target_name

    if has_corrupt_entries(source_file_path):
        repair_epub(source_file_path, target_path)
    else:
        shutil.copyfile(str(source_file_path), str(target_path))
    return target_path


def read_book_summary_snapshot(root_dir: str | Path, *, slug: str) -> dict:
    detail = read_book_detail(root_dir, slug=slug)
    chapter_summaries: list[ChapterSummary] = []

    for chapter in detail["chapters"]:
        summary = extract_section(chapter["markdown"], "요약")
        key_events = [
            row.strip()[2:].strip()
            for row in extract_section(chapter["markdown"], "핵심 사건").splitlines()
            if row.strip().startswith("- ")
        ]
        chapter_summaries.append(
            ChapterSummary(
                chapter_index=chapter["index"],
                chapter_title=chapter["title"],
                summary=summary or "",
                key_events=key_events,
                character_events=[],
                character_traits=[],
            )
        )

    return {
        "book_title": detail["book_title"],
        "chapter_summaries": chapter_summaries,
        "character_summaries_text": "\n\n".join(item["markdown"] for item in detail["characters"]),
        "setting_markdown": detail.get("setting_markdown", ""),
    }


def extract_section(markdown: str, section_title: str) -> str:
    pattern = rf"##\s+{re.escape(section_title)}\n([\s\S]*?)(\n##\s+|$)"
    match = re.search(pattern, markdown or "", flags=re.MULTILINE)
    if not match:
        return ""
    return match.group(1).strip()


def load_chapter_digest_index(
    book_title: str,
    *,
    root_dir: str | Path = "books",
) -> dict[int, str]:
    root = Path(root_dir)
    book_dir = root / _book_dir_name(book_title)
    index_path = book_dir / _CHAPTER_DIGEST_INDEX_FILE
    if not index_path.exists():
        return {}

    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    if not isinstance(payload, dict):
        return {}

    digest_map: dict[int, str] = {}
    for key, value in payload.items():
        try:
            chapter_index = int(str(key))
        except (TypeError, ValueError):
            continue
        digest = str(value or "").strip()
        if chapter_index > 0 and digest:
            digest_map[chapter_index] = digest
    return digest_map


def save_chapter_digest_index(
    book_title: str,
    digest_by_index: dict[int, str],
    *,
    root_dir: str | Path = "books",
) -> Path:
    book_dir = ensure_book_directories(book_title, root_dir=root_dir)
    index_path = book_dir / _CHAPTER_DIGEST_INDEX_FILE
    payload = {str(index): digest for index, digest in sorted(digest_by_index.items()) if index > 0 and digest}
    index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return index_path


def read_saved_chapter_summaries(
    book_title: str,
    *,
    root_dir: str | Path = "books",
) -> dict[int, ChapterSummary]:
    root = Path(root_dir)
    book_dir = root / _book_dir_name(book_title)
    chapter_dir = book_dir / "chapter"
    if not chapter_dir.exists():
        return {}

    summaries: dict[int, ChapterSummary] = {}
    for chapter_path in sorted(chapter_dir.glob("*.md"), key=_chapter_sort_key):
        markdown = chapter_path.read_text(encoding="utf-8", errors="ignore")
        match = _CHAPTER_NAME_RE.match(chapter_path.name)
        chapter_index = int(match.group("index")) if match else 0
        chapter_title = match.group("title") if match else chapter_path.stem

        heading_match = re.search(r"^#\s+Chapter\s+\d+:\s*(.+)$", markdown, flags=re.MULTILINE)
        if heading_match and heading_match.group(1).strip():
            chapter_title = heading_match.group(1).strip()

        summary_text = extract_section(markdown, "요약")
        key_events = [
            row.strip()[2:].strip()
            for row in extract_section(markdown, "핵심 사건").splitlines()
            if row.strip().startswith("- ")
        ]

        if chapter_index <= 0:
            continue

        summaries[chapter_index] = ChapterSummary(
            chapter_index=chapter_index,
            chapter_title=chapter_title,
            summary=summary_text or "",
            key_events=key_events,
            character_events=[],
            character_traits=[],
        )
    return summaries


def prune_chapter_files(
    book_title: str,
    chapter_summaries: list[ChapterSummary],
    *,
    root_dir: str | Path = "books",
) -> None:
    book_dir = ensure_book_directories(book_title, root_dir=root_dir)
    chapter_dir = book_dir / "chapter"
    valid_names = {_chapter_file_name(chapter) for chapter in chapter_summaries}
    for path in chapter_dir.glob("*.md"):
        if path.name not in valid_names:
            path.unlink(missing_ok=True)
