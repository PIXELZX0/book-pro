import logging
import asyncio
import json
import os
import tempfile
from typing import Any
from datetime import datetime, timezone
from pathlib import Path

from fastapi.concurrency import run_in_threadpool
from fastapi import FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app import service
from app.audiobook import AudiobookGenerator
from app.config import get_settings
from app.epub_parser import parse_epub
from app.mcp_server import MountPathRewriteMiddleware, build_mcp_app, mcp_mount_path
from app.progress import (
    TERMINAL_EVENTS,
    fail_upload_progress,
    get_upload_progress,
    has_upload_events,
    init_upload_progress,
    list_upload_events,
    list_upload_progress,
    update_upload_progress,
)
from app.schemas import (
    BookDetailResponse,
    AudioScriptLine,
    AudiobookCreateRequest,
    AudiobookCreateResponse,
    BookReaderProgressRequest,
    BookReaderProgressResponse,
    BookUploadResponse,
    BookAskRequest,
    BookAskResponse,
    BookListResponse,
    BookReaderResponse,
    BookSummary,
    ChapterSummary,
    ChatScriptChapter,
    ChatScriptCreateRequest,
    ChatScriptResponse,
    MultiSummarizeError,
    MultiSummarizeResponse,
    ProviderModelsResponse,
    StudioBibleFinalizeRequest,
    StudioBibleResponse,
    StudioChapterFinalizeRequest,
    StudioChapterFinalizeResponse,
    StudioMessageRequest,
    StudioProjectCreateRequest,
    StudioProjectDetailResponse,
    StudioProjectResponse,
    StudioSeriesCreateRequest,
    StudioSeriesResponse,
    StudioVolumeCreateRequest,
    SummarizeResponse,
    UploadProgressResponse,
)
from app.prompts import build_studio_bible_prompt, build_studio_system_prompt
from app.provider_models import fetch_provider_models
from app.storage import (
    ensure_book_directories,
    extract_section,
    get_latest_epub_path,
    list_books,
    list_series,
    list_series_volumes,
    read_bible,
    read_bible_conversation,
    read_book_detail,
    read_book_reader,
    read_book_reader_progress,
    read_book_summary_snapshot,
    read_series,
    read_studio_conversation,
    read_studio_project,
    save_bible,
    save_bible_conversation,
    save_book_reader_progress,
    save_chapter_summary,
    save_series,
    save_studio_conversation,
    save_studio_project,
    save_uploaded_epub,
)
from app.summarizer import MultiProviderBookSummarizer, normalize_provider
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
SKILL_DOC_PATH = BASE_DIR / "SKILL.md"
logger = logging.getLogger("uvicorn.error")
DEFAULT_MULTI_SUMMARY_PARALLEL = 3
MAX_CHAPTER_SUMMARY_PARALLEL = 8
_UPLOAD_STREAM_POLL_INTERVAL = 0.4
_UPLOAD_STREAM_HEARTBEAT = 10.0
_UPLOAD_STREAM_WAIT_TIMEOUT = 30.0
_UPLOAD_STREAM_IDLE_TIMEOUT = 900.0


def _sse_message(event: dict[str, Any]) -> str:
    payload = json.dumps(
        {"seq": event["seq"], "at": event["at"], **event["data"]},
        ensure_ascii=False,
    )
    return f"id: {event['seq']}\nevent: {event['event']}\ndata: {payload}\n\n"

_build_summarizer = service.build_summarizer
_normalize_error_message = service.normalize_error_message
_resolve_chapter_parallel = service.resolve_chapter_parallel
_is_local_tts_base_url = service.is_local_tts_base_url
_resolve_tts_api_key = service.resolve_tts_api_key
_summarize_from_temp_path = service.summarize_from_temp_path

_mcp_app = build_mcp_app()

app = FastAPI(
    title="book-pro",
    description="EPUB 소설/서사의 챕터/캐릭터/세계관 요약 생성 API",
    version="0.3.0",
    lifespan=_mcp_app.lifespan if _mcp_app is not None else None,
)

