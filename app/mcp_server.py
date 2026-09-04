import logging
from functools import partial
from typing import Any

from fastapi.concurrency import run_in_threadpool

from app import service
from app.config import get_settings
from app.progress import get_upload_progress
from app.studio_agent import run_agent as studio_agent_run

try:  # pragma: no cover - fastmcp는 requirements에 포함되어 있으나 설치 전 환경 보호용
    from fastmcp import FastMCP
    from fastmcp.exceptions import ToolError
except ImportError:  # pragma: no cover
    FastMCP = None

    class ToolError(Exception):
        pass


logger = logging.getLogger("uvicorn.error")

MCP_NAME = "book-pro"
MCP_INSTRUCTIONS = (
    "book-pro is a book library and AI writing studio. "
    "Use the reading tools to browse the library, read chapter summaries, original EPUB text, "
    "characters and world settings, and to ask questions about a book. "
    "Use the studio tools to create projects or series, co-write with the studio assistant, "
    "manage the setting bible, and finalize chapters. "
    "Long running EPUB summarization is asynchronous: start it and poll get_upload_progress."
)

_server: Any = None


def _tool_error(exc: Exception) -> Exception:
    message = service.normalize_error_message(exc)
    logger.warning("[MCP 도구 오류] %s", message)
    return ToolError(message)


