import asyncio
import base64
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from ebooklib import epub
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from fastmcp import Client
from fastmcp.exceptions import ToolError

import app.service as service
from app import mcp_server
from app.config import get_settings
from app.progress import complete_upload_progress
from app.mcp_server import (
    MCPHttpApp,
    MountPathRewriteMiddleware,
    build_mcp_app,
    get_mcp_server,
    mcp_mount_path,
)
from app.schemas import BookSummary, ChapterSummary, WorldSummary, WritingStyleSummary

EXPECTED_TOOLS = {
    "list_books",
    "get_book_overview",
    "list_chapters",
    "read_chapter_summary",
    "read_original_chapter",
    "list_characters",
    "read_character",
    "read_world_setting",
    "search_book",
    "ask_book",
    "get_reading_progress",
    "update_reading_progress",
    "list_provider_models",
    "import_epub",
    "summarize_epub_start",
    "summarize_book_start",
    "get_upload_progress_state",
    "list_active_uploads",
    "create_studio_project",
    "create_studio_series",
    "add_series_volume",
    "list_studio_projects",
    "list_studio_series",
    "get_studio_series",
    "get_studio_project",
    "studio_chat",
    "finalize_chapter",
    "get_bible",
    "save_bible",
    "bible_chat",
}


class StubSummarizer:
    def __init__(self, reply: str = "스텁 응답") -> None:
        self.reply = reply
        self.messages: list[dict[str, str]] = []

    def stream_with_messages(self, messages: list[dict[str, str]]) -> Iterator[str]:
        self.messages = messages
        yield self.reply[:2]
        yield self.reply[2:]

    def answer_about_book(self, **kwargs: Any) -> str:
        return self.reply