if (WEB_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

if _mcp_app is not None:
    app.add_middleware(MountPathRewriteMiddleware, path=mcp_mount_path())
    app.mount(mcp_mount_path(), _mcp_app)


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/panel")


@app.get("/panel")
def panel() -> FileResponse:
    panel_path = WEB_DIR / "index.html"
    if not panel_path.exists():
        raise HTTPException(status_code=404, detail="웹 패널 파일이 없습니다.")
    return FileResponse(str(panel_path))


@app.get("/studio")
def studio_page() -> FileResponse:
    studio_path = WEB_DIR / "studio.html"
    if not studio_path.exists():
        raise HTTPException(status_code=404, detail="스튜디오 페이지 파일이 없습니다.")
    return FileResponse(str(studio_path))


@app.get("/skill.md")
def skill_markdown() -> FileResponse:
    if not SKILL_DOC_PATH.exists():
        raise HTTPException(status_code=404, detail="SKILL.md 파일이 없습니다.")
    return FileResponse(str(SKILL_DOC_PATH), media_type="text/markdown; charset=utf-8")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/providers/models", response_model=ProviderModelsResponse)
def get_provider_models(
    provider: str = Form(...),
    api_key: str | None = Form(default=None),
) -> ProviderModelsResponse:
    settings = get_settings()

    try:
        normalized = normalize_provider(provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    resolved_key = (api_key or "").strip()
    if not resolved_key and normalized == normalize_provider(settings.default_provider):
        resolved_key = settings.openai_api_key

    try:
        models = fetch_provider_models(normalized, api_key=resolved_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ProviderModelsResponse(provider=normalized, models=models)


async def _summarize_upload(
    file: UploadFile,
    *,
    summarizer: MultiProviderBookSummarizer,
    chapter_limit: int | None,
    chapter_parallel: int,
    language: str,
    precise_analysis: bool,
    output_dir: str,
    upload_id: str | None = None,
) -> BookSummary:
    if not file.filename:
        raise ValueError("파일 이름이 없습니다.")

    if not file.filename.lower().endswith(".epub"):
        raise ValueError(".epub 파일만 업로드할 수 있습니다.")

    upload_key = (upload_id or "").strip() or None
    if upload_key:
        init_upload_progress(upload_key, file_name=file.filename)
        update_upload_progress(
            upload_key,
            status="processing",
            progress=1,
            stage="upload",
            message="업로드 파일 수신 중",
        )

    temp_path: str | None = None
    try:
        logger.info(
            "[업로드 시작] file='%s' provider='%s' model='%s' precise=%s chapter_parallel=%d",
            file.filename,
            summarizer.provider,
            summarizer.model,
            precise_analysis,
            chapter_parallel,
        )
        suffix = Path(file.filename).suffix or ".epub"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            temp_path = tmp.name

        if upload_key:
            update_upload_progress(
                upload_key,
                status="processing",
                progress=4,
                stage="parse",
                message="EPUB 파싱 준비 중",
            )

        summary = await run_in_threadpool(
            _summarize_from_temp_path,
            temp_path,
            file.filename,
            summarizer,
            chapter_limit,
            chapter_parallel,
            language,
            precise_analysis,
            output_dir,
            upload_key,
        )
        return summary
    except Exception as exc:  # noqa: BLE001
        logger.exception("[업로드 실패] file='%s'", file.filename)
        if upload_key:
            fail_upload_progress(upload_key, error=_normalize_error_message(exc))
        raise
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/summaries/from-epub", response_model=SummarizeResponse)
async def summarize_from_epub(
    file: UploadFile = File(..., description="요약할 EPUB 파일"),
    upload_id: str | None = Form(default=None),
    provider: str | None = Form(default=None),
    api_key: str | None = Form(default=None),
    model: str | None = Form(default=None),
    language: str = Form(default="ko"),
    precise_analysis: bool = Form(default=False),
    max_chapters: int | None = Form(default=None),
    chapter_parallel: int | None = Form(default=None),
) -> SummarizeResponse:
    settings = get_settings()
    chapter_limit = (
        max_chapters
        if max_chapters is not None
        else settings.max_chapters_per_request
    )
    if chapter_limit is not None and chapter_limit <= 0:
        chapter_limit = None
    resolved_chapter_parallel = _resolve_chapter_parallel(chapter_parallel, settings.chapter_parallel)

    try:
        logger.info(
            "[요청 시작] /summaries/from-epub file='%s' precise=%s chapter_parallel=%d",
            file.filename or "unknown.epub",
            precise_analysis,
            resolved_chapter_parallel,
        )
        summarizer = _build_summarizer(provider=provider, api_key=api_key, model=model)
        summary = await _summarize_upload(
            file,
            summarizer=summarizer,
            chapter_limit=chapter_limit,
            chapter_parallel=resolved_chapter_parallel,
            language=language,
            precise_analysis=precise_analysis,
            output_dir=settings.output_dir,
            upload_id=upload_id,
        )
        logger.info(
            "[요청 완료] /summaries/from-epub title='%s'",
            summary.book_title,
        )
        return SummarizeResponse(data=summary)
    except ValueError as exc:
        logger.warning("[요청 오류] /summaries/from-epub error='%s'", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("[요청 실패] /summaries/from-epub")
        normalized_error = _normalize_error_message(exc)
        status_code = 400 if "API key" in normalized_error else 500
        raise HTTPException(
            status_code=status_code,
            detail=f"요약 생성 중 오류가 발생했습니다: {normalized_error}",
        ) from exc


@app.post("/books/upload-epub", response_model=BookUploadResponse)
async def upload_epub_only(
    file: UploadFile = File(..., description="저장할 EPUB 파일"),
) -> BookUploadResponse:
    settings = get_settings()

    if not file.filename:
        raise HTTPException(status_code=400, detail="파일 이름이 없습니다.")
    if not file.filename.lower().endswith(".epub"):
        raise HTTPException(status_code=400, detail=".epub 파일만 업로드할 수 있습니다.")

    temp_path: str | None = None
    try:
        logger.info("[요청 시작] /books/upload-epub file='%s'", file.filename)
        suffix = Path(file.filename).suffix or ".epub"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            temp_path = tmp.name

        book = await run_in_threadpool(parse_epub, temp_path)
        saved_epub = save_uploaded_epub(
            book.title,
            source_file_path=temp_path,
            original_filename=file.filename,
            root_dir=settings.output_dir,
        )
        book_dir = ensure_book_directories(book.title, root_dir=settings.output_dir)
        logger.info(
            "[요청 완료] /books/upload-epub title='%s' slug='%s' path='%s'",
            book.title,
            book_dir.name,
            saved_epub,
        )
        return BookUploadResponse(
            slug=book_dir.name,
            book_title=book.title,
            chapter_count=len(book.chapters),
            epub_path=str(saved_epub),
        )
    except ValueError as exc:
        logger.warning("[요청 오류] /books/upload-epub error='%s'", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("[요청 실패] /books/upload-epub")
        raise HTTPException(status_code=500, detail=f"EPUB 업로드 중 오류가 발생했습니다: {exc}") from exc
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/books/{book_slug}/summaries", response_model=SummarizeResponse)
async def summarize_existing_book(
    book_slug: str,
    upload_id: str | None = Form(default=None),
    provider: str | None = Form(default=None),
    api_key: str | None = Form(default=None),
    model: str | None = Form(default=None),
    language: str = Form(default="ko"),
    precise_analysis: bool = Form(default=False),
    max_chapters: int | None = Form(default=None),
    chapter_parallel: int | None = Form(default=None),
) -> SummarizeResponse:
    settings = get_settings()
    chapter_limit = (
        max_chapters
        if max_chapters is not None
        else settings.max_chapters_per_request
    )
    if chapter_limit is not None and chapter_limit <= 0:
        chapter_limit = None
    resolved_chapter_parallel = _resolve_chapter_parallel(chapter_parallel, settings.chapter_parallel)

    try:
        epub_path = get_latest_epub_path(settings.output_dir, slug=book_slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    upload_key = (upload_id or "").strip() or None
    if upload_key:
        init_upload_progress(upload_key, file_name=epub_path.name)
        update_upload_progress(
            upload_key,
            status="processing",
            progress=1,
            stage="start",
            message="요약 시작",
        )

    temp_path: str | None = None
    try:
        logger.info(
            "[요청 시작] /books/%s/summaries file='%s' precise=%s chapter_parallel=%d",
            book_slug,
            epub_path.name,
            precise_analysis,
            resolved_chapter_parallel,
        )
        summarizer = _build_summarizer(provider=provider, api_key=api_key, model=model)

        suffix = epub_path.suffix or ".epub"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(epub_path.read_bytes())
            temp_path = tmp.name

        summary = await run_in_threadpool(
            _summarize_from_temp_path,
            temp_path,
            epub_path.name,
            summarizer,
            chapter_limit,
            resolved_chapter_parallel,
            language,
            precise_analysis,
            settings.output_dir,
            upload_key,
        )
        logger.info(
            "[요청 완료] /books/%s/summaries title='%s'",
            book_slug,
            summary.book_title,
        )
        return SummarizeResponse(data=summary)
    except ValueError as exc:
        logger.warning("[요청 오류] /books/%s/summaries error='%s'", book_slug, exc)
        if upload_key:
            fail_upload_progress(upload_key, error=_normalize_error_message(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("[요청 실패] /books/%s/summaries", book_slug)
        normalized_error = _normalize_error_message(exc)
        if upload_key:
            fail_upload_progress(upload_key, error=normalized_error)
        status_code = 400 if "API key" in normalized_error else 500
        raise HTTPException(
            status_code=status_code,
            detail=f"요약 생성 중 오류가 발생했습니다: {normalized_error}",
        ) from exc
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/summaries/from-epubs", response_model=MultiSummarizeResponse)
async def summarize_from_epubs(
    files: list[UploadFile] = File(..., description="요약할 EPUB 파일들"),
    provider: str | None = Form(default=None),
    api_key: str | None = Form(default=None),
    model: str | None = Form(default=None),
    language: str = Form(default="ko"),
    precise_analysis: bool = Form(default=False),
    max_chapters: int | None = Form(default=None),
    max_parallel: int | None = Form(default=None),
    chapter_parallel: int | None = Form(default=None),
) -> MultiSummarizeResponse:
    if not files:
        raise HTTPException(status_code=400, detail="최소 1개 이상의 파일이 필요합니다.")

    settings = get_settings()
    chapter_limit = (
        max_chapters
        if max_chapters is not None
        else settings.max_chapters_per_request
    )
    if chapter_limit is not None and chapter_limit <= 0:
        chapter_limit = None
    resolved_chapter_parallel = _resolve_chapter_parallel(chapter_parallel, settings.chapter_parallel)

    try:
        _build_summarizer(provider=provider, api_key=api_key, model=model)
    except ValueError as exc:
        logger.warning("[요청 오류] /summaries/from-epubs error='%s'", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    results: list[BookSummary] = []
    errors: list[MultiSummarizeError] = []
    total_files = len(files)
    parallel = max_parallel or DEFAULT_MULTI_SUMMARY_PARALLEL
    parallel = max(1, min(parallel, total_files))
    logger.info(
        "[배치 요청 시작] /summaries/from-epubs files=%d parallel=%d chapter_parallel=%d precise=%s",
        total_files,
        parallel,
        resolved_chapter_parallel,
        precise_analysis,
    )

    semaphore = asyncio.Semaphore(parallel)

    async def process_file(index: int, file: UploadFile) -> tuple[BookSummary | None, MultiSummarizeError | None]:
        file_name = file.filename or "unknown.epub"
        logger.info("[배치 진행 %d/%d] file='%s' 대기", index, total_files, file_name)
        async with semaphore:
            logger.info("[배치 진행 %d/%d] file='%s' 처리 시작", index, total_files, file_name)
            try:
                summarizer = _build_summarizer(provider=provider, api_key=api_key, model=model)
                summary = await _summarize_upload(
                    file,
                    summarizer=summarizer,
                    chapter_limit=chapter_limit,
                    chapter_parallel=resolved_chapter_parallel,
                    language=language,
                    precise_analysis=precise_analysis,
                    output_dir=settings.output_dir,
                )
                logger.info(
                    "[배치 진행 %d/%d] file='%s' 처리 완료 title='%s'",
                    index,
                    total_files,
                    file_name,
                    summary.book_title,
                )
                return summary, None
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "[배치 진행 %d/%d] file='%s' 처리 실패",
                    index,
                    total_files,
                    file_name,
                )
                return (
                    None,
                    MultiSummarizeError(
                        file_name=file_name,
                        error=_normalize_error_message(exc),
                    ),
                )

    outcomes = await asyncio.gather(
        *(process_file(index, file) for index, file in enumerate(files, start=1))
    )

    for summary, error in outcomes:
        if summary:
            results.append(summary)
        if error:
            errors.append(error)

    logger.info(
        "[배치 요청 완료] /summaries/from-epubs success=%d failure=%d",
        len(results),
        len(errors),
    )
    return MultiSummarizeResponse(
        success_count=len(results),
        failure_count=len(errors),
        data=results,
        errors=errors,
    )


@app.get("/books", response_model=BookListResponse)
def get_books(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
) -> BookListResponse:
    settings = get_settings()
    payload = list_books(settings.output_dir, page=page, page_size=page_size)
    return BookListResponse.model_validate(payload)


@app.get("/books/{book_slug}", response_model=BookDetailResponse)
def get_book_detail(book_slug: str) -> BookDetailResponse:
    settings = get_settings()

    try:
        payload = read_book_detail(settings.output_dir, slug=book_slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return BookDetailResponse.model_validate(payload)


@app.get("/books/{book_slug}/reader", response_model=BookReaderResponse)
def get_book_reader(book_slug: str) -> BookReaderResponse:
    settings = get_settings()

    try:
        payload = read_book_reader(settings.output_dir, slug=book_slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return BookReaderResponse.model_validate(payload)


@app.get("/books/{book_slug}/reader/progress", response_model=BookReaderProgressResponse)
def get_book_reader_progress(book_slug: str) -> BookReaderProgressResponse:
    settings = get_settings()

    try:
        payload = read_book_reader_progress(settings.output_dir, slug=book_slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return BookReaderProgressResponse.model_validate(payload)


@app.put("/books/{book_slug}/reader/progress", response_model=BookReaderProgressResponse)
def put_book_reader_progress(
    book_slug: str,
    payload: BookReaderProgressRequest,
) -> BookReaderProgressResponse:
    settings = get_settings()

    try:
        saved = save_book_reader_progress(
            settings.output_dir,
            slug=book_slug,
            page=payload.page,
            total_pages=payload.total_pages,
            ratio=payload.ratio,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return BookReaderProgressResponse.model_validate(saved)


@app.get("/uploads/{upload_id}/progress", response_model=UploadProgressResponse)
def get_upload_progress_state(upload_id: str) -> UploadProgressResponse:
    payload = get_upload_progress(upload_id)
    if not payload:
        return UploadProgressResponse(
            upload_id=upload_id,
            file_name="",
            book_title="",
            status="queued",
            progress=0,
            stage="queued",
            message="요약 요청 대기 중",
            chapter_index=None,
            chapter_total=None,
            chapter_title=None,
            character_index=None,
            character_total=None,
            character_name=None,
            error="",
            updated_at=datetime.now(tz=timezone.utc).isoformat(),
        )
    return UploadProgressResponse.model_validate(payload)


@app.get("/uploads/{upload_id}/stream")
async def stream_upload_events(
    request: Request,
    upload_id: str,
    last_event_id: str | None = Header(default=None),
) -> StreamingResponse:
    try:
        cursor = max(0, int((last_event_id or "0").strip()))
    except ValueError:
        cursor = 0

    async def _iter_chunks() -> Any:
        nonlocal cursor
        idle_seconds = 0.0
        since_heartbeat = 0.0

        while True:
            if await request.is_disconnected():
                return

            events = list_upload_events(upload_id, after_seq=cursor)
            for event in events:
                cursor = max(cursor, int(event["seq"]))
                idle_seconds = 0.0
                yield _sse_message(event)
                if event["event"] in TERMINAL_EVENTS:
                    return

            if idle_seconds >= _UPLOAD_STREAM_IDLE_TIMEOUT:
                yield _sse_message(
                    {
                        "seq": cursor,
                        "event": "timeout",
                        "data": {"message": "진행 상황 스트림이 종료되었습니다."},
                        "at": datetime.now(tz=timezone.utc).isoformat(),
                    }
                )
                return
            if not has_upload_events(upload_id) and idle_seconds >= _UPLOAD_STREAM_WAIT_TIMEOUT:
                yield _sse_message(
                    {
                        "seq": cursor,
                        "event": "timeout",
                        "data": {"message": "요약 작업을 찾을 수 없습니다."},
                        "at": datetime.now(tz=timezone.utc).isoformat(),
                    }
                )
                return

            await asyncio.sleep(_UPLOAD_STREAM_POLL_INTERVAL)
            idle_seconds += _UPLOAD_STREAM_POLL_INTERVAL
            since_heartbeat += _UPLOAD_STREAM_POLL_INTERVAL
            if since_heartbeat >= _UPLOAD_STREAM_HEARTBEAT:
                since_heartbeat = 0.0
                yield ": ping\n\n"

    return StreamingResponse(
        _iter_chunks(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/uploads/active", response_model=list[UploadProgressResponse])
def list_active_upload_progress() -> list[UploadProgressResponse]:
    rows = list_upload_progress(active_only=True)
    return [UploadProgressResponse.model_validate(row) for row in rows]


@app.post("/books/{book_slug}/ask", response_model=BookAskResponse)
def ask_about_book(book_slug: str, payload: BookAskRequest) -> BookAskResponse:
    settings = get_settings()
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="질문을 입력해 주세요.")

    mode = (payload.mode or "book").strip().lower()
    if mode not in {"book", "character"}:
        raise HTTPException(status_code=400, detail="mode는 book 또는 character만 가능합니다.")

    character_name = (payload.character_name or "").strip() or None
    if mode == "character" and not character_name:
        raise HTTPException(status_code=400, detail="character 모드에서는 character_name이 필요합니다.")

    try:
        snapshot = read_book_summary_snapshot(settings.output_dir, slug=book_slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        summarizer = _build_summarizer(
            provider=payload.provider,
            api_key=payload.api_key,
            model=payload.model,
        )
        answer = summarizer.answer_about_book(
            book_title=snapshot["book_title"],
            chapter_summaries=snapshot["chapter_summaries"],
            character_summaries_text=snapshot["character_summaries_text"],
            setting_markdown=snapshot["setting_markdown"],
            question=question,
            language=(payload.language or "ko").strip() or "ko",
            character_name=character_name if mode == "character" else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        normalized_error = _normalize_error_message(exc)
        status_code = 400 if "API key" in normalized_error else 500
        raise HTTPException(
            status_code=status_code,
            detail=f"질문 처리 중 오류가 발생했습니다: {normalized_error}",
        ) from exc

    return BookAskResponse(
        answer=answer,
        mode=mode,
        book_title=snapshot["book_title"],
        character_name=character_name if mode == "character" else None,
    )


@app.post("/books/{book_slug}/ask/stream")
def ask_about_book_stream(book_slug: str, payload: BookAskRequest) -> StreamingResponse:
    settings = get_settings()
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="질문을 입력해 주세요.")

    mode = (payload.mode or "book").strip().lower()
    if mode not in {"book", "character"}:
        raise HTTPException(status_code=400, detail="mode는 book 또는 character만 가능합니다.")

    character_name = (payload.character_name or "").strip() or None
    if mode == "character" and not character_name:
        raise HTTPException(status_code=400, detail="character 모드에서는 character_name이 필요합니다.")

    try:
        snapshot = read_book_summary_snapshot(settings.output_dir, slug=book_slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        summarizer = _build_summarizer(
            provider=payload.provider,
            api_key=payload.api_key,
            model=payload.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    language = (payload.language or "ko").strip() or "ko"

    def _iter_chunks() -> Any:
        try:
            for chunk in summarizer.answer_about_book_stream(
                book_title=snapshot["book_title"],
                chapter_summaries=snapshot["chapter_summaries"],
                character_summaries_text=snapshot["character_summaries_text"],
                setting_markdown=snapshot["setting_markdown"],
                question=question,
                language=language,
                character_name=character_name if mode == "character" else None,
            ):
                if chunk:
                    yield chunk
        except Exception as exc:  # noqa: BLE001
            normalized_error = _normalize_error_message(exc)
            logger.exception("[스트림 질문 실패] /books/%s/ask/stream", book_slug)
            yield f"\n\n[오류] 질문 처리 중 오류가 발생했습니다: {normalized_error}"

    return StreamingResponse(
        _iter_chunks(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/studio/projects", response_model=StudioProjectResponse)
def create_studio_project(payload: StudioProjectCreateRequest) -> StudioProjectResponse:
    settings = get_settings()
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="제목을 입력해 주세요.")

    try:
        project_path = save_studio_project(
            title,
            premise=(payload.premise or "").strip(),
            genre=(payload.genre or "").strip(),
            language=(payload.language or "ko").strip() or "ko",
            root_dir=settings.output_dir,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    slug = project_path.parent.name
    project = read_studio_project(settings.output_dir, slug=slug)
    return StudioProjectResponse(slug=slug, chapter_count=0, **project)


@app.get("/studio/projects/{slug}", response_model=StudioProjectDetailResponse)
def get_studio_project(slug: str) -> StudioProjectDetailResponse:
    settings = get_settings()
    try:
        project = read_studio_project(settings.output_dir, slug=slug)
        detail = read_book_detail(settings.output_dir, slug=slug)
        messages = read_studio_conversation(settings.output_dir, slug=slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return StudioProjectDetailResponse(
        slug=slug,
        chapter_count=detail["chapter_count"],
        messages=messages,
        **project,
    )


@app.post("/studio/projects/{slug}/messages/stream")
def studio_message_stream(slug: str, payload: StudioMessageRequest) -> StreamingResponse:
    settings = get_settings()
    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="메시지를 입력해 주세요.")

    try:
        project = read_studio_project(settings.output_dir, slug=slug)
        detail = read_book_detail(settings.output_dir, slug=slug)
        history = read_studio_conversation(settings.output_dir, slug=slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        summarizer = _build_summarizer(
            provider=payload.provider,
            api_key=payload.api_key,
            model=payload.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    language = (payload.language or project.get("language") or "ko").strip() or "ko"

    finalized_chapters = [
        {
            "chapter_index": chapter["index"],
            "chapter_title": chapter["title"],
            "summary": extract_section(chapter["markdown"], "요약") or "",
        }
        for chapter in detail["chapters"]
    ]

    now = datetime.now(tz=timezone.utc).isoformat()
    user_turn = {"role": "user", "content": message, "created_at": now}
    updated_history = history + [user_turn]
    save_studio_conversation(settings.output_dir, slug=slug, messages=updated_history)

    system_prompt = build_studio_system_prompt(
        book_title=project["book_title"],
        premise=project.get("premise", ""),
        genre=project.get("genre", ""),
        language=language,
        finalized_chapters=finalized_chapters,
    )
    llm_messages = [{"role": "system", "content": system_prompt}]
    llm_messages.extend({"role": turn["role"], "content": turn["content"]} for turn in updated_history)

    def _iter_chunks() -> Any:
        collected: list[str] = []
        try:
            for chunk in summarizer.stream_with_messages(llm_messages):
                if chunk:
                    collected.append(chunk)
                    yield chunk
        except Exception as exc:  # noqa: BLE001
            normalized_error = _normalize_error_message(exc)
            logger.exception("[스튜디오 스트림 실패] /studio/projects/%s/messages/stream", slug)
            yield f"\n\n[오류] 메시지 처리 중 오류가 발생했습니다: {normalized_error}"
            return

        assistant_turn = {
            "role": "assistant",
            "content": "".join(collected),
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        save_studio_conversation(
            settings.output_dir,
            slug=slug,
            messages=updated_history + [assistant_turn],
        )

    return StreamingResponse(
        _iter_chunks(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post(
    "/studio/projects/{slug}/chapters/finalize",
    response_model=StudioChapterFinalizeResponse,
)
def finalize_studio_chapter(
    slug: str, payload: StudioChapterFinalizeRequest
) -> StudioChapterFinalizeResponse:
    settings = get_settings()
    chapter_title = (payload.chapter_title or "").strip()
    if not chapter_title:
        raise HTTPException(status_code=400, detail="챕터 제목을 입력해 주세요.")
    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="챕터 내용을 입력해 주세요.")

    try:
        project = read_studio_project(settings.output_dir, slug=slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    chapter = ChapterSummary(
        chapter_index=payload.chapter_index,
        chapter_title=chapter_title,
        summary=content,
        key_events=[],
        character_events=[],
        character_traits=[],
    )
    chapter_path = save_chapter_summary(
        project["book_title"], chapter, root_dir=settings.output_dir
    )
    detail = read_book_detail(settings.output_dir, slug=slug)

    return StudioChapterFinalizeResponse(
        chapter_index=payload.chapter_index,
        chapter_title=chapter_title,
        file_name=chapter_path.name,
        chapter_count=detail["chapter_count"],
    )


@app.get("/studio/series", response_model=list[StudioSeriesResponse])
def get_studio_series_list() -> list[StudioSeriesResponse]:
    settings = get_settings()
    return [StudioSeriesResponse.model_validate(item) for item in list_series(settings.output_dir)]


@app.post("/studio/series", response_model=StudioSeriesResponse)
def create_studio_series(payload: StudioSeriesCreateRequest) -> StudioSeriesResponse:
    settings = get_settings()
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="제목을 입력해 주세요.")

    try:
        series_path = save_series(
            title,
            premise=(payload.premise or "").strip(),
            genre=(payload.genre or "").strip(),
            language=(payload.language or "ko").strip() or "ko",
            root_dir=settings.output_dir,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    slug = series_path.parent.name
    series = read_series(settings.output_dir, slug=slug)
    return StudioSeriesResponse(slug=slug, volumes=[], **series)


@app.get("/studio/series/{slug}", response_model=StudioSeriesResponse)
def get_studio_series(slug: str) -> StudioSeriesResponse:
    settings = get_settings()
    try:
        series = read_series(settings.output_dir, slug=slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    volumes = list_series_volumes(settings.output_dir, series_slug=slug)
    return StudioSeriesResponse(slug=slug, volumes=volumes, **series)


@app.post("/studio/series/{slug}/volumes", response_model=StudioProjectResponse)
def create_studio_volume(slug: str, payload: StudioVolumeCreateRequest) -> StudioProjectResponse:
    settings = get_settings()
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="권 제목을 입력해 주세요.")

    try:
        series = read_series(settings.output_dir, slug=slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        project_path = save_studio_project(
            title,
            premise=series.get("premise", ""),
            genre=series.get("genre", ""),
            language=series.get("language", "ko"),
            root_dir=settings.output_dir,
            book_format="long",
            series_slug=slug,
            volume_index=payload.volume_index,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    volume_slug = project_path.parent.name
    bible = read_bible(settings.output_dir, slug=slug)
    if bible["setting_markdown"] or bible["characters"]:
        save_bible(
            settings.output_dir,
            slug=volume_slug,
            setting_markdown=bible["setting_markdown"],
            characters=bible["characters"],
        )

    project = read_studio_project(settings.output_dir, slug=volume_slug)
    return StudioProjectResponse(slug=volume_slug, chapter_count=0, **project)


def _get_bible_response(slug: str) -> StudioBibleResponse:
    settings = get_settings()
    bible = read_bible(settings.output_dir, slug=slug)
    messages = read_bible_conversation(settings.output_dir, slug=slug)
    return StudioBibleResponse(
        setting_markdown=bible["setting_markdown"],
        characters=bible["characters"],
        messages=messages,
    )


def _finalize_bible(slug: str, payload: StudioBibleFinalizeRequest) -> StudioBibleResponse:
    settings = get_settings()
    save_bible(
        settings.output_dir,
        slug=slug,
        setting_markdown=payload.setting_markdown,
        characters=[character.model_dump() for character in payload.characters],
    )
    return _get_bible_response(slug)


def _stream_bible_messages(
    *,
    slug: str,
    payload: StudioMessageRequest,
    title: str,
    premise: str,
    genre: str,
) -> StreamingResponse:
    settings = get_settings()
    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="메시지를 입력해 주세요.")

    try:
        bible = read_bible(settings.output_dir, slug=slug)
        history = read_bible_conversation(settings.output_dir, slug=slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        summarizer = _build_summarizer(
            provider=payload.provider,
            api_key=payload.api_key,
            model=payload.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    language = (payload.language or "ko").strip() or "ko"

    now = datetime.now(tz=timezone.utc).isoformat()
    user_turn = {"role": "user", "content": message, "created_at": now}
    updated_history = history + [user_turn]
    save_bible_conversation(settings.output_dir, slug=slug, messages=updated_history)

    system_prompt = build_studio_bible_prompt(
        title=title,
        premise=premise,
        genre=genre,
        language=language,
        existing_setting=bible["setting_markdown"],
        existing_characters=bible["characters"],
    )
    llm_messages = [{"role": "system", "content": system_prompt}]
    llm_messages.extend({"role": turn["role"], "content": turn["content"]} for turn in updated_history)

    def _iter_chunks() -> Any:
        collected: list[str] = []
        try:
            for chunk in summarizer.stream_with_messages(llm_messages):
                if chunk:
                    collected.append(chunk)
                    yield chunk
        except Exception as exc:  # noqa: BLE001
            normalized_error = _normalize_error_message(exc)
            logger.exception("[설정집 스트림 실패] slug=%s", slug)
            yield f"\n\n[오류] 메시지 처리 중 오류가 발생했습니다: {normalized_error}"
            return

        assistant_turn = {
            "role": "assistant",
            "content": "".join(collected),
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        save_bible_conversation(
            settings.output_dir,
            slug=slug,
            messages=updated_history + [assistant_turn],
        )

    return StreamingResponse(
        _iter_chunks(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/studio/projects/{slug}/bible", response_model=StudioBibleResponse)
def get_studio_book_bible(slug: str) -> StudioBibleResponse:
    settings = get_settings()
    try:
        read_studio_project(settings.output_dir, slug=slug)
        return _get_bible_response(slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/studio/projects/{slug}/bible/finalize", response_model=StudioBibleResponse)
def finalize_studio_book_bible(slug: str, payload: StudioBibleFinalizeRequest) -> StudioBibleResponse:
    settings = get_settings()
    try:
        read_studio_project(settings.output_dir, slug=slug)
        return _finalize_bible(slug, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/studio/projects/{slug}/bible/messages/stream")
def studio_book_bible_stream(slug: str, payload: StudioMessageRequest) -> StreamingResponse:
    settings = get_settings()
    try:
        project = read_studio_project(settings.output_dir, slug=slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _stream_bible_messages(
        slug=slug,
        payload=payload,
        title=project["book_title"],
        premise=project.get("premise", ""),
        genre=project.get("genre", ""),
    )


@app.get("/studio/series/{slug}/bible", response_model=StudioBibleResponse)
def get_studio_series_bible(slug: str) -> StudioBibleResponse:
    settings = get_settings()
    try:
        read_series(settings.output_dir, slug=slug)
        return _get_bible_response(slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/studio/series/{slug}/bible/finalize", response_model=StudioBibleResponse)
def finalize_studio_series_bible(slug: str, payload: StudioBibleFinalizeRequest) -> StudioBibleResponse:
    settings = get_settings()
    try:
        read_series(settings.output_dir, slug=slug)
        return _finalize_bible(slug, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/studio/series/{slug}/bible/messages/stream")
def studio_series_bible_stream(slug: str, payload: StudioMessageRequest) -> StreamingResponse:
    settings = get_settings()
    try:
        series = read_series(settings.output_dir, slug=slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _stream_bible_messages(
        slug=slug,
        payload=payload,
        title=series["series_title"],
        premise=series.get("premise", ""),
        genre=series.get("genre", ""),
    )


@app.post("/books/{book_slug}/audiobook", response_model=AudiobookCreateResponse)
def create_audiobook(book_slug: str, payload: AudiobookCreateRequest) -> AudiobookCreateResponse:
    settings = get_settings()

    try:
        snapshot = read_book_summary_snapshot(settings.output_dir, slug=book_slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        llm_summarizer = _build_summarizer(
            provider=payload.provider,
            api_key=payload.api_key,
            model=payload.model,
        )

        tts_base_url = (payload.tts_base_url or "").strip() or settings.qwen_tts_base_url
        tts_model = (payload.tts_model or "").strip() or settings.qwen_tts_model
        tts_api_key = _resolve_tts_api_key(
            payload_tts_api_key=payload.tts_api_key,
            default_tts_api_key=settings.qwen_tts_api_key,
            tts_base_url=tts_base_url,
        )

        tts_client = OpenAI(api_key=tts_api_key, base_url=tts_base_url)
        generator = AudiobookGenerator(
            llm_client=llm_summarizer.client,
            llm_model=llm_summarizer.model,
            tts_client=tts_client,
            tts_model=tts_model,
            tts_base_url=tts_base_url,
            tts_api_key=tts_api_key,
        )

        script_bundle = generator.generate_chapter_scripts(
            book_title=snapshot["book_title"],
            chapter_summaries=snapshot["chapter_summaries"],
            character_summaries_text=snapshot["character_summaries_text"],
            language=payload.language,
            target_minutes=payload.target_minutes,
        )

        output_dir = Path(settings.output_dir) / book_slug / "audiobook"
        synthesis = generator.synthesize(
            script_bundle=script_bundle,
            out_dir=output_dir,
            book_title=snapshot["book_title"],
            language=payload.language,
            narrator_voice=payload.narrator_voice,
            character_voices=payload.character_voices,
            character_summaries_text=snapshot["character_summaries_text"],
            character_voice_prompts=payload.character_voice_prompts,
            enable_voice_design=payload.enable_voice_design,
            enable_base_voice_clone=payload.enable_base_voice_clone,
            voice_design_model=payload.voice_design_model,
            voice_clone_model=payload.voice_clone_model,
            voice_target_model=(payload.voice_target_model or "").strip() or tts_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("[오디오북 생성 실패] slug='%s'", book_slug)
        raise HTTPException(status_code=500, detail=f"오디오북 생성 중 오류: {exc}") from exc

    return AudiobookCreateResponse(
        book_slug=book_slug,
        book_title=snapshot["book_title"],
        script_path=str(synthesis.script_bundle_path),
        script_bundle_path=str(synthesis.script_bundle_path),
        chapter_script_dir=str(synthesis.chapter_script_dir),
        audio_dir=str(synthesis.segment_dir),
        chapter_audio_dir=str(synthesis.chapter_audio_dir),
        voice_profile_path=str(synthesis.voice_profile_path),
        final_audio_path=str(synthesis.final_audio_path),
        line_count=synthesis.line_count,
        chapter_count=synthesis.chapter_count,
        voice_count=synthesis.voice_count,
    )


@app.post("/books/{book_slug}/chat-script", response_model=ChatScriptResponse)
def create_chat_script(book_slug: str, payload: ChatScriptCreateRequest) -> ChatScriptResponse:
    settings = get_settings()

    try:
        snapshot = read_book_summary_snapshot(settings.output_dir, slug=book_slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        llm_summarizer = _build_summarizer(
            provider=payload.provider,
            api_key=payload.api_key,
            model=payload.model,
        )
        generator = AudiobookGenerator(
            llm_client=llm_summarizer.client,
            llm_model=llm_summarizer.model,
        )
        script_bundle = generator.generate_chapter_scripts(
            book_title=snapshot["book_title"],
            chapter_summaries=snapshot["chapter_summaries"],
            character_summaries_text=snapshot["character_summaries_text"],
            language=payload.language,
            target_minutes=payload.target_minutes,
        )

        output_dir = Path(settings.output_dir) / book_slug / "chat"
        output_dir.mkdir(parents=True, exist_ok=True)
        script_path = output_dir / "script.json"
        script_path.write_text(script_bundle.model_dump_json(indent=2), encoding="utf-8")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("[채팅형 변환 실패] slug='%s'", book_slug)
        raise HTTPException(status_code=500, detail=f"채팅형 변환 중 오류: {exc}") from exc

    return ChatScriptResponse(
        book_slug=book_slug,
        book_title=snapshot["book_title"],
        script_path=str(script_path),
        chapter_count=len(script_bundle.chapters),
        line_count=sum(len(chapter.lines) for chapter in script_bundle.chapters),
        chapters=[
            ChatScriptChapter(
                chapter_index=chapter.chapter_index,
                chapter_title=chapter.chapter_title,
                lines=chapter.lines,
            )
            for chapter in script_bundle.chapters
        ],
    )


@app.get("/books/{book_slug}/chat-script", response_model=ChatScriptResponse)
def get_chat_script(book_slug: str) -> ChatScriptResponse:
    settings = get_settings()

    try:
        snapshot = read_book_summary_snapshot(settings.output_dir, slug=book_slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    script_path = Path(settings.output_dir) / book_slug / "chat" / "script.json"
    if not script_path.exists():
        raise HTTPException(status_code=404, detail="채팅형 대본이 아직 생성되지 않았습니다.")

    try:
        payload = json.loads(script_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail="채팅형 대본을 읽을 수 없습니다.") from exc

    chapters = [
        ChatScriptChapter(
            chapter_index=chapter.get("chapter_index", 0),
            chapter_title=chapter.get("chapter_title", ""),
            lines=[AudioScriptLine(**line) for line in chapter.get("lines", [])],
        )
        for chapter in payload.get("chapters", [])
    ]
    return ChatScriptResponse(
        book_slug=book_slug,
        book_title=snapshot["book_title"],
        script_path=str(script_path),
        chapter_count=len(chapters),
        line_count=sum(len(chapter.lines) for chapter in chapters),
        chapters=chapters,
    )
