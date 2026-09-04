import logging
import asyncio
import json
import os
import tempfile
from typing import Any
from datetime import datetime, timezone
from pathlib import Path

from fastapi.concurrency import run_in_threadpool
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app import service
from app.audiobook import AudiobookGenerator
from app.config import get_settings
from app.epub_parser import parse_epub
from app.mcp_server import MountPathRewriteMiddleware, build_mcp_app, mcp_mount_path
from app.progress import (
    fail_upload_progress,
    get_upload_progress,
    init_upload_progress,
    list_upload_progress,
    update_upload_progress,
)
from app.schemas import (
    BookDetailResponse,
    AudioScriptLine,
    AudiobookCreateRequest,
    AudiobookCreateResponse,
    BookChapterFile,
    BookReaderProgressRequest,
    BookReaderProgressResponse,
    BookUploadResponse,
    BookAskRequest,
    BookAskResponse,
    BookListResponse,
    BookReaderResponse,
    BookSummary,
    ChatScriptChapter,
    ChatScriptCreateRequest,
    ChatScriptResponse,
    MultiSummarizeError,
    MultiSummarizeResponse,
    ProviderModelsResponse,
    StudioBibleFinalizeRequest,
    StudioBibleResponse,
    StudioActionResponse,
    StudioAgentRequest,
    StudioChapterDeleteResponse,
    StudioChapterFinalizeRequest,
    StudioChapterFinalizeResponse,
    StudioChapterListResponse,
    StudioChatResponse,
    StudioDeleteResponse,
    StudioHistoryItem,
    StudioHistoryRestoreRequest,
    StudioHistoryRestoreResponse,
    StudioMessageRequest,
    StudioPendingAction,
    StudioProjectCreateRequest,
    StudioProjectDetailResponse,
    StudioProjectResponse,
    StudioProjectUpdateRequest,
    StudioSeriesCreateRequest,
    StudioSeriesResponse,
    StudioVolumeCreateRequest,
    SummarizeResponse,
    UploadProgressResponse,
)
from app.provider_models import fetch_provider_models
from app.studio_agent import iter_agent_events as studio_agent_iter_events
from app.storage import (
    ensure_book_directories,
    get_latest_epub_path,
    list_books,
    read_book_detail,
    read_book_reader,
    read_book_reader_progress,
    read_book_summary_snapshot,
    save_book_reader_progress,
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


def _http_from_studio_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=service.normalize_error_message(exc))


