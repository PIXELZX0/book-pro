import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.progress import (
    append_upload_event,
    complete_upload_progress,
    fail_upload_progress,
    init_upload_progress,
    list_upload_events,
)
from app.schemas import BookSummary, ChapterSummary, WorldSummary, WritingStyleSummary

client = TestClient(app)


def _parse_sse(text: str) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block or block.startswith(":"):
            continue
        event_name = None
        data_line = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line[7:]
            elif line.startswith("data: "):
                data_line = line[6:]
        if event_name and data_line:
            frames.append({"event": event_name, "data": json.loads(data_line)})
    return frames


class _FakeSummarizer:
    def summarize_incremental(self, book, *, chapter_callback=None, **kwargs: Any) -> BookSummary:
        chapters = []
        for chapter in book.chapters:
            summary = ChapterSummary(
                chapter_index=chapter.index,
                chapter_title=chapter.title,
                summary=f"{chapter.title} 요약",
                key_events=["사건 발생"],
            )
            chapters.append(summary)
            if chapter_callback:
                chapter_callback(summary)
        return BookSummary(
            book_title=book.title,
            chapter_summaries=chapters,
            world_summary=WorldSummary(summary="세계관"),
            writing_style=WritingStyleSummary(summary="문체"),
        )


def test_progress_updates_are_recorded_as_events() -> None:
    init_upload_progress("job-events", file_name="book.epub")
    append_upload_event("job-events", "chapter", {"chapter_index": 1, "chapter_title": "제1장"})
    complete_upload_progress("job-events")

    events = list_upload_events("job-events")
    assert [event["event"] for event in events] == ["progress", "chapter", "progress", "done"]
    assert [event["seq"] for event in events] == [1, 2, 3, 4]
    assert events[1]["data"]["chapter_title"] == "제1장"
    assert events[-1]["data"]["status"] == "completed"


def test_init_resets_previous_events() -> None:
    init_upload_progress("job-reset", file_name="book.epub")
    complete_upload_progress("job-reset")
    init_upload_progress("job-reset", file_name="book.epub")

    events = list_upload_events("job-reset")
    assert [event["event"] for event in events] == ["progress"]
    assert events[0]["data"]["status"] == "queued"


def test_stream_emits_progress_chapter_and_done_events() -> None:
    def producer() -> None:
        init_upload_progress("job-stream", file_name="book.epub")
        time.sleep(0.2)
        append_upload_event(
            "job-stream",
            "chapter",
            {"chapter_index": 1, "chapter_title": "제1장", "summary": "요약 본문"},
        )
        time.sleep(0.2)
        complete_upload_progress("job-stream")

    thread = threading.Thread(target=producer, daemon=True)
    thread.start()

    with client.stream("GET", "/uploads/job-stream/stream") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        text = ""
        for chunk in response.iter_text():
            text += chunk
            if "event: done" in text:
                break

    thread.join(timeout=5)
    frames = _parse_sse(text)

    assert [frame["event"] for frame in frames] == ["progress", "chapter", "progress", "done"]
    chapter_frame = frames[1]
    assert chapter_frame["data"]["chapter_index"] == 1
    assert chapter_frame["data"]["summary"] == "요약 본문"
    assert frames[0]["data"]["seq"] == 1


def test_stream_resumes_from_last_event_id() -> None:
    init_upload_progress("job-resume", file_name="book.epub")
    append_upload_event("job-resume", "chapter", {"chapter_index": 1})
    append_upload_event("job-resume", "chapter", {"chapter_index": 2})
    append_upload_event("job-resume", "chapter", {"chapter_index": 3})
    complete_upload_progress("job-resume")

    with client.stream(
        "GET", "/uploads/job-resume/stream", headers={"Last-Event-ID": "3"}
    ) as response:
        text = ""
        for chunk in response.iter_text():
            text += chunk
            if "event: done" in text:
                break

    frames = _parse_sse(text)
    assert [frame["data"]["chapter_index"] for frame in frames if frame["event"] == "chapter"] == [3]


def test_stream_ends_with_timeout_event_for_unknown_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_module, "_UPLOAD_STREAM_WAIT_TIMEOUT", 0.5)

    with client.stream("GET", "/uploads/job-unknown/stream") as response:
        text = ""
        for chunk in response.iter_text():
            text += chunk
            if "event: timeout" in text:
                break

    frames = _parse_sse(text)
    assert [frame["event"] for frame in frames] == ["timeout"]


def test_stream_emits_failed_event() -> None:
    init_upload_progress("job-fail", file_name="book.epub")
    fail_upload_progress("job-fail", error="API key가 유효하지 않습니다.")

    with client.stream("GET", "/uploads/job-fail/stream") as response:
        text = ""
        for chunk in response.iter_text():
            text += chunk
            if "event: failed" in text:
                break

    frames = _parse_sse(text)

    assert [frame["event"] for frame in frames] == ["progress", "progress", "failed"]
    assert frames[-1]["data"]["status"] == "failed"
    assert frames[-1]["data"]["error"] == "API key가 유효하지 않습니다."


def test_summarize_publishes_chapter_events(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path / "books"))
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        from app import service
        from app.models import BookContent, Chapter

        settings = get_settings()
        source = Path(__file__).resolve().parents[1]
        epub_path = source / "books" / "book-일진녀 길들이기" / "1wls.epub"
        if not epub_path.exists():
            pytest.skip("샘플 EPUB이 없어 챕터 이벤트 검증을 건너뜁니다.")

        upload_id = "job-chapters"
        init_upload_progress(upload_id, file_name=epub_path.name)

        book = BookContent(
            title="이벤트 테스트",
            chapters=[
                Chapter(index=1, title="제1장", text="본문 " * 200),
                Chapter(index=2, title="제2장", text="본문 " * 200),
            ],
        )
        monkeypatch.setattr(service, "parse_epub", lambda *args, **kwargs: book)

        summary = service.summarize_from_temp_path(
            str(epub_path),
            epub_path.name,
            _FakeSummarizer(),
            None,
            1,
            "ko",
            False,
            settings.output_dir,
            upload_id,
        )

        chapter_events = [
            event for event in list_upload_events(upload_id) if event["event"] == "chapter"
        ]
        assert len(summary.chapter_summaries) == 2
        assert [event["data"]["chapter_title"] for event in chapter_events] == ["제1장", "제2장"]
        assert chapter_events[0]["data"]["summary"] == "제1장 요약"
        assert chapter_events[0]["data"]["file_name"].endswith(".md")
    finally:
        get_settings.cache_clear()