async def _run(func: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return await run_in_threadpool(partial(func, *args, **kwargs))
    except Exception as exc:  # noqa: BLE001
        raise _tool_error(exc) from exc


async def list_books(
    page: int = 1,
    page_size: int = 20,
    only_studio: bool = False,
) -> dict[str, Any]:
    """List books in the library.

    Args:
        page: 1-based page number.
        page_size: Items per page (1-50).
        only_studio: Only return books created in the Studio.
    """
    return await _run(
        service.list_library,
        page=page,
        page_size=page_size,
        only_studio=only_studio,
    )


async def get_book_overview(slug: str) -> dict[str, Any]:
    """Get a book overview: chapter list with previews, character previews and world settings.

    Args:
        slug: Book slug such as `book-my-novel` (from list_books).
    """
    return await _run(service.get_book_overview, slug)


async def list_chapters(slug: str) -> dict[str, Any]:
    """List all summarized chapters of a book with short previews.

    Args:
        slug: Book slug.
    """
    return await _run(service.list_chapters, slug)


async def read_chapter_summary(slug: str, chapter_index: int) -> dict[str, Any]:
    """Read the full markdown summary of one chapter.

    Args:
        slug: Book slug.
        chapter_index: Chapter number shown by list_chapters.
    """
    return await _run(service.read_chapter_summary, slug, chapter_index)


async def read_original_chapter(
    slug: str,
    chapter_index: int,
    offset: int = 0,
    max_chars: int = 12000,
) -> dict[str, Any]:
    """Read the original EPUB text of one chapter, re-parsed from the stored EPUB.

    Args:
        slug: Book slug.
        chapter_index: Chapter number.
        offset: Character offset to start from (for paging through long chapters).
        max_chars: Maximum characters to return (500-60000).
    """
    return await _run(
        service.read_original_chapter,
        slug,
        chapter_index,
        offset=offset,
        max_chars=max_chars,
    )


async def list_characters(slug: str) -> dict[str, Any]:
    """List the characters of a book.

    Args:
        slug: Book slug.
    """
    return await _run(service.list_characters, slug)


async def read_character(slug: str, name: str) -> dict[str, Any]:
    """Read the full character profile markdown.

    Args:
        slug: Book slug.
        name: Character name (from list_characters).
    """
    return await _run(service.read_character, slug, name)


async def read_world_setting(slug: str) -> dict[str, Any]:
    """Read the world/setting summary markdown of a book.

    Args:
        slug: Book slug.
    """
    return await _run(service.read_world_setting, slug)


async def search_book(
    slug: str,
    query: str,
    scope: str = "all",
    max_results: int = 20,
) -> dict[str, Any]:
    """Search text inside a book and return snippets with match positions.

    Args:
        slug: Book slug.
        query: Text to search for (case-insensitive).
        scope: `all`, `summary` (summaries/characters/settings) or `original` (EPUB text).
        max_results: Maximum number of matches (1-100).
    """
    return await _run(
        service.search_book,
        slug,
        query,
        scope=scope,
        max_results=max_results,
    )


async def ask_book(
    slug: str,
    question: str,
    mode: str = "book",
    character_name: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """Ask a question about a book and get an AI answer grounded in its summaries.

    Args:
        slug: Book slug.
        question: Question to ask.
        mode: `book` for whole-book questions, `character` to answer in a character's voice.
        character_name: Required when mode is `character`.
        provider: LLM provider override (openai, anthropic, openrouter, venice, kilo-code, opencode-go, opencode-zen).
        model: Model override.
        api_key: Provider API key override (falls back to server defaults).
        language: Answer language (default `ko`).
    """
    return await _run(
        service.ask_book,
        slug,
        question,
        mode=mode,
        character_name=character_name,
        provider=provider,
        api_key=api_key,
        model=model,
        language=language,
    )


async def get_reading_progress(slug: str) -> dict[str, Any]:
    """Get the saved reading position (page, total_pages, ratio) of a book.

    Args:
        slug: Book slug.
    """
    return await _run(service.get_reading_progress, slug)


async def update_reading_progress(
    slug: str,
    page: int,
    total_pages: int,
    ratio: float | None = None,
) -> dict[str, Any]:
    """Save the reading position of a book so reading can resume later.

    Args:
        slug: Book slug.
        page: Zero-based page index.
        total_pages: Total page count.
        ratio: Optional 0-1 progress ratio (computed from page when omitted).
    """
    return await _run(
        service.update_reading_progress,
        slug,
        page=page,
        total_pages=total_pages,
        ratio=ratio,
    )


async def list_provider_models(
    provider: str,
    api_key: str | None = None,
) -> dict[str, Any]:
    """List the models available for a provider.

    Args:
        provider: openai, anthropic, openrouter, venice, kilo-code, opencode-go or opencode-zen.
        api_key: Provider API key (falls back to server defaults).
    """
    return await _run(service.fetch_models, provider, api_key)


async def import_epub(
    file_path: str | None = None,
    base64_content: str | None = None,
    file_name: str | None = None,
) -> dict[str, Any]:
    """Import an EPUB into the library without summarizing it.

    Provide either `base64_content` or `file_path`. `file_path` is only accepted inside
    the directory configured by BOOK_PRO_MCP_IMPORT_DIR.

    Args:
        file_path: Absolute path to a local .epub inside BOOK_PRO_MCP_IMPORT_DIR.
        base64_content: Base64 encoded EPUB payload.
        file_name: File name to use with `base64_content`.
    """
    try:
        payload, name = service.read_epub_source(
            file_path=file_path,
            base64_content=base64_content,
            file_name=file_name,
        )
    except Exception as exc:  # noqa: BLE001
        raise _tool_error(exc) from exc
    return await _run(service.import_epub, payload, name)


async def summarize_epub_start(
    file_path: str | None = None,
    base64_content: str | None = None,
    file_name: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    language: str = "ko",
    precise_analysis: bool = False,
    max_chapters: int | None = None,
    chapter_parallel: int | None = None,
    upload_id: str | None = None,
) -> dict[str, Any]:
    """Start an EPUB summarization job in the background and return an upload_id immediately.

    Poll `get_upload_progress` with the returned upload_id until status is `completed` or `failed`.

    Args:
        file_path: Absolute path to a local .epub inside BOOK_PRO_MCP_IMPORT_DIR.
        base64_content: Base64 encoded EPUB payload.
        file_name: File name to use with `base64_content`.
        provider: LLM provider override.
        model: Model override.
        api_key: Provider API key override.
        language: Summary language (default `ko`).
        precise_analysis: Enable precise chapter-level character analysis.
        max_chapters: Limit the number of chapters (omit for unlimited).
        chapter_parallel: Chapter workers for a single book (1-8).
        upload_id: Optional custom job id.
    """
    try:
        payload, name = service.read_epub_source(
            file_path=file_path,
            base64_content=base64_content,
            file_name=file_name,
        )
        service.build_summarizer(provider=provider, api_key=api_key, model=model)
    except Exception as exc:  # noqa: BLE001
        raise _tool_error(exc) from exc

    return service.start_summary_job(
        upload_id=upload_id,
        payload=payload,
        file_name=name,
        provider=provider,
        api_key=api_key,
        model=model,
        language=language,
        precise_analysis=precise_analysis,
        max_chapters=max_chapters,
        chapter_parallel=chapter_parallel,
    )


async def summarize_book_start(
    slug: str,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    language: str = "ko",
    precise_analysis: bool = False,
    max_chapters: int | None = None,
    chapter_parallel: int | None = None,
    upload_id: str | None = None,
) -> dict[str, Any]:
    """Start summarizing an EPUB that is already stored in the library.

    Args:
        slug: Book slug that already has an EPUB.
        provider: LLM provider override.
        model: Model override.
        api_key: Provider API key override.
        language: Summary language (default `ko`).
        precise_analysis: Enable precise chapter-level character analysis.
        max_chapters: Limit the number of chapters.
        chapter_parallel: Chapter workers for a single book (1-8).
        upload_id: Optional custom job id.
    """
    try:
        service.build_summarizer(provider=provider, api_key=api_key, model=model)
    except Exception as exc:  # noqa: BLE001
        raise _tool_error(exc) from exc

    return service.start_summary_job(
        upload_id=upload_id,
        book_slug=slug,
        provider=provider,
        api_key=api_key,
        model=model,
        language=language,
        precise_analysis=precise_analysis,
        max_chapters=max_chapters,
        chapter_parallel=chapter_parallel,
    )


async def get_upload_progress_state(upload_id: str) -> dict[str, Any]:
    """Get the progress of a summarization job started by summarize_epub_start / summarize_book_start.

    Args:
        upload_id: Job id returned by the start tools.
    """
    payload = get_upload_progress(upload_id)
    if not payload:
        return {
            "upload_id": upload_id,
            "file_name": "",
            "book_title": "",
            "status": "queued",
            "progress": 0,
            "stage": "queued",
            "message": "요약 요청 대기 중",
            "chapter_index": None,
            "chapter_total": None,
            "chapter_title": None,
            "error": "",
        }
    return payload


async def list_active_uploads() -> list[dict[str, Any]]:
    """List queued or processing summarization jobs."""
    return await _run(service.list_uploads, active_only=True)


async def create_studio_project(
    title: str,
    premise: str = "",
    genre: str = "",
    language: str = "ko",
) -> dict[str, Any]:
    """Create a single-volume Studio project to write a new book with the AI assistant.

    Args:
        title: Book title.
        premise: One-line premise or logline.
        genre: Genre such as fantasy, romance, mystery.
        language: Writing language (default `ko`).
    """
    return await _run(
        service.create_project,
        title,
        premise=premise,
        genre=genre,
        language=language,
    )


async def create_studio_series(
    title: str,
    premise: str = "",
    genre: str = "",
    language: str = "ko",
) -> dict[str, Any]:
    """Create a multi-volume Studio series. Add volumes with add_series_volume.

    Args:
        title: Series title.
        premise: Series premise or logline.
        genre: Genre.
        language: Writing language (default `ko`).
    """
    return await _run(
        service.create_series,
        title,
        premise=premise,
        genre=genre,
        language=language,
    )


async def add_series_volume(
    series_slug: str,
    title: str,
    volume_index: int,
) -> dict[str, Any]:
    """Add a volume to a Studio series (inherits the series premise, genre and setting bible).

    Args:
        series_slug: Series slug from create_studio_series / list_studio_series.
        title: Volume title.
        volume_index: Volume number starting at 1.
    """
    return await _run(
        service.add_series_volume,
        series_slug,
        title,
        volume_index=volume_index,
    )


async def list_studio_projects() -> list[dict[str, Any]]:
    """List standalone Studio projects (volumes that belong to a series are excluded)."""
    return await _run(service.list_studio_projects)


async def list_studio_series() -> list[dict[str, Any]]:
    """List Studio series with their volumes."""
    return await _run(service.list_studio_series)


async def get_studio_series(slug: str) -> dict[str, Any]:
    """Get a Studio series with its volumes.

    Args:
        slug: Series slug.
    """
    return await _run(service.get_series, slug)


async def get_studio_project(slug: str) -> dict[str, Any]:
    """Get a Studio project: metadata, chapter count and the saved conversation.

    Args:
        slug: Project slug.
    """
    return await _run(service.get_project, slug)


async def studio_chat(
    slug: str,
    message: str,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """Send a message to the Studio co-writing assistant and get its full reply.

    The conversation is persisted, and already finalized chapters are used as context.

    Args:
        slug: Project slug (a volume slug for series volumes).
        message: Instruction or question for the assistant.
        provider: LLM provider override.
        model: Model override.
        api_key: Provider API key override.
        language: Writing language (defaults to the project language).
    """
    return await _run(
        service.studio_chat,
        slug,
        message,
        provider=provider,
        api_key=api_key,
        model=model,
        language=language,
    )


async def finalize_chapter(
    slug: str,
    chapter_index: int,
    chapter_title: str,
    content: str,
) -> dict[str, Any]:
    """Save a chapter of a Studio project as a finalized chapter markdown file.

    Args:
        slug: Project slug.
        chapter_index: Chapter number starting at 1.
        chapter_title: Chapter title.
        content: Chapter body text (usually the assistant reply from studio_chat).
    """
    return await _run(
        service.finalize_chapter,
        slug,
        chapter_index=chapter_index,
        chapter_title=chapter_title,
        content=content,
    )


async def get_bible(slug: str, container_type: str = "auto") -> dict[str, Any]:
    """Read the setting bible (world setting + character sheets) of a project or series.

    Args:
        slug: Project slug or series slug.
        container_type: `book` for a project, `series` for a series, `auto` to detect.
    """
    return await _run(service.get_bible_state, slug, container_type=container_type)


async def save_bible(
    slug: str,
    setting_markdown: str | None = None,
    characters_markdown: str | None = None,
    container_type: str = "auto",
) -> dict[str, Any]:
    """Save the setting bible of a project or series.

    Args:
        slug: Project slug or series slug.
        setting_markdown: World/setting markdown. Omit to keep the current value.
        characters_markdown: Character sheets as `## Name` blocks. Omit to keep the current value.
        container_type: `book` for a project, `series` for a series, `auto` to detect.
    """
    return await _run(
        service.save_bible_state,
        slug,
        setting_markdown=setting_markdown,
        characters_markdown=characters_markdown,
        container_type=container_type,
    )


async def update_studio_project(
    slug: str,
    premise: str | None = None,
    genre: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """Update Studio project metadata (fields left out are kept as-is).

    Args:
        slug: Project slug.
        premise: New premise/logline.
        genre: New genre.
        language: New writing language.
    """
    return await _run(
        service.update_project,
        slug,
        premise=premise,
        genre=genre,
        language=language,
    )


async def delete_studio_project(
    slug: str,
    container_type: str = "auto",
) -> dict[str, Any]:
    """Move a Studio project or series to the trash directory (books/.trash/...).

    Deleting a series keeps its volumes but detaches them from the series.
    The trash directory is not exposed through the reading tools.

    Args:
        slug: Project slug or series slug.
        container_type: `book` for a project, `series` for a series, `auto` to detect.
    """
    return await _run(service.delete_studio_container, slug, container_type=container_type)


async def export_studio_book(
    slug: str,
    export_format: str = "markdown",
    include_bible: bool = False,
) -> dict[str, Any]:
    """Export finalized chapters of a Studio project (or a whole series) to a file.

    Args:
        slug: Project slug or series slug.
        export_format: `markdown` or `epub`.
        include_bible: Append the setting bible (world/characters) as an appendix.
    """
    return await _run(
        service.export_studio_book,
        slug,
        export_format=export_format,
        include_bible=include_bible,
    )


async def studio_agent_chat(
    slug: str,
    message: str,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    language: str | None = None,
    mode: str = "auto",
    max_steps: int = 12,
) -> dict[str, Any]:
    """Run the agentic Studio assistant: it can read, create, edit and delete project files
    (chapters, setting bible, notes) via file tools before answering.

    Args:
        slug: Project slug (a volume slug for series volumes).
        message: Instruction or question for the agent.
        provider: LLM provider override.
        model: Model override (must support OpenAI-style tool calling).
        api_key: Provider API key override.
        language: Writing language (defaults to the project language).
        mode: `auto` applies file writes immediately, `approve` stores them as pending actions.
        max_steps: Max tool-calling steps per run (1-24).
    """
    return await _run(
        studio_agent_run,
        slug,
        message,
        provider=provider,
        api_key=api_key,
        model=model,
        language=language,
        mode=mode,
        max_steps=max_steps,
    )


async def studio_list_files(slug: str, path: str = "") -> dict[str, Any]:
    """List files/directories of a Studio project sandbox (relative paths).

    Args:
        slug: Project slug.
        path: Relative directory path (`""` for the project root).
    """
    return await _run(service.studio_list_files, slug, path)


async def studio_read_file(
    slug: str,
    path: str,
    offset: int = 0,
    max_chars: int | None = None,
) -> dict[str, Any]:
    """Read a text file (.md/.json/.txt) from a Studio project sandbox.

    Args:
        slug: Project slug.
        path: Relative file path (e.g. `chapter/c-1-제목.md`).
        offset: Character offset to start from.
        max_chars: Max characters to return.
    """
    return await _run(
        service.studio_read_file,
        slug,
        path,
        offset=offset,
        max_chars=max_chars,
    )


async def studio_write_file(slug: str, path: str, content: str) -> dict[str, Any]:
    """Create or overwrite a text file in a Studio project sandbox (snapshot is kept).

    Args:
        slug: Project slug.
        path: Relative file path (chapters: `chapter/c-<number>-<title>.md`).
        content: Full file content.
    """
    return await _run(service.studio_write_file, slug, path, content)


async def studio_edit_file(
    slug: str,
    path: str,
    find: str,
    replace: str,
    count: int = 1,
) -> dict[str, Any]:
    """Replace exact substring occurrences in a Studio project file (snapshot is kept).

    Args:
        slug: Project slug.
        path: Relative file path.
        find: Exact text to find.
        replace: Replacement text.
        count: Number of occurrences to replace.
    """
    return await _run(
        service.studio_edit_file,
        slug,
        path,
        find,
        replace,
        count=count,
    )


async def studio_delete_file(slug: str, path: str) -> dict[str, Any]:
    """Delete a Studio project file (moved to books/.trash).

    Args:
        slug: Project slug.
        path: Relative file path.
    """
    return await _run(service.studio_delete_file, slug, path)


async def bible_chat(
    slug: str,
    message: str,
    container_type: str = "book",
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """Ask the setting-bible assistant to draft or expand world settings and characters.

    The reply is not saved automatically: review it and persist it with save_bible.

    Args:
        slug: Project slug or series slug.
        message: What to draft or expand.
        container_type: `book` for a project, `series` for a series.
        provider: LLM provider override.
        model: Model override.
        api_key: Provider API key override.
        language: Writing language (default `ko`).
    """
    return await _run(
        service.bible_chat,
        slug,
        message,
        container_type=container_type,
        provider=provider,
        api_key=api_key,
        model=model,
        language=language,
    )


async def book_overview_resource(slug: str) -> str:
    overview = await run_in_threadpool(service.get_book_overview, slug)
    lines = [
        f"# {overview['book_title']}",
        "",
        f"- chapters: {overview['chapter_count']}",
        f"- characters: {overview['character_count']}",
        "",
        "## Chapters",
    ]
    for chapter in overview["chapters"]:
        lines.append(f"- {chapter['index']}. {chapter['title']}: {chapter['preview']}")
    if overview["characters"]:
        lines.extend(["", "## Characters"])
        for character in overview["characters"]:
            lines.append(f"- {character['name']}: {character['preview']}")
    if overview["setting_markdown"]:
        lines.extend(["", "## World settings", "", overview["setting_markdown"]])
    return "\n".join(lines)


async def book_chapter_resource(slug: str, index: int) -> str:
    chapter = await run_in_threadpool(service.read_chapter_summary, slug, int(index))
    return f"# {chapter['chapter_title']}\n\n{chapter['markdown']}"


async def book_original_resource(slug: str, index: int) -> str:
    chapter = await run_in_threadpool(service.read_original_chapter, slug, int(index))
    header = f"# {chapter['chapter_title']} (original text {chapter['offset']}-{chapter['offset'] + chapter['returned_chars']}/{chapter['total_chars']} chars)"
    return f"{header}\n\n{chapter['text']}"


async def book_setting_resource(slug: str) -> str:
    setting = await run_in_threadpool(service.read_world_setting, slug)
    return setting["setting_markdown"]


def read_book_guide(slug: str) -> str:
    return (
        "Read this book step by step with book-pro tools.\n"
        "1. Call get_book_overview to see the chapter list, characters and world settings.\n"
        "2. Call read_chapter_summary for the chapters you need, in order.\n"
        "3. Call read_original_chapter when you need the original EPUB text.\n"
        "4. Call search_book to locate specific scenes, names or phrases.\n"
        "5. Call ask_book when a question needs reasoning across the whole book.\n"
        "6. Call update_reading_progress to remember where you stopped.\n"
        f"Book slug: {slug}"
    )


def write_next_chapter(slug: str, instruction: str = "") -> str:
    guidance = (
        "Write the next chapter of this Studio project.\n"
        "1. Call get_studio_project to read the premise and finalized chapters.\n"
        "2. Call get_bible to load the world settings and character sheets.\n"
        "3. Call studio_chat with a concrete instruction to draft the chapter.\n"
        "4. Call finalize_chapter to save the approved chapter text.\n"
        f"Project slug: {slug}"
    )
    if instruction:
        guidance = f"{guidance}\nInstruction: {instruction}"
    return guidance


_TOOLS: list[Any] = [
    list_books,
    get_book_overview,
    list_chapters,
    read_chapter_summary,
    read_original_chapter,
    list_characters,
    read_character,
    read_world_setting,
    search_book,
    ask_book,
    get_reading_progress,
    update_reading_progress,
    list_provider_models,
    import_epub,
    summarize_epub_start,
    summarize_book_start,
    get_upload_progress_state,
    list_active_uploads,
    create_studio_project,
    create_studio_series,
    add_series_volume,
    list_studio_projects,
    list_studio_series,
    get_studio_series,
    get_studio_project,
    studio_chat,
    update_studio_project,
    delete_studio_project,
    export_studio_book,
    studio_agent_chat,
    studio_list_files,
    studio_read_file,
    studio_write_file,
    studio_edit_file,
    studio_delete_file,
    finalize_chapter,
    get_bible,
    save_bible,
    bible_chat,
]

_RESOURCE_TEMPLATES: list[tuple[str, Any]] = [
    ("book://{slug}/overview", book_overview_resource),
    ("book://{slug}/chapter/{index}", book_chapter_resource),
    ("book://{slug}/original/{index}", book_original_resource),
    ("book://{slug}/setting", book_setting_resource),
]

_PROMPTS: list[Any] = [
    read_book_guide,
    write_next_chapter,
]


class MountPathRewriteMiddleware:
    """Starlette Mount only matches `path/...`, so `/mcp` is rewritten to `/mcp/`."""

    def __init__(self, app: Any, *, path: str) -> None:
        self.app = app
        self.path = (path or "").rstrip("/")

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if (
            scope.get("type") == "http"
            and self.path
            and scope.get("path") == self.path
        ):
            normalized = f"{self.path}/"
            scope = {
                **scope,
                "path": normalized,
                "raw_path": normalized.encode("latin-1"),
            }
        await self.app(scope, receive, send)


class MCPHttpApp:
    def __init__(self, app: Any, *, token: str = "") -> None:
        self.app = app
        self.expected = f"Bearer {token}" if token else ""
        self.lifespan = getattr(app, "lifespan", None)

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") == "http" and self.expected and not self._authorized(scope):
            await self._unauthorized(send)
            return

        await self.app(scope, receive, send)

    async def _unauthorized(self, send: Any) -> None:
        body = b'{"error":"unauthorized"}'
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", b"Bearer"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    def _authorized(self, scope: Any) -> bool:
        for key, value in scope.get("headers", []):
            if key.decode("latin-1").lower() == "authorization":
                return value.decode("latin-1") == self.expected
        return False


def create_mcp_server() -> Any:
    if FastMCP is None:
        raise RuntimeError("fastmcp 패키지가 설치되지 않았습니다. `pip install -r requirements.txt` 후 다시 시도하세요.")

    server = FastMCP(MCP_NAME, instructions=MCP_INSTRUCTIONS)
    for tool in _TOOLS:
        server.tool(tool)
    for template, func in _RESOURCE_TEMPLATES:
        server.resource(template)(func)
    for prompt in _PROMPTS:
        server.prompt(prompt)
    return server


def get_mcp_server() -> Any:
    global _server
    if _server is None:
        _server = create_mcp_server()
    return _server


def build_mcp_app() -> Any | None:
    settings = get_settings()
    if not settings.mcp_enabled:
        logger.info("[MCP] BOOK_PRO_MCP_ENABLED=false 이므로 MCP를 비활성화합니다.")
        return None
    if FastMCP is None:
        logger.warning(
            "[MCP] fastmcp 패키지를 찾을 수 없어 MCP를 비활성화합니다. `pip install -r requirements.txt`를 실행하세요."
        )
        return None

    mount_path = mcp_mount_path()
    mcp_app = get_mcp_server().http_app(
        path="/",
        stateless_http=True,
        json_response=True,
    )

    token = (settings.mcp_token or "").strip()
    if not token:
        logger.info("[MCP] 엔드포인트 활성화: %s (인증 없음)", mount_path)
    else:
        logger.info("[MCP] 엔드포인트 활성화: %s (Bearer 토큰 인증)", mount_path)

    return MCPHttpApp(mcp_app, token=token)


def _normalized_path(value: str) -> str:
    path = (value or "").strip() or "/mcp"
    if not path.startswith("/"):
        path = f"/{path}"
    return path.rstrip("/") or "/mcp"


def mcp_mount_path() -> str:
    return _normalized_path(get_settings().mcp_path)


def main() -> None:
    server = get_mcp_server()
    logger.info("[MCP] stdio 서버 시작: %s", MCP_NAME)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
