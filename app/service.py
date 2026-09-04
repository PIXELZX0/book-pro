import asyncio
import base64
import binascii
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from fastapi.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.epub_parser import parse_epub
from app.progress import (
    complete_upload_progress,
    fail_upload_progress,
    init_upload_progress,
    list_upload_progress,
    update_upload_progress,
)
from app.prompts import build_studio_bible_prompt, build_studio_system_prompt
from app.provider_models import fetch_provider_models
from app.schemas import BookSummary, ChapterSummary
from app.storage import (
    compute_chapter_digest,
    ensure_book_directories,
    extract_section,
    get_latest_epub_path,
    list_books,
    list_series,
    list_series_volumes,
    load_chapter_digest_index,
    prune_chapter_files,
    read_bible,
    read_bible_conversation,
    read_book_detail,
    read_book_reader,
    read_book_reader_progress,
    read_book_summary_snapshot,
    read_saved_chapter_summaries,
    read_series,
    read_studio_conversation,
    read_studio_project,
    save_bible,
    save_bible_conversation,
    save_book_reader_progress,
    save_book_summary,
    save_chapter_digest_index,
    save_chapter_summary,
    save_series,
    save_studio_conversation,
    save_studio_project,
    save_uploaded_epub,
)
from app.summarizer import MultiProviderBookSummarizer, normalize_provider

logger = logging.getLogger("uvicorn.error")

MAX_CHAPTER_SUMMARY_PARALLEL = 8
DEFAULT_CHAPTER_PREVIEW_CHARS = 220
DEFAULT_ORIGINAL_CHARS = 12000
MAX_ORIGINAL_CHARS = 60000

_BIBLE_CHARACTER_BLOCK_RE = re.compile(r"(?m)^##\s+")


def build_summarizer(
    *,
    provider: str | None,
    api_key: str | None,
    model: str | None,
) -> MultiProviderBookSummarizer:
    settings = get_settings()
    provider_value = normalize_provider(provider or settings.default_provider)
    resolved_api_key = (api_key or "").strip() or settings.openai_api_key
    resolved_model = (model or "").strip()

    default_provider = normalize_provider(settings.default_provider)
    if not resolved_model and provider_value == default_provider:
        resolved_model = settings.default_model

    if not resolved_api_key:
        raise ValueError(
            "API key가 비어 있습니다. Web Panel에서 입력하거나 .env의 OPENAI_API_KEY를 설정하세요."
        )

    return MultiProviderBookSummarizer(
        provider=provider_value,
        api_key=resolved_api_key,
        model=resolved_model or None,
    )


def normalize_error_message(exc: Exception) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    lower = text.lower()

    if "incorrect api key provided" in lower or "invalid_api_key" in lower:
        return "API key가 유효하지 않습니다. Settings에서 선택한 Provider의 API key를 확인하세요."
    if "timed out" in lower or "timeout" in lower:
        return "AI provider 응답 대기 시간이 초과되었습니다. 잠시 후 다시 시도하세요."
    if "api key가 비어 있습니다" in text:
        return text
    if "not a zip file" in lower or "bad zip file" in lower or "bad crc-32" in lower:
        return (
            "EPUB 파일을 열 수 없습니다. 파일이 손상되었거나 업로드가 완전하지 않습니다. "
            "원본 EPUB을 다시 내려받아 업로드해 주세요."
        )

    if len(text) > 420:
        return f"{text[:420]}..."
    return text


