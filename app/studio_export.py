import html
from pathlib import Path
from typing import Any

from ebooklib import epub

from app.storage import (
    list_series_volumes,
    read_bible,
    read_book_detail,
    read_series,
    read_studio_project,
)

_BIBLE_APPENDIX_TITLE = "부록 — 세계관/캐릭터"


def _markdown_to_html(markdown: str) -> str:
    parts: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            text = html.escape("\n".join(buffer)).replace("\n", "<br />")
            parts.append(f"<p>{text}</p>")
            buffer.clear()

    for line in (markdown or "").splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if stripped.startswith("### "):
            flush()
            parts.append(f"<h3>{html.escape(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            flush()
            parts.append(f"<h2>{html.escape(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            flush()
            parts.append(f"<h1>{html.escape(stripped[2:])}</h1>")
        else:
            buffer.append(line)
    flush()
    return "\n".join(parts)


def _collect_container(
    root_dir: str | Path,
    *,
    slug: str,
    container_type: str,
    include_bible: bool,
) -> dict[str, Any]:
    if container_type == "series":
        series = read_series(root_dir, slug=slug)
        title = series["series_title"]
        language = series.get("language", "ko")
        sections = []
        for volume in list_series_volumes(root_dir, series_slug=slug):
            detail = read_book_detail(root_dir, slug=volume["slug"])
            sections.append(
                {
                    "heading": f"{volume['volume_index']}권 {volume['book_title']}",
                    "chapters": detail["chapters"],
                }
            )
    else:
        project = read_studio_project(root_dir, slug=slug)
        detail = read_book_detail(root_dir, slug=slug)
        title = project.get("book_title") or detail["book_title"]
        language = project.get("language", "ko")
        sections = [{"heading": None, "chapters": detail["chapters"]}]

    bible_markdown = ""
    if include_bible:
        bible = read_bible(root_dir, slug=slug)
        blocks = [f"## {_BIBLE_APPENDIX_TITLE}", ""]
        if bible["setting_markdown"]:
            blocks.extend([bible["setting_markdown"], ""])
        for character in bible["characters"]:
            blocks.extend([character["markdown"], ""])
        bible_markdown = "\n".join(blocks).strip()

    return {
        "title": title,
        "language": language or "ko",
        "sections": sections,
        "bible_markdown": bible_markdown,
    }


def _build_markdown(collected: dict[str, Any]) -> str:
    parts = [f"# {collected['title']}", ""]
    for section in collected["sections"]:
        if section["heading"]:
            parts.extend([f"## {section['heading']}", ""])
        for chapter in section["chapters"]:
            parts.extend([chapter["markdown"].rstrip(), "", "---", ""])
    if collected["bible_markdown"]:
        parts.extend([collected["bible_markdown"], ""])
    return "\n".join(parts).rstrip() + "\n"


def _build_epub(collected: dict[str, Any], *, identifier: str) -> epub.EpubBook:
    book = epub.EpubBook()
    book.set_identifier(identifier)
    book.set_title(collected["title"])
    book.set_language(collected["language"])

    spine: list[Any] = ["nav"]
    toc: list[Any] = []
    for section_index, section in enumerate(collected["sections"], start=1):
        for chapter in section["chapters"]:
            item = epub.EpubHtml(
                title=chapter["title"],
                file_name=f"chap_{section_index}_{chapter['index']}.xhtml",
                lang=collected["language"],
            )
            item.id = f"c{section_index}-{chapter['index']}"
            heading = (
                f"<h2>{html.escape(section['heading'])}</h2>" if section["heading"] else ""
            )
            item.content = (
                f"<html><head></head><body>{heading}"
                f"{_markdown_to_html(chapter['markdown'])}</body></html>"
            )
            book.add_item(item)
            spine.append(item)
            toc.append(epub.Link(item.file_name, chapter["title"], item.id))

    if collected["bible_markdown"]:
        item = epub.EpubHtml(
            title=_BIBLE_APPENDIX_TITLE,
            file_name="bible.xhtml",
            lang=collected["language"],
        )
        item.id = "bible"
        item.content = (
            f"<html><head></head><body>{_markdown_to_html(collected['bible_markdown'])}"
            "</body></html>"
        )
        book.add_item(item)
        spine.append(item)
        toc.append(epub.Link(item.file_name, _BIBLE_APPENDIX_TITLE, item.id))

    book.spine = spine
    book.toc = tuple(toc)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    return book


def export_studio_container(
    root_dir: str | Path,
    *,
    slug: str,
    container_type: str,
    export_format: str,
    include_bible: bool = False,
) -> Path:
    collected = _collect_container(
        root_dir,
        slug=slug,
        container_type=container_type,
        include_bible=include_bible,
    )
    export_dir = Path(root_dir) / slug / "export"
    export_dir.mkdir(parents=True, exist_ok=True)

    if export_format == "epub":
        target = export_dir / f"{slug}.epub"
        epub.write_epub(
            str(target), _build_epub(collected, identifier=f"book-pro-{slug}")
        )
    else:
        target = export_dir / f"{slug}.md"
        target.write_text(_build_markdown(collected), encoding="utf-8")
    return target