def _studio_stream_response(chunks: Any, *, log_label: str) -> StreamingResponse:
    def _iter_chunks() -> Any:
        try:
            yield from chunks
        except Exception as exc:  # noqa: BLE001
            normalized_error = service.normalize_error_message(exc)
            logger.exception("[스튜디오 스트림 실패] %s", log_label)
            yield f"\n\n[오류] 메시지 처리 중 오류가 발생했습니다: {normalized_error}"

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
    try:
        project = service.create_project(
            payload.title,
            premise=payload.premise,
            genre=payload.genre,
            language=payload.language,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioProjectResponse.model_validate(project)


@app.get("/studio/projects/{slug}", response_model=StudioProjectDetailResponse)
def get_studio_project(slug: str) -> StudioProjectDetailResponse:
    try:
        project = service.get_project(slug)
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioProjectDetailResponse.model_validate(project)


@app.post("/studio/projects/{slug}/messages/stream")
def studio_message_stream(slug: str, payload: StudioMessageRequest) -> StreamingResponse:
    try:
        chunks = service.iter_studio_chat(
            slug,
            payload.message,
            provider=payload.provider,
            api_key=payload.api_key,
            model=payload.model,
            language=payload.language,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return _studio_stream_response(
        chunks, log_label=f"/studio/projects/{slug}/messages/stream"
    )


@app.post(
    "/studio/projects/{slug}/chapters/finalize",
    response_model=StudioChapterFinalizeResponse,
)
def finalize_studio_chapter(
    slug: str, payload: StudioChapterFinalizeRequest
) -> StudioChapterFinalizeResponse:
    try:
        result = service.finalize_chapter(
            slug,
            chapter_index=payload.chapter_index,
            chapter_title=payload.chapter_title,
            content=payload.content,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioChapterFinalizeResponse.model_validate(result)


@app.post("/studio/projects/{slug}/agent/stream")
def studio_agent_stream(slug: str, payload: StudioAgentRequest) -> StreamingResponse:
    try:
        events = studio_agent_iter_events(
            slug,
            payload.message,
            provider=payload.provider,
            api_key=payload.api_key,
            model=payload.model,
            language=payload.language,
            mode=payload.mode,
            max_steps=payload.max_steps,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc

    def _iter_ndjson() -> Any:
        try:
            for event in events:
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as exc:  # noqa: BLE001
            normalized_error = service.normalize_error_message(exc)
            logger.exception("[스튜디오 에이전트 스트림 실패] slug='%s'", slug)
            yield json.dumps(
                {"type": "error", "message": normalized_error}, ensure_ascii=False
            ) + "\n"

    return StreamingResponse(
        _iter_ndjson(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/studio/projects/{slug}/agent/actions", response_model=list[StudioPendingAction])
def list_studio_agent_actions(slug: str) -> list[StudioPendingAction]:
    try:
        actions = service.list_studio_pending_actions(slug)
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return [StudioPendingAction.model_validate(action) for action in actions]


@app.post("/studio/projects/{slug}/agent/actions/{action_id}/apply", response_model=StudioActionResponse)
def apply_studio_agent_action(slug: str, action_id: str) -> StudioActionResponse:
    try:
        result = service.apply_studio_pending_action(slug, action_id)
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioActionResponse.model_validate(result)


@app.post("/studio/projects/{slug}/agent/actions/{action_id}/reject", response_model=StudioActionResponse)
def reject_studio_agent_action(slug: str, action_id: str) -> StudioActionResponse:
    try:
        result = service.reject_studio_pending_action(slug, action_id)
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioActionResponse.model_validate(result)


@app.get("/studio/projects/{slug}/agent/history", response_model=list[StudioHistoryItem])
def list_studio_agent_history(slug: str) -> list[StudioHistoryItem]:
    try:
        entries = service.list_studio_file_history(slug)
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return [StudioHistoryItem.model_validate(entry) for entry in entries]


@app.post(
    "/studio/projects/{slug}/agent/history/restore",
    response_model=StudioHistoryRestoreResponse,
)
def restore_studio_agent_history(
    slug: str, payload: StudioHistoryRestoreRequest
) -> StudioHistoryRestoreResponse:
    try:
        result = service.restore_studio_file_history(slug, payload.entry_id)
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioHistoryRestoreResponse.model_validate(result)


@app.get("/studio/series", response_model=list[StudioSeriesResponse])
def get_studio_series_list() -> list[StudioSeriesResponse]:
    return [
        StudioSeriesResponse.model_validate(item) for item in service.list_studio_series()
    ]


@app.post("/studio/series", response_model=StudioSeriesResponse)
def create_studio_series(payload: StudioSeriesCreateRequest) -> StudioSeriesResponse:
    try:
        series = service.create_series(
            payload.title,
            premise=payload.premise,
            genre=payload.genre,
            language=payload.language,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioSeriesResponse.model_validate(series)


@app.get("/studio/series/{slug}", response_model=StudioSeriesResponse)
def get_studio_series(slug: str) -> StudioSeriesResponse:
    try:
        series = service.get_series(slug)
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioSeriesResponse.model_validate(series)


@app.post("/studio/series/{slug}/volumes", response_model=StudioProjectResponse)
def create_studio_volume(slug: str, payload: StudioVolumeCreateRequest) -> StudioProjectResponse:
    try:
        project = service.add_series_volume(
            slug,
            payload.title,
            volume_index=payload.volume_index,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioProjectResponse.model_validate(project)


@app.get("/studio/projects", response_model=list[StudioProjectResponse])
def get_studio_project_list() -> list[StudioProjectResponse]:
    return [
        StudioProjectResponse.model_validate(item)
        for item in service.list_studio_projects()
    ]


@app.post("/studio/projects/{slug}/messages", response_model=StudioChatResponse)
def studio_message(slug: str, payload: StudioMessageRequest) -> StudioChatResponse:
    try:
        result = service.studio_chat(
            slug,
            payload.message,
            provider=payload.provider,
            api_key=payload.api_key,
            model=payload.model,
            language=payload.language,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioChatResponse.model_validate(result)


@app.patch("/studio/projects/{slug}", response_model=StudioProjectResponse)
def update_studio_project_endpoint(
    slug: str, payload: StudioProjectUpdateRequest
) -> StudioProjectResponse:
    try:
        service.update_project(
            slug,
            premise=payload.premise,
            genre=payload.genre,
            language=payload.language,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioProjectResponse.model_validate(service.get_project(slug))


@app.delete("/studio/projects/{slug}", response_model=StudioDeleteResponse)
def delete_studio_project_endpoint(slug: str) -> StudioDeleteResponse:
    try:
        result = service.delete_project(slug)
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioDeleteResponse.model_validate(result)


@app.get("/studio/projects/{slug}/chapters", response_model=StudioChapterListResponse)
def get_studio_project_chapters(slug: str) -> StudioChapterListResponse:
    try:
        result = service.list_project_chapters(slug)
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioChapterListResponse.model_validate(result)


@app.get("/studio/projects/{slug}/chapters/{chapter_index}", response_model=BookChapterFile)
def get_studio_project_chapter(slug: str, chapter_index: int) -> BookChapterFile:
    try:
        result = service.get_project_chapter(slug, chapter_index)
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return BookChapterFile.model_validate(result)


@app.delete(
    "/studio/projects/{slug}/chapters/{chapter_index}",
    response_model=StudioChapterDeleteResponse,
)
def delete_studio_project_chapter(
    slug: str, chapter_index: int
) -> StudioChapterDeleteResponse:
    try:
        result = service.delete_project_chapter(slug, chapter_index)
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioChapterDeleteResponse.model_validate(result)


@app.get("/studio/projects/{slug}/export")
def export_studio_project_file(
    slug: str,
    format: str = Query(default="markdown"),
    include_bible: bool = Query(default=False),
) -> FileResponse:
    return _studio_export_file_response(slug, format=format, include_bible=include_bible)


@app.patch("/studio/series/{slug}", response_model=StudioSeriesResponse)
def update_studio_series_endpoint(
    slug: str, payload: StudioProjectUpdateRequest
) -> StudioSeriesResponse:
    try:
        service.update_series(
            slug,
            premise=payload.premise,
            genre=payload.genre,
            language=payload.language,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioSeriesResponse.model_validate(service.get_series(slug))


@app.delete("/studio/series/{slug}", response_model=StudioDeleteResponse)
def delete_studio_series_endpoint(slug: str) -> StudioDeleteResponse:
    try:
        result = service.delete_series(slug)
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioDeleteResponse.model_validate(result)


@app.get("/studio/series/{slug}/export")
def export_studio_series_file(
    slug: str,
    format: str = Query(default="markdown"),
    include_bible: bool = Query(default=False),
) -> FileResponse:
    return _studio_export_file_response(slug, format=format, include_bible=include_bible)


def _studio_export_file_response(
    slug: str,
    *,
    format: str,
    include_bible: bool,
) -> FileResponse:
    try:
        result = service.export_studio_book(
            slug,
            export_format=format,
            include_bible=include_bible,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    media_type = (
        "application/epub+zip" if result["format"] == "epub" else "text/markdown; charset=utf-8"
    )
    return FileResponse(
        result["path"],
        filename=result["file_name"],
        media_type=media_type,
    )


@app.get("/studio/projects/{slug}/bible", response_model=StudioBibleResponse)
def get_studio_book_bible(slug: str) -> StudioBibleResponse:
    try:
        state = service.get_bible_state(slug, container_type="book")
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioBibleResponse.model_validate(state)


@app.post("/studio/projects/{slug}/bible/finalize", response_model=StudioBibleResponse)
def finalize_studio_book_bible(slug: str, payload: StudioBibleFinalizeRequest) -> StudioBibleResponse:
    try:
        state = service.save_bible_state(
            slug,
            container_type="book",
            setting_markdown=payload.setting_markdown,
            characters=[character.model_dump() for character in payload.characters],
        )
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioBibleResponse.model_validate(state)


@app.post("/studio/projects/{slug}/bible/messages/stream")
def studio_book_bible_stream(slug: str, payload: StudioMessageRequest) -> StreamingResponse:
    try:
        chunks = service.iter_bible_chat(
            slug,
            payload.message,
            container_type="book",
            provider=payload.provider,
            api_key=payload.api_key,
            model=payload.model,
            language=payload.language,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return _studio_stream_response(
        chunks, log_label=f"/studio/projects/{slug}/bible/messages/stream"
    )


@app.get("/studio/series/{slug}/bible", response_model=StudioBibleResponse)
def get_studio_series_bible(slug: str) -> StudioBibleResponse:
    try:
        state = service.get_bible_state(slug, container_type="series")
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioBibleResponse.model_validate(state)


@app.post("/studio/series/{slug}/bible/finalize", response_model=StudioBibleResponse)
def finalize_studio_series_bible(slug: str, payload: StudioBibleFinalizeRequest) -> StudioBibleResponse:
    try:
        state = service.save_bible_state(
            slug,
            container_type="series",
            setting_markdown=payload.setting_markdown,
            characters=[character.model_dump() for character in payload.characters],
        )
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return StudioBibleResponse.model_validate(state)


@app.post("/studio/series/{slug}/bible/messages/stream")
def studio_series_bible_stream(slug: str, payload: StudioMessageRequest) -> StreamingResponse:
    try:
        chunks = service.iter_bible_chat(
            slug,
            payload.message,
            container_type="series",
            provider=payload.provider,
            api_key=payload.api_key,
            model=payload.model,
            language=payload.language,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise _http_from_studio_error(exc) from exc
    return _studio_stream_response(
        chunks, log_label=f"/studio/series/{slug}/bible/messages/stream"
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