def _root_response(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def _run(scenario: Callable[[Client], Awaitable[Any]]) -> Any:
    async def main() -> Any:
        async with Client(get_mcp_server()) as client:
            return await scenario(client)

    return asyncio.run(main())


async def _call(client: Client, name: str, payload: dict[str, Any] | None = None) -> Any:
    result = await client.call_tool(name, payload or {})
    return result.data


def _build_epub(path: Path, title: str = "테스트 소설") -> bytes:
    book = epub.EpubBook()
    book.set_identifier("id-test-book")
    book.set_title(title)
    book.set_language("ko")

    body = " ".join(["주인공은 오래된 도서관에서 비밀 일기를 발견했다."] * 80)
    spine: list[Any] = ["nav"]
    toc: list[Any] = []
    for index in (1, 2):
        chapter = epub.EpubHtml(
            title=f"제{index}장",
            file_name=f"chap_{index}.xhtml",
            lang="ko",
        )
        chapter.content = f"<h1>제{index}장</h1><p>{body}</p><p>사건은 눈사태처럼 커졌다.</p>"
        book.add_item(chapter)
        spine.append(chapter)
        toc.append(epub.Link(f"chap_{index}.xhtml", f"제{index}장", f"제{index}장"))

    book.spine = spine
    book.toc = tuple(toc)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(str(path), book)
    return path.read_bytes()


@pytest.fixture
def epub_payload(tmp_path: Path) -> bytes:
    return _build_epub(tmp_path / "sample.epub")


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path / "books"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("BOOK_PRO_MCP_TOKEN", raising=False)
    monkeypatch.delenv("BOOK_PRO_MCP_IMPORT_DIR", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_expected_tools_are_registered() -> None:
    async def scenario(server: Any) -> set[str]:
        tools = await server.list_tools()
        return {tool.name for tool in tools}

    names = asyncio.run(scenario(get_mcp_server()))
    assert EXPECTED_TOOLS.issubset(names)


def test_resource_templates_are_registered() -> None:
    async def scenario() -> set[str]:
        templates = await get_mcp_server().list_resource_templates()
        return {template.uri_template for template in templates}

    assert asyncio.run(scenario()) == {
        "book://{slug}/overview",
        "book://{slug}/chapter/{index}",
        "book://{slug}/original/{index}",
        "book://{slug}/setting",
    }


def test_reading_flow(epub_payload: bytes) -> None:
    async def scenario(client: Client) -> None:
        imported = await _call(
            client,
            "import_epub",
            {"base64_content": base64.b64encode(epub_payload).decode("ascii")},
        )
        slug = imported["slug"]
        assert imported["chapter_count"] == 2

        library = await _call(client, "list_books", {"page_size": 10})
        assert slug in [item["slug"] for item in library["items"]]

        original = await _call(
            client,
            "read_original_chapter",
            {"slug": slug, "chapter_index": 1, "max_chars": 800},
        )
        assert original["returned_chars"] == 800
        assert original["has_more"] is True

        found = await _call(
            client, "search_book", {"slug": slug, "query": "눈사태", "scope": "original"}
        )
        assert found["matches"]
        assert found["matches"][0]["source"] == "original"

        progress = await _call(
            client, "update_reading_progress", {"slug": slug, "page": 3, "total_pages": 10}
        )
        assert progress["ratio"] == pytest.approx(3 / 9)
        assert (await _call(client, "get_reading_progress", {"slug": slug}))["page"] == 3

        overview = await _call(client, "get_book_overview", {"slug": slug})
        assert overview["book_title"] == "테스트 소설"

    _run(scenario)


def test_read_chapter_summary_and_resources() -> None:
    async def scenario(client: Client) -> None:
        project = await _call(client, "create_studio_project", {"title": "ResourceNovel"})
        slug = project["slug"]
        await _call(
            client,
            "finalize_chapter",
            {
                "slug": slug,
                "chapter_index": 1,
                "chapter_title": "첫 장",
                "content": "지하 서고에서 일기를 발견했다.",
            },
        )

        chapter = await _call(client, "read_chapter_summary", {"slug": slug, "chapter_index": 1})
        assert "일기" in chapter["markdown"]

        resources = await client.read_resource(f"book://{slug}/chapter/1")
        text = resources[0].text if hasattr(resources[0], "text") else str(resources[0])
        assert "첫 장" in text

        with pytest.raises(ToolError, match="챕터를 찾을 수 없습니다"):
            await _call(client, "read_chapter_summary", {"slug": slug, "chapter_index": 7})

    _run(scenario)


def test_studio_project_flow() -> None:
    async def scenario(client: Client) -> None:
        project = await _call(
            client,
            "create_studio_project",
            {"title": "새 소설", "premise": "도서관의 비밀", "genre": "미스터리"},
        )
        slug = project["slug"]

        finalized = await _call(
            client,
            "finalize_chapter",
            {
                "slug": slug,
                "chapter_index": 1,
                "chapter_title": "첫 장",
                "content": "도서관 지하에서 일기를 발견했다.",
            },
        )
        assert finalized["chapter_count"] == 1

        detail = await _call(client, "get_studio_project", {"slug": slug})
        assert detail["chapter_count"] == 1
        assert detail["premise"] == "도서관의 비밀"

        chapters = await _call(client, "list_chapters", {"slug": slug})
        assert [chapter["title"] for chapter in chapters["chapters"]] == ["첫 장"]

        projects = await _call(client, "list_studio_projects")
        assert slug in [item["slug"] for item in projects]

    _run(scenario)


def test_studio_chat_persists_conversation(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = StubSummarizer("첫 장의 초안입니다.")
    monkeypatch.setattr(service, "build_summarizer", lambda **kwargs: stub)

    async def scenario(client: Client) -> None:
        project = await _call(client, "create_studio_project", {"title": "대화 소설"})
        slug = project["slug"]

        reply = await _call(client, "studio_chat", {"slug": slug, "message": "첫 장을 써 줘"})
        assert reply["reply"] == "첫 장의 초안입니다."
        assert stub.messages[0]["role"] == "system"
        assert stub.messages[0]["content"].startswith("너는 사용자와 함께 새 소설을 집필하는")

        detail = await _call(client, "get_studio_project", {"slug": slug})
        assert [turn["role"] for turn in detail["messages"]] == ["user", "assistant"]
        assert detail["messages"][1]["content"] == "첫 장의 초안입니다."

    _run(scenario)


def test_ask_book_uses_summary_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = StubSummarizer("중심 갈등은 일기의 정체다.")
    monkeypatch.setattr(service, "build_summarizer", lambda **kwargs: stub)

    async def scenario(client: Client) -> None:
        project = await _call(client, "create_studio_project", {"title": "질문 소설"})
        slug = project["slug"]
        await _call(
            client,
            "finalize_chapter",
            {
                "slug": slug,
                "chapter_index": 1,
                "chapter_title": "첫 장",
                "content": "## 요약\n주인공이 일기를 발견했다.",
            },
        )

        answer = await _call(client, "ask_book", {"slug": slug, "question": "중심 갈등은?"})
        assert answer["answer"].startswith("중심 갈등은 일기의 정체다.")
        assert answer["mode"] == "book"

        with pytest.raises(ToolError, match="character_name"):
            await _call(
                client,
                "ask_book",
                {"slug": slug, "question": "누구?", "mode": "character"},
            )

    _run(scenario)


def test_series_volume_inherits_bible() -> None:
    async def scenario(client: Client) -> None:
        series = await _call(
            client,
            "create_studio_series",
            {"title": "연대기", "premise": "왕국의 몰락", "genre": "판타지"},
        )
        saved = await _call(
            client,
            "save_bible",
            {
                "slug": series["slug"],
                "setting_markdown": "## 세계관\n마법이 사라진 왕국",
                "characters_markdown": "## 아이린\n마지막 마법사\n\n## 카일\n용병",
            },
        )
        assert [character["name"] for character in saved["characters"]] == ["아이린", "카일"]

        volume = await _call(
            client,
            "add_series_volume",
            {"series_slug": series["slug"], "title": "1권", "volume_index": 1},
        )
        volume_bible = await _call(client, "get_bible", {"slug": volume["slug"]})
        assert volume_bible["setting_markdown"] == "## 세계관\n마법이 사라진 왕국"
        assert len(volume_bible["characters"]) == 2

        detail = await _call(client, "get_studio_series", {"slug": series["slug"]})
        assert [item["slug"] for item in detail["volumes"]] == [volume["slug"]]

        listed = await _call(client, "list_studio_series")
        assert series["slug"] in [item["slug"] for item in listed]

        projects = await _call(client, "list_studio_projects")
        assert volume["slug"] not in [item["slug"] for item in projects]

    _run(scenario)


def test_bible_chat_uses_series_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = StubSummarizer("설정집 초안")
    monkeypatch.setattr(service, "build_summarizer", lambda **kwargs: stub)

    async def scenario(client: Client) -> None:
        series = await _call(client, "create_studio_series", {"title": "연대기"})
        reply = await _call(
            client,
            "bible_chat",
            {"slug": series["slug"], "message": "세계관을 정리해 줘", "container_type": "series"},
        )
        assert reply["reply"] == "설정집 초안"
        assert reply["container_type"] == "series"
        assert "연대기" in stub.messages[0]["content"]

    _run(scenario)


def test_import_epub_path_is_restricted_to_import_dir(
    tmp_path: Path, epub_payload: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    monkeypatch.setenv("BOOK_PRO_MCP_IMPORT_DIR", str(allowed_dir))
    get_settings.cache_clear()

    outside = tmp_path / "outside.epub"
    outside.write_bytes(epub_payload)
    inside = allowed_dir / "inside.epub"
    inside.write_bytes(epub_payload)

    async def scenario(client: Client) -> None:
        with pytest.raises(ToolError, match="BOOK_PRO_MCP_IMPORT_DIR"):
            await _call(client, "import_epub", {"file_path": str(outside)})

        imported = await _call(client, "import_epub", {"file_path": str(inside)})
        assert imported["chapter_count"] == 2

    try:
        _run(scenario)
    finally:
        get_settings.cache_clear()


def test_import_epub_requires_import_dir_for_path(
    tmp_path: Path, epub_payload: bytes
) -> None:
    target = tmp_path / "sample.epub"
    target.write_bytes(epub_payload)

    async def scenario(client: Client) -> None:
        with pytest.raises(ToolError, match="BOOK_PRO_MCP_IMPORT_DIR"):
            await _call(client, "import_epub", {"file_path": str(target)})

    _run(scenario)


def test_summarize_job_progress(
    epub_payload: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary = BookSummary(
        book_title="테스트 소설",
        chapter_summaries=[
            ChapterSummary(chapter_index=1, chapter_title="제1장", summary="요약")
        ],
        world_summary=WorldSummary(summary="세계관"),
        writing_style=WritingStyleSummary(summary="문체"),
    )
    monkeypatch.setattr(service, "build_summarizer", lambda **kwargs: StubSummarizer())

    def fake_summarize(*args: Any) -> BookSummary:
        complete_upload_progress(args[8], message="요약 완료")
        return summary

    monkeypatch.setattr(service, "summarize_from_temp_path", fake_summarize)

    async def scenario(client: Client) -> None:
        imported = await _call(
            client,
            "import_epub",
            {"base64_content": base64.b64encode(epub_payload).decode("ascii")},
        )
        started = await _call(client, "summarize_book_start", {"slug": imported["slug"]})
        assert started["status"] == "queued"

        state: dict[str, Any] = {}
        for _ in range(200):
            state = await _call(
                client, "get_upload_progress_state", {"upload_id": started["upload_id"]}
            )
            if state["status"] in {"completed", "failed"}:
                break
            await asyncio.sleep(0.01)

        assert state["status"] == "completed"
        assert state["book_title"] == "테스트 소설"

    _run(scenario)


def test_summarize_epub_start_accepts_base64(epub_payload: bytes, monkeypatch: pytest.MonkeyPatch) -> None:
    summary = BookSummary(
        book_title="테스트 소설",
        world_summary=WorldSummary(summary="세계관"),
        writing_style=WritingStyleSummary(summary="문체"),
    )
    monkeypatch.setattr(service, "build_summarizer", lambda **kwargs: StubSummarizer())
    monkeypatch.setattr(service, "summarize_from_temp_path", lambda *args, **kwargs: summary)

    async def scenario(client: Client) -> None:
        started = await _call(
            client,
            "summarize_epub_start",
            {
                "base64_content": base64.b64encode(epub_payload).decode("ascii"),
                "file_name": "sample.epub",
            },
        )
        assert started["upload_id"]

        active = await _call(client, "list_active_uploads")
        assert started["upload_id"] in [item["upload_id"] for item in active]

        with pytest.raises(ToolError, match="file_path 또는 base64_content"):
            await _call(client, "summarize_epub_start", {})

    _run(scenario)


def test_mcp_http_app_requires_token() -> None:
    inner = FastAPI()

    @inner.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    app = FastAPI()
    app.mount("/mcp", MCPHttpApp(inner, token="secret"))

    with TestClient(app) as test_client:
        assert test_client.get("/mcp/ping").status_code == 401
        response = test_client.get("/mcp/ping", headers={"Authorization": "Bearer secret"})
        assert response.status_code == 200


def test_mcp_http_app_opens_without_token() -> None:
    inner = FastAPI()

    @inner.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    app = FastAPI()
    app.mount("/mcp", MCPHttpApp(inner))

    with TestClient(app) as test_client:
        assert test_client.get("/mcp/ping").status_code == 200


def test_mount_path_rewrite_middleware_adds_trailing_slash() -> None:
    child = Starlette(routes=[Route("/", _root_response)])

    app = FastAPI()
    app.add_middleware(MountPathRewriteMiddleware, path="/mcp")
    app.mount("/mcp", child)

    with TestClient(app) as test_client:
        response = test_client.get("/mcp", follow_redirects=False)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_build_mcp_app_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOOK_PRO_MCP_ENABLED", "false")
    get_settings.cache_clear()
    try:
        assert build_mcp_app() is None
    finally:
        get_settings.cache_clear()


def test_mount_path_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOOK_PRO_MCP_PATH", "mcp")
    get_settings.cache_clear()
    try:
        assert mcp_mount_path() == "/mcp"
        assert build_mcp_app() is not None
    finally:
        get_settings.cache_clear()


def test_get_mcp_server_caches_instance() -> None:
    assert mcp_server.get_mcp_server() is mcp_server.get_mcp_server()