def normalize_title_for_compare(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def resolve_chapter_parallel(requested: int | None, default_value: int) -> int:
    candidate = requested if requested is not None else default_value
    if candidate <= 0:
        candidate = 1
    return max(1, min(int(candidate), MAX_CHAPTER_SUMMARY_PARALLEL))


def is_local_tts_base_url(base_url: str) -> bool:
    candidate = (base_url or "").strip()
    if not candidate:
        return False
    try:
        host = (urlparse(candidate).hostname or "").strip().lower()
    except ValueError:
        return False
    return host in {"localhost", "127.0.0.1", "0.0.0.0", "::1", "host.docker.internal"}


def resolve_tts_api_key(
    *,
    payload_tts_api_key: str | None,
    default_tts_api_key: str,
    tts_base_url: str,
) -> str:
    resolved = (payload_tts_api_key or "").strip() or (default_tts_api_key or "").strip()
    if resolved:
        return resolved

    if is_local_tts_base_url(tts_base_url):
        return "none"

    raise ValueError(
        "Qwen3 TTS API key가 필요합니다. tts_api_key 또는 BOOK_PRO_QWEN_TTS_API_KEY를 설정하세요. "
        "로컬 vLLM-Omni(localhost) 사용 시에는 API key 없이 자동으로 'none' 값을 사용합니다."
    )

def _preview(text: str, limit: int) -> str:
    flat = re.sub(r"\s+", " ", (text or "").strip())
    if len(flat) <= limit:
        return flat
    return f"{flat[:limit]}..."


def _write_temp_epub(payload: bytes) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp:
        tmp.write(payload)
        return tmp.name


def resolve_chapter_limit(requested: int | None, settings: Settings) -> int | None:
    chapter_limit = requested if requested is not None else settings.max_chapters_per_request
    if chapter_limit is not None and chapter_limit <= 0:
        return None
    return chapter_limit


def fetch_models(provider: str, api_key: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    normalized = normalize_provider(provider)
    resolved_key = (api_key or "").strip()
    if not resolved_key and normalized == normalize_provider(settings.default_provider):
        resolved_key = settings.openai_api_key
    return {"provider": normalized, "models": fetch_provider_models(normalized, api_key=resolved_key)}


def _resolve_import_path(file_path: str, import_dir: str) -> Path:
    candidate = Path(file_path).expanduser().resolve()
    if not candidate.is_file():
        raise ValueError(f"EPUB 파일을 찾을 수 없습니다: {file_path}")
    if candidate.suffix.lower() != ".epub":
        raise ValueError(".epub 파일만 가져올 수 있습니다.")
    root = Path(import_dir).expanduser().resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(
            "허용된 가져오기 디렉터리(BOOK_PRO_MCP_IMPORT_DIR) 밖의 파일은 읽을 수 없습니다."
        )
    return candidate


def read_epub_source(
    *,
    file_path: str | None,
    base64_content: str | None,
    file_name: str | None,
) -> tuple[bytes, str]:
    raw_base64 = (base64_content or "").strip()
    if raw_base64:
        try:
            payload = base64.b64decode(raw_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("base64_content를 디코딩할 수 없습니다.") from exc
        if not payload:
            raise ValueError("base64_content가 비어 있습니다.")
        name = (file_name or "").strip() or "upload.epub"
        if not name.lower().endswith(".epub"):
            name = f"{name}.epub"
        return payload, name

    raw_path = (file_path or "").strip()
    if raw_path:
        import_dir = (get_settings().mcp_import_dir or "").strip()
        if not import_dir:
            raise ValueError(
                "파일 경로 가져오기는 BOOK_PRO_MCP_IMPORT_DIR이 설정된 경우에만 가능합니다. "
                "base64_content를 사용하세요."
            )
        candidate = _resolve_import_path(raw_path, import_dir)
        return candidate.read_bytes(), candidate.name

    raise ValueError("file_path 또는 base64_content 중 하나는 반드시 필요합니다.")


def import_epub(payload: bytes, file_name: str) -> dict[str, Any]:
    settings = get_settings()
    name = (file_name or "").strip() or "upload.epub"
    temp_path = _write_temp_epub(payload)
    try:
        book = parse_epub(temp_path)
        saved_epub = save_uploaded_epub(
            book.title,
            source_file_path=temp_path,
            original_filename=name,
            root_dir=settings.output_dir,
        )
        book_dir = ensure_book_directories(book.title, root_dir=settings.output_dir)
    finally:
        os.remove(temp_path)

    logger.info("[MCP EPUB 가져오기] file='%s' slug='%s'", name, book_dir.name)
    return {
        "slug": book_dir.name,
        "book_title": book.title,
        "chapter_count": len(book.chapters),
        "epub_path": str(saved_epub),
    }


async def run_summary_job(
    *,
    upload_id: str,
    payload: bytes | None = None,
    file_name: str | None = None,
    book_slug: str | None = None,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    language: str = "ko",
    precise_analysis: bool = False,
    max_chapters: int | None = None,
    chapter_parallel: int | None = None,
) -> None:
    settings = get_settings()
    temp_path: str | None = None
    try:
        summarizer = build_summarizer(provider=provider, api_key=api_key, model=model)
        chapter_limit = resolve_chapter_limit(max_chapters, settings)
        parallel = resolve_chapter_parallel(chapter_parallel, settings.chapter_parallel)
        update_upload_progress(
            upload_id,
            status="processing",
            progress=1,
            stage="start",
            message="요약 시작",
        )

        if payload is not None and file_name:
            temp_path = _write_temp_epub(payload)
            source_path, source_name = temp_path, file_name
        elif book_slug:
            epub_path = get_latest_epub_path(settings.output_dir, slug=book_slug)
            source_path, source_name = str(epub_path), epub_path.name
        else:
            raise ValueError("요약할 EPUB 파일 정보가 없습니다.")

        summary = await run_in_threadpool(
            summarize_from_temp_path,
            source_path,
            source_name,
            summarizer,
            chapter_limit,
            parallel,
            (language or "ko").strip() or "ko",
            precise_analysis,
            settings.output_dir,
            upload_id,
        )
        update_upload_progress(upload_id, book_title=summary.book_title)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[MCP 요약 실패] upload_id='%s'", upload_id)
        fail_upload_progress(upload_id, error=normalize_error_message(exc))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def start_summary_job(
    *,
    upload_id: str | None = None,
    payload: bytes | None = None,
    file_name: str | None = None,
    book_slug: str | None = None,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    language: str = "ko",
    precise_analysis: bool = False,
    max_chapters: int | None = None,
    chapter_parallel: int | None = None,
) -> dict[str, Any]:
    job_id = (upload_id or "").strip() or uuid4().hex
    init_upload_progress(job_id, file_name=file_name or book_slug or "unknown.epub")
    update_upload_progress(
        job_id,
        status="queued",
        progress=0,
        stage="queued",
        message="요약 요청 대기 중",
    )
    asyncio.create_task(
        run_summary_job(
            upload_id=job_id,
            payload=payload,
            file_name=file_name,
            book_slug=book_slug,
            provider=provider,
            api_key=api_key,
            model=model,
            language=language,
            precise_analysis=precise_analysis,
            max_chapters=max_chapters,
            chapter_parallel=chapter_parallel,
        )
    )
    return {"upload_id": job_id, "status": "queued"}


def list_library(*, page: int = 1, page_size: int = 20, only_studio: bool = False) -> dict[str, Any]:
    settings = get_settings()
    safe_page = max(1, int(page))
    safe_page_size = max(1, min(int(page_size), 50))
    payload = list_books(settings.output_dir, page=safe_page, page_size=safe_page_size)
    items = list(payload["items"])
    if only_studio:
        items = [item for item in items if item.get("is_studio")]
    return {
        "page": payload["page"],
        "page_size": payload["page_size"],
        "total": len(items),
        "items": items,
    }


def get_book_overview(slug: str) -> dict[str, Any]:
    settings = get_settings()
    detail = read_book_detail(settings.output_dir, slug=slug)
    return {
        "slug": detail["slug"],
        "book_title": detail["book_title"],
        "chapter_count": detail["chapter_count"],
        "character_count": detail["character_count"],
        "updated_at": detail["updated_at"],
        "is_studio": detail["is_studio"],
        "chapters": [
            {
                "index": chapter["index"],
                "title": chapter["title"],
                "preview": _preview(chapter["markdown"], DEFAULT_CHAPTER_PREVIEW_CHARS),
            }
            for chapter in detail["chapters"]
        ],
        "characters": [
            {
                "name": character["name"],
                "preview": _preview(character["markdown"], DEFAULT_CHAPTER_PREVIEW_CHARS),
            }
            for character in detail["characters"]
        ],
        "setting_markdown": detail["setting_markdown"],
    }


def list_chapters(slug: str) -> dict[str, Any]:
    settings = get_settings()
    detail = read_book_detail(settings.output_dir, slug=slug)
    return {
        "slug": slug,
        "book_title": detail["book_title"],
        "chapter_count": detail["chapter_count"],
        "chapters": [
            {
                "index": chapter["index"],
                "title": chapter["title"],
                "file_name": chapter["file_name"],
                "preview": _preview(chapter["markdown"], DEFAULT_CHAPTER_PREVIEW_CHARS),
            }
            for chapter in detail["chapters"]
        ],
    }


def read_chapter_summary(slug: str, chapter_index: int) -> dict[str, Any]:
    settings = get_settings()
    detail = read_book_detail(settings.output_dir, slug=slug)
    for chapter in detail["chapters"]:
        if chapter["index"] == chapter_index:
            return {
                "slug": slug,
                "book_title": detail["book_title"],
                "chapter_index": chapter["index"],
                "chapter_title": chapter["title"],
                "file_name": chapter["file_name"],
                "markdown": chapter["markdown"],
            }
    raise ValueError(f"챕터를 찾을 수 없습니다: {chapter_index}")


def list_characters(slug: str) -> dict[str, Any]:
    settings = get_settings()
    detail = read_book_detail(settings.output_dir, slug=slug)
    return {
        "slug": slug,
        "book_title": detail["book_title"],
        "character_count": detail["character_count"],
        "characters": [
            {
                "name": character["name"],
                "file_name": character["file_name"],
                "preview": _preview(character["markdown"], DEFAULT_CHAPTER_PREVIEW_CHARS),
            }
            for character in detail["characters"]
        ],
    }


def read_character(slug: str, name: str) -> dict[str, Any]:
    settings = get_settings()
    detail = read_book_detail(settings.output_dir, slug=slug)
    needle = (name or "").strip().lower()
    for character in detail["characters"]:
        if character["name"].lower() == needle:
            return {
                "slug": slug,
                "book_title": detail["book_title"],
                "name": character["name"],
                "file_name": character["file_name"],
                "markdown": character["markdown"],
            }
    raise ValueError(f"캐릭터를 찾을 수 없습니다: {name}")


def read_world_setting(slug: str) -> dict[str, Any]:
    settings = get_settings()
    detail = read_book_detail(settings.output_dir, slug=slug)
    return {
        "slug": slug,
        "book_title": detail["book_title"],
        "setting_markdown": detail["setting_markdown"],
    }


def read_original_chapter(
    slug: str,
    chapter_index: int,
    *,
    offset: int = 0,
    max_chars: int = DEFAULT_ORIGINAL_CHARS,
) -> dict[str, Any]:
    settings = get_settings()
    reader = read_book_reader(settings.output_dir, slug=slug)
    for chapter in reader["chapters"]:
        if chapter["index"] == chapter_index:
            limit = max(500, min(int(max_chars), MAX_ORIGINAL_CHARS))
            start = max(0, int(offset))
            text = chapter["text"] or ""
            sliced = text[start : start + limit]
            return {
                "slug": slug,
                "book_title": reader["book_title"],
                "chapter_index": chapter["index"],
                "chapter_title": chapter["title"],
                "offset": start,
                "returned_chars": len(sliced),
                "total_chars": len(text),
                "has_more": start + len(sliced) < len(text),
                "text": sliced,
            }
    raise ValueError(f"챕터를 찾을 수 없습니다: {chapter_index}")


def search_book(
    slug: str,
    query: str,
    *,
    scope: str = "all",
    max_results: int = 20,
    context_chars: int = 160,
) -> dict[str, Any]:
    settings = get_settings()
    needle = (query or "").strip()
    if not needle:
        raise ValueError("검색어를 입력해 주세요.")

    resolved_scope = (scope or "all").strip().lower()
    if resolved_scope not in {"all", "summary", "original"}:
        raise ValueError("scope는 all, summary, original만 가능합니다.")

    limit = max(1, min(int(max_results), 100))
    detail = read_book_detail(settings.output_dir, slug=slug)
    matches: list[dict[str, Any]] = []

    def collect(source: str, chapter_index: int | None, label: str, text: str) -> None:
        haystack = (text or "").lower()
        position = haystack.find(needle.lower())
        while position != -1 and len(matches) < limit:
            start = max(0, position - context_chars // 2)
            end = min(len(text or ""), position + len(needle) + context_chars // 2)
            matches.append(
                {
                    "source": source,
                    "chapter_index": chapter_index,
                    "title": label,
                    "position": position,
                    "snippet": (text or "")[start:end],
                }
            )
            position = haystack.find(needle.lower(), position + len(needle))

    if resolved_scope in {"all", "summary"}:
        for chapter in detail["chapters"]:
            collect("summary", chapter["index"], chapter["title"], chapter["markdown"])
        for character in detail["characters"]:
            collect("summary", None, character["name"], character["markdown"])
        collect("summary", None, "세계관/설정", detail["setting_markdown"])

    if resolved_scope in {"all", "original"}:
        try:
            reader = read_book_reader(settings.output_dir, slug=slug)
        except FileNotFoundError:
            reader = None
        if reader:
            for chapter in reader["chapters"]:
                collect("original", chapter["index"], chapter["title"], chapter["text"])

    return {
        "slug": slug,
        "book_title": detail["book_title"],
        "query": needle,
        "scope": resolved_scope,
        "truncated": len(matches) >= limit,
        "matches": matches[:limit],
    }


def ask_book(
    slug: str,
    question: str,
    *,
    mode: str = "book",
    character_name: str | None = None,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    clean_question = (question or "").strip()
    if not clean_question:
        raise ValueError("질문을 입력해 주세요.")

    resolved_mode = (mode or "book").strip().lower()
    if resolved_mode not in {"book", "character"}:
        raise ValueError("mode는 book 또는 character만 가능합니다.")

    resolved_character = (character_name or "").strip() or None
    if resolved_mode == "character" and not resolved_character:
        raise ValueError("character 모드에서는 character_name이 필요합니다.")

    settings = get_settings()
    snapshot = read_book_summary_snapshot(settings.output_dir, slug=slug)
    summarizer = build_summarizer(provider=provider, api_key=api_key, model=model)
    answer = summarizer.answer_about_book(
        book_title=snapshot["book_title"],
        chapter_summaries=snapshot["chapter_summaries"],
        character_summaries_text=snapshot["character_summaries_text"],
        setting_markdown=snapshot["setting_markdown"],
        question=clean_question,
        language=(language or "ko").strip() or "ko",
        character_name=resolved_character if resolved_mode == "character" else None,
    )
    return {
        "slug": slug,
        "book_title": snapshot["book_title"],
        "mode": resolved_mode,
        "character_name": resolved_character if resolved_mode == "character" else None,
        "answer": answer,
    }


def get_reading_progress(slug: str) -> dict[str, Any]:
    settings = get_settings()
    return read_book_reader_progress(settings.output_dir, slug=slug)


def update_reading_progress(
    slug: str,
    *,
    page: int,
    total_pages: int,
    ratio: float | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    return save_book_reader_progress(
        settings.output_dir,
        slug=slug,
        page=page,
        total_pages=total_pages,
        ratio=ratio,
    )


def create_project(
    title: str,
    *,
    premise: str = "",
    genre: str = "",
    language: str = "ko",
) -> dict[str, Any]:
    settings = get_settings()
    clean_title = (title or "").strip()
    if not clean_title:
        raise ValueError("제목을 입력해 주세요.")

    project_path = save_studio_project(
        clean_title,
        premise=(premise or "").strip(),
        genre=(genre or "").strip(),
        language=(language or "ko").strip() or "ko",
        root_dir=settings.output_dir,
    )
    slug = project_path.parent.name
    project = read_studio_project(settings.output_dir, slug=slug)
    logger.info("[MCP 스튜디오 프로젝트 생성] slug='%s'", slug)
    return {"slug": slug, "chapter_count": 0, **project}


def create_series(
    title: str,
    *,
    premise: str = "",
    genre: str = "",
    language: str = "ko",
) -> dict[str, Any]:
    settings = get_settings()
    clean_title = (title or "").strip()
    if not clean_title:
        raise ValueError("제목을 입력해 주세요.")

    series_path = save_series(
        clean_title,
        premise=(premise or "").strip(),
        genre=(genre or "").strip(),
        language=(language or "ko").strip() or "ko",
        root_dir=settings.output_dir,
    )
    slug = series_path.parent.name
    series = read_series(settings.output_dir, slug=slug)
    logger.info("[MCP 스튜디오 시리즈 생성] slug='%s'", slug)
    return {"slug": slug, "volumes": [], **series}


def add_series_volume(series_slug: str, title: str, *, volume_index: int) -> dict[str, Any]:
    settings = get_settings()
    clean_title = (title or "").strip()
    if not clean_title:
        raise ValueError("권 제목을 입력해 주세요.")

    series = read_series(settings.output_dir, slug=series_slug)
    project_path = save_studio_project(
        clean_title,
        premise=series.get("premise", ""),
        genre=series.get("genre", ""),
        language=series.get("language", "ko"),
        root_dir=settings.output_dir,
        book_format="long",
        series_slug=series_slug,
        volume_index=int(volume_index),
    )
    volume_slug = project_path.parent.name

    bible = read_bible(settings.output_dir, slug=series_slug)
    if bible["setting_markdown"] or bible["characters"]:
        save_bible(
            settings.output_dir,
            slug=volume_slug,
            setting_markdown=bible["setting_markdown"],
            characters=bible["characters"],
        )

    project = read_studio_project(settings.output_dir, slug=volume_slug)
    logger.info(
        "[MCP 스튜디오 권 추가] series='%s' volume='%s' index=%s",
        series_slug,
        volume_slug,
        volume_index,
    )
    return {"slug": volume_slug, "chapter_count": 0, **project}


def list_studio_projects() -> list[dict[str, Any]]:
    settings = get_settings()
    payload = list_books(settings.output_dir, page=1, page_size=50)
    return [
        item
        for item in payload["items"]
        if item.get("is_studio") and not item.get("series_slug")
    ]


def list_studio_series() -> list[dict[str, Any]]:
    settings = get_settings()
    return list_series(settings.output_dir)


def get_series(slug: str) -> dict[str, Any]:
    settings = get_settings()
    series = read_series(settings.output_dir, slug=slug)
    return {
        "slug": slug,
        "volumes": list_series_volumes(settings.output_dir, series_slug=slug),
        **series,
    }


def get_project(slug: str) -> dict[str, Any]:
    settings = get_settings()
    project = read_studio_project(settings.output_dir, slug=slug)
    detail = read_book_detail(settings.output_dir, slug=slug)
    messages = read_studio_conversation(settings.output_dir, slug=slug)
    return {
        "slug": slug,
        "chapter_count": detail["chapter_count"],
        "messages": messages,
        **project,
    }


def studio_chat(
    slug: str,
    message: str,
    *,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    clean_message = (message or "").strip()
    if not clean_message:
        raise ValueError("메시지를 입력해 주세요.")

    project = read_studio_project(settings.output_dir, slug=slug)
    detail = read_book_detail(settings.output_dir, slug=slug)
    history = read_studio_conversation(settings.output_dir, slug=slug)
    summarizer = build_summarizer(provider=provider, api_key=api_key, model=model)
    resolved_language = (language or project.get("language") or "ko").strip() or "ko"

    finalized_chapters = [
        {
            "chapter_index": chapter["index"],
            "chapter_title": chapter["title"],
            "summary": extract_section(chapter["markdown"], "요약") or "",
        }
        for chapter in detail["chapters"]
    ]

    now = datetime.now(tz=timezone.utc).isoformat()
    user_turn = {"role": "user", "content": clean_message, "created_at": now}
    updated_history = history + [user_turn]
    save_studio_conversation(settings.output_dir, slug=slug, messages=updated_history)

    system_prompt = build_studio_system_prompt(
        book_title=project["book_title"],
        premise=project.get("premise", ""),
        genre=project.get("genre", ""),
        language=resolved_language,
        finalized_chapters=finalized_chapters,
    )
    llm_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    llm_messages.extend({"role": turn["role"], "content": turn["content"]} for turn in updated_history)

    reply = "".join(chunk for chunk in summarizer.stream_with_messages(llm_messages) if chunk)

    assistant_turn = {
        "role": "assistant",
        "content": reply,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    save_studio_conversation(
        settings.output_dir,
        slug=slug,
        messages=updated_history + [assistant_turn],
    )
    return {
        "slug": slug,
        "reply": reply,
        "chapter_count": detail["chapter_count"],
        "language": resolved_language,
    }


def finalize_chapter(
    slug: str,
    *,
    chapter_index: int,
    chapter_title: str,
    content: str,
) -> dict[str, Any]:
    settings = get_settings()
    clean_title = (chapter_title or "").strip()
    if not clean_title:
        raise ValueError("챕터 제목을 입력해 주세요.")
    clean_content = (content or "").strip()
    if not clean_content:
        raise ValueError("챕터 내용을 입력해 주세요.")

    project = read_studio_project(settings.output_dir, slug=slug)
    chapter = ChapterSummary(
        chapter_index=int(chapter_index),
        chapter_title=clean_title,
        summary=clean_content,
        key_events=[],
        character_events=[],
        character_traits=[],
    )
    chapter_path = save_chapter_summary(
        project["book_title"], chapter, root_dir=settings.output_dir
    )
    detail = read_book_detail(settings.output_dir, slug=slug)
    return {
        "slug": slug,
        "chapter_index": int(chapter_index),
        "chapter_title": clean_title,
        "file_name": chapter_path.name,
        "chapter_count": detail["chapter_count"],
    }


def get_bible_state(slug: str) -> dict[str, Any]:
    settings = get_settings()
    bible = read_bible(settings.output_dir, slug=slug)
    messages = read_bible_conversation(settings.output_dir, slug=slug)
    return {
        "slug": slug,
        "setting_markdown": bible["setting_markdown"],
        "characters": bible["characters"],
        "messages": messages,
    }


def parse_bible_characters(text: str) -> list[dict[str, Any]]:
    characters: list[dict[str, Any]] = []
    for block in _BIBLE_CHARACTER_BLOCK_RE.split(text or ""):
        block = block.strip()
        if not block:
            continue
        name = (block.split("\n")[0] or "").strip() or "이름없음"
        characters.append({"name": name, "markdown": f"## {block}"})
    return characters


def save_bible_state(
    slug: str,
    *,
    setting_markdown: str | None = None,
    characters_markdown: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    current = read_bible(settings.output_dir, slug=slug)
    resolved_setting = current["setting_markdown"] if setting_markdown is None else setting_markdown
    resolved_characters = (
        current["characters"]
        if characters_markdown is None
        else parse_bible_characters(characters_markdown)
    )
    save_bible(
        settings.output_dir,
        slug=slug,
        setting_markdown=resolved_setting,
        characters=resolved_characters,
    )
    return get_bible_state(slug)


def bible_chat(
    slug: str,
    message: str,
    *,
    container_type: str = "book",
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    clean_message = (message or "").strip()
    if not clean_message:
        raise ValueError("메시지를 입력해 주세요.")

    resolved_container = (container_type or "book").strip().lower()
    if resolved_container not in {"book", "series"}:
        raise ValueError("container_type은 book 또는 series만 가능합니다.")

    if resolved_container == "series":
        meta = read_series(settings.output_dir, slug=slug)
        title = meta["series_title"]
    else:
        meta = read_studio_project(settings.output_dir, slug=slug)
        title = meta["book_title"]

    bible = read_bible(settings.output_dir, slug=slug)
    history = read_bible_conversation(settings.output_dir, slug=slug)
    summarizer = build_summarizer(provider=provider, api_key=api_key, model=model)
    resolved_language = (language or meta.get("language") or "ko").strip() or "ko"

    now = datetime.now(tz=timezone.utc).isoformat()
    user_turn = {"role": "user", "content": clean_message, "created_at": now}
    updated_history = history + [user_turn]
    save_bible_conversation(settings.output_dir, slug=slug, messages=updated_history)

    system_prompt = build_studio_bible_prompt(
        title=title,
        premise=meta.get("premise", ""),
        genre=meta.get("genre", ""),
        language=resolved_language,
        existing_setting=bible["setting_markdown"],
        existing_characters=bible["characters"],
    )
    llm_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    llm_messages.extend({"role": turn["role"], "content": turn["content"]} for turn in updated_history)

    reply = "".join(chunk for chunk in summarizer.stream_with_messages(llm_messages) if chunk)

    assistant_turn = {
        "role": "assistant",
        "content": reply,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    save_bible_conversation(
        settings.output_dir,
        slug=slug,
        messages=updated_history + [assistant_turn],
    )
    return {
        "slug": slug,
        "container_type": resolved_container,
        "reply": reply,
        "language": resolved_language,
    }


def list_uploads(*, active_only: bool = False) -> list[dict[str, Any]]:
    return list_upload_progress(active_only=active_only)


def summarize_from_temp_path(
    temp_path: str,
    original_filename: str,
    summarizer: MultiProviderBookSummarizer,
    chapter_limit: int | None,
    chapter_parallel: int,
    language: str,
    precise_analysis: bool,
    output_dir: str,
    upload_id: str | None,
) -> BookSummary:
    book = parse_epub(temp_path)
    logger.info(
        "[업로드 파싱 완료] file='%s' title='%s' chapters=%d",
        original_filename,
        book.title,
        len(book.chapters),
    )
    if upload_id:
        update_upload_progress(
            upload_id,
            status="processing",
            progress=6,
            stage="parse",
            message="EPUB 메타데이터/챕터 파싱 완료",
            book_title=book.title,
            chapter_total=len(book.chapters),
        )

    ensure_book_directories(book.title, root_dir=output_dir)
    saved_epub = save_uploaded_epub(
        book.title,
        source_file_path=temp_path,
        original_filename=original_filename,
        root_dir=output_dir,
    )
    logger.info(
        "[원본 EPUB 저장] file='%s' path='%s'",
        original_filename,
        saved_epub,
    )
    if upload_id:
        update_upload_progress(
            upload_id,
            status="processing",
            progress=7,
            stage="saving",
            message="원본 EPUB 저장 완료",
            book_title=book.title,
        )

    original_chapter_count = len(book.chapters)
    if chapter_limit is not None and chapter_limit > 0:
        book.chapters = book.chapters[:chapter_limit]
        if original_chapter_count != len(book.chapters):
            logger.info(
                "[챕터 제한 적용] title='%s' %d -> %d",
                book.title,
                original_chapter_count,
                len(book.chapters),
            )
    if upload_id:
        update_upload_progress(
            upload_id,
            status="processing",
            progress=8,
            stage="chapter",
            message="요약 준비 완료" if not precise_analysis else "정밀 분석 요약 준비 완료",
            chapter_total=len(book.chapters),
            book_title=book.title,
        )

    previous_digest_map = load_chapter_digest_index(book.title, root_dir=output_dir)
    previous_summary_map = read_saved_chapter_summaries(book.title, root_dir=output_dir)
    previous_summary_by_digest: dict[str, ChapterSummary] = {}
    for index, digest in previous_digest_map.items():
        chapter_summary = previous_summary_map.get(index)
        if chapter_summary and digest and digest not in previous_summary_by_digest:
            previous_summary_by_digest[digest] = chapter_summary

    digest_map: dict[int, str] = {}
    reusable_summary_map: dict[int, ChapterSummary] = {}
    refresh_indexes: set[int] = set()
    for chapter in book.chapters:
        digest = compute_chapter_digest(chapter_title=chapter.title, chapter_text=chapter.text)
        digest_map[chapter.index] = digest

        reusable = None
        if previous_digest_map.get(chapter.index) == digest:
            reusable = previous_summary_map.get(chapter.index)
        if reusable is None:
            reusable = previous_summary_by_digest.get(digest)
        if reusable is None and chapter.index not in previous_digest_map:
            existing_by_index = previous_summary_map.get(chapter.index)
            if (
                existing_by_index
                and normalize_title_for_compare(existing_by_index.chapter_title)
                == normalize_title_for_compare(chapter.title)
            ):
                reusable = existing_by_index

        if reusable is None:
            refresh_indexes.add(chapter.index)
            continue

        if reusable.chapter_index != chapter.index or reusable.chapter_title != chapter.title:
            reusable = reusable.model_copy(
                update={
                    "chapter_index": chapter.index,
                    "chapter_title": chapter.title,
                }
            )
        reusable_summary_map[chapter.index] = reusable

    logger.info(
        "[증분 판정] title='%s' total=%d refresh=%d reuse=%d",
        book.title,
        len(book.chapters),
        len(refresh_indexes),
        len(reusable_summary_map),
    )
    digest_index_in_progress = dict(previous_digest_map)

    def on_progress(payload: dict[str, Any]) -> None:
        if not upload_id:
            return
        update_upload_progress(
            upload_id,
            book_title=book.title,
            **payload,
        )

    def on_chapter_summary(chapter_summary: ChapterSummary) -> None:
        chapter_digest = digest_map.get(chapter_summary.chapter_index, "")
        if chapter_digest:
            digest_index_in_progress[chapter_summary.chapter_index] = chapter_digest
            save_chapter_digest_index(
                book.title,
                digest_index_in_progress,
                root_dir=output_dir,
            )
        chapter_path = save_chapter_summary(
            book.title,
            chapter_summary,
            root_dir=output_dir,
        )
        logger.info(
            "[챕터 파일 즉시 저장] title='%s' chapter=%d path='%s'",
            book.title,
            chapter_summary.chapter_index,
            chapter_path,
        )

    summary = summarizer.summarize_incremental(
        book,
        existing_chapter_summaries=reusable_summary_map,
        chapters_to_refresh=refresh_indexes,
        language=language,
        precise_analysis=precise_analysis,
        progress_callback=on_progress,
        chapter_callback=on_chapter_summary,
        chapter_parallel=chapter_parallel,
    )
    if upload_id:
        update_upload_progress(
            upload_id,
            status="processing",
            progress=99,
            stage="saving",
            message="요약 Markdown 저장 중",
            book_title=summary.book_title,
        )
    saved_dir = save_book_summary(summary, root_dir=output_dir)
    prune_chapter_files(summary.book_title, summary.chapter_summaries, root_dir=output_dir)
    save_chapter_digest_index(summary.book_title, digest_map, root_dir=output_dir)
    logger.info(
        "[업로드 완료] file='%s' title='%s' saved_dir='%s'",
        original_filename,
        summary.book_title,
        saved_dir,
    )
    if upload_id:
        complete_upload_progress(upload_id, message="요약 완료")
        update_upload_progress(upload_id, book_title=summary.book_title)
    return summary
