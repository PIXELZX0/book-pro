import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import app.service as service_module
from app.config import get_settings
from app.main import app, _is_local_tts_base_url, _resolve_chapter_parallel, _resolve_tts_api_key


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_redirects_to_panel() -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers.get("location") == "/panel"


def test_panel_page_is_served() -> None:
    response = client.get("/panel")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "book-pro Web Panel" in response.text


def test_skill_markdown_endpoint() -> None:
    response = client.get("/skill.md")
    assert response.status_code == 200
    assert "text/markdown" in response.headers.get("content-type", "")
    assert "# book-pro Skill" in response.text


def test_book_ask_requires_question() -> None:
    response = client.post("/books/book-missing/ask", json={"question": "   "})
    assert response.status_code == 400
    assert "질문" in response.json()["detail"]


def test_book_ask_character_requires_name() -> None:
    response = client.post(
        "/books/book-missing/ask",
        json={"question": "안녕", "mode": "character", "character_name": ""},
    )
    assert response.status_code == 400
    assert "character_name" in response.json()["detail"]


def test_create_audiobook_requires_existing_book() -> None:
    response = client.post(
        "/books/book-missing/audiobook",
        json={
            "api_key": "test-key",
            "tts_api_key": "test-tts-key",
        },
    )
    assert response.status_code == 404


def test_create_chat_script_requires_existing_book() -> None:
    response = client.post(
        "/books/book-missing/chat-script",
        json={"api_key": "test-key"},
    )
    assert response.status_code == 404


def test_get_chat_script_requires_existing_book() -> None:
    response = client.get("/books/book-missing/chat-script")
    assert response.status_code == 404


def test_upload_epub_only_rejects_non_epub() -> None:
    response = client.post(
        "/books/upload-epub",
        files={"file": ("test.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert ".epub" in response.json()["detail"]


def test_summarize_existing_book_requires_existing_book() -> None:
    response = client.post("/books/book-missing/summaries")
    assert response.status_code == 404


def test_reader_progress_requires_existing_book() -> None:
    response = client.get("/books/book-missing/reader/progress")
    assert response.status_code == 404


def test_reader_progress_update_requires_existing_book() -> None:
    response = client.put(
        "/books/book-missing/reader/progress",
        json={"page": 3, "total_pages": 20, "ratio": 0.15},
    )
    assert response.status_code == 404


def test_is_local_tts_base_url() -> None:
    assert _is_local_tts_base_url("http://127.0.0.1:8091/v1")
    assert _is_local_tts_base_url("http://localhost:8091/v1")
    assert not _is_local_tts_base_url("https://dashscope.aliyuncs.com/compatible-mode/v1")


def test_resolve_tts_api_key_uses_none_for_local_vllm() -> None:
    resolved = _resolve_tts_api_key(
        payload_tts_api_key="",
        default_tts_api_key="",
        tts_base_url="http://127.0.0.1:8091/v1",
    )
    assert resolved == "none"


def test_resolve_tts_api_key_requires_value_for_remote() -> None:
    with pytest.raises(ValueError):
        _resolve_tts_api_key(
            payload_tts_api_key="",
            default_tts_api_key="",
            tts_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )


def test_resolve_chapter_parallel_clamps_values() -> None:
    assert _resolve_chapter_parallel(None, 3) == 3
    assert _resolve_chapter_parallel(0, 3) == 1
    assert _resolve_chapter_parallel(99, 3) == 8


def test_studio_create_project_requires_title() -> None:
    response = client.post("/studio/projects", json={"title": "   "})
    assert response.status_code == 400


def test_studio_get_project_requires_existing_project() -> None:
    response = client.get("/studio/projects/book-missing-studio-project")
    assert response.status_code == 404


def test_studio_message_stream_requires_message() -> None:
    response = client.post(
        "/studio/projects/book-missing-studio-project/messages/stream",
        json={"message": "   "},
    )
    assert response.status_code == 400


def test_studio_finalize_chapter_rejects_invalid_index() -> None:
    response = client.post(
        "/studio/projects/book-missing-studio-project/chapters/finalize",
        json={"chapter_index": 0, "chapter_title": "제목", "content": "내용"},
    )
    assert response.status_code == 422


def test_studio_create_project_collides_with_non_studio_book(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        (tmp_path / "book-테스트북").mkdir(parents=True)

        response = client.post("/studio/projects", json={"title": "테스트북"})
        assert response.status_code == 400
    finally:
        get_settings.cache_clear()


def test_studio_finalize_chapter_reuses_existing_book_pipeline(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        create_response = client.post(
            "/studio/projects",
            json={"title": "스튜디오 테스트북", "premise": "prem", "genre": "판타지"},
        )
        assert create_response.status_code == 200
        slug = create_response.json()["slug"]

        finalize_response = client.post(
            f"/studio/projects/{slug}/chapters/finalize",
            json={"chapter_index": 1, "chapter_title": "시작", "content": "옛날 옛적에..."},
        )
        assert finalize_response.status_code == 200
        assert finalize_response.json()["chapter_count"] == 1

        chapter_files = list((tmp_path / slug / "chapter").glob("c-1-*.md"))
        assert len(chapter_files) == 1

        detail_response = client.get(f"/books/{slug}")
        assert detail_response.status_code == 200
        detail_payload = detail_response.json()
        assert detail_payload["chapter_count"] == 1
        assert detail_payload["is_studio"] is True
    finally:
        get_settings.cache_clear()


def test_studio_create_series_requires_title() -> None:
    response = client.post("/studio/series", json={"title": "  "})
    assert response.status_code == 400


def test_studio_get_series_requires_existing_series() -> None:
    response = client.get("/studio/series/series-missing")
    assert response.status_code == 404


def test_studio_create_volume_requires_existing_series() -> None:
    response = client.post(
        "/studio/series/series-missing/volumes",
        json={"title": "1권", "volume_index": 1},
    )
    assert response.status_code == 404


def test_studio_book_bible_requires_existing_project() -> None:
    response = client.get("/studio/projects/book-missing-studio-project/bible")
    assert response.status_code == 404


def test_studio_series_bible_requires_existing_series() -> None:
    response = client.get("/studio/series/series-missing/bible")
    assert response.status_code == 404


def test_studio_series_volume_inherits_shared_bible(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        series_response = client.post(
            "/studio/series",
            json={"title": "용사냥 시리즈", "premise": "용을 사냥하는 이야기", "genre": "판타지"},
        )
        assert series_response.status_code == 200
        series_slug = series_response.json()["slug"]

        bible_response = client.post(
            f"/studio/series/{series_slug}/bible/finalize",
            json={
                "setting_markdown": "# 세계관\n용이 실존하는 대륙",
                "characters": [{"name": "주인공", "markdown": "## 주인공\n용사냥꾼"}],
            },
        )
        assert bible_response.status_code == 200
        assert bible_response.json()["setting_markdown"] == "# 세계관\n용이 실존하는 대륙"

        volume_response = client.post(
            f"/studio/series/{series_slug}/volumes",
            json={"title": "용사냥 1권", "volume_index": 1},
        )
        assert volume_response.status_code == 200
        volume_payload = volume_response.json()
        assert volume_payload["format"] == "long"
        assert volume_payload["series_slug"] == series_slug
        assert volume_payload["volume_index"] == 1
        volume_slug = volume_payload["slug"]

        # Bible copied into the new volume's own setting.md / character files,
        # so the existing World/Character tabs work on it unchanged.
        detail_response = client.get(f"/books/{volume_slug}")
        assert detail_response.status_code == 200
        detail_payload = detail_response.json()
        assert "용이 실존하는 대륙" in detail_payload["setting_markdown"]
        assert len(detail_payload["characters"]) == 1

        series_detail = client.get(f"/studio/series/{series_slug}")
        assert series_detail.status_code == 200
        volumes = series_detail.json()["volumes"]
        assert len(volumes) == 1
        assert volumes[0]["slug"] == volume_slug
        assert volumes[0]["volume_index"] == 1
    finally:
        get_settings.cache_clear()


class _StubStreamSummarizer:
    def __init__(self, reply: str = "스텁 응답") -> None:
        self.reply = reply
        self.messages: list[dict] = []

    def stream_with_messages(self, messages: list[dict]) -> Iterator[str]:
        self.messages = messages
        yield self.reply[:2]
        yield self.reply[2:]


def test_studio_create_project_rejects_duplicate_title(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        first = client.post("/studio/projects", json={"title": "중복 소설", "premise": "원본"})
        assert first.status_code == 200
        original_created_at = first.json()["created_at"]

        duplicate = client.post("/studio/projects", json={"title": "중복 소설", "premise": "다름"})
        assert duplicate.status_code == 400

        project = client.get(f"/studio/projects/{first.json()['slug']}").json()
        assert project["premise"] == "원본"
        assert project["created_at"] == original_created_at
    finally:
        get_settings.cache_clear()


def test_studio_list_projects_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        created = client.post("/studio/projects", json={"title": "목록 책"}).json()
        items = client.get("/studio/projects").json()
        assert created["slug"] in [item["slug"] for item in items]
        assert all("book_title" in item and "chapter_count" in item for item in items)
    finally:
        get_settings.cache_clear()


def test_studio_message_stream_happy_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    stub = _StubStreamSummarizer("스트림 답변 완료")
    monkeypatch.setattr(service_module, "build_summarizer", lambda **kwargs: stub)
    try:
        slug = client.post("/studio/projects", json={"title": "스트림 책"}).json()["slug"]

        response = client.post(
            f"/studio/projects/{slug}/messages/stream", json={"message": "이어가 줘"}
        )
        assert response.status_code == 200
        assert response.text == "스트림 답변 완료"

        detail = client.get(f"/studio/projects/{slug}").json()
        assert [turn["role"] for turn in detail["messages"]] == ["user", "assistant"]
        assert detail["messages"][1]["content"] == "스트림 답변 완료"
        assert stub.messages[0]["role"] == "system"
    finally:
        get_settings.cache_clear()


def test_studio_bible_message_stream_happy_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    stub = _StubStreamSummarizer("설정집 답변")
    monkeypatch.setattr(service_module, "build_summarizer", lambda **kwargs: stub)
    try:
        slug = client.post("/studio/projects", json={"title": "바이블 스트림 책"}).json()["slug"]

        response = client.post(
            f"/studio/projects/{slug}/bible/messages/stream", json={"message": "세계관 정리해 줘"}
        )
        assert response.status_code == 200
        assert response.text == "설정집 답변"

        bible = client.get(f"/studio/projects/{slug}/bible").json()
        assert [turn["role"] for turn in bible["messages"]] == ["user", "assistant"]
    finally:
        get_settings.cache_clear()


def test_studio_non_streaming_message(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    stub = _StubStreamSummarizer("비스트리밍 답변")
    monkeypatch.setattr(service_module, "build_summarizer", lambda **kwargs: stub)
    try:
        slug = client.post("/studio/projects", json={"title": "동기 책"}).json()["slug"]

        response = client.post(f"/studio/projects/{slug}/messages", json={"message": "안녕"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["reply"] == "비스트리밍 답변"
        assert payload["slug"] == slug
        assert payload["chapter_count"] == 0
    finally:
        get_settings.cache_clear()


def test_studio_update_project_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        slug = client.post("/studio/projects", json={"title": "수정 책"}).json()["slug"]

        response = client.patch(
            f"/studio/projects/{slug}", json={"genre": "로맨스", "language": "en"}
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["genre"] == "로맨스"
        assert payload["language"] == "en"
        assert payload["premise"] == ""
    finally:
        get_settings.cache_clear()


def test_studio_delete_project_moves_to_trash(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        slug = client.post("/studio/projects", json={"title": "삭제 책"}).json()["slug"]

        response = client.delete(f"/studio/projects/{slug}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["container_type"] == "book"
        assert ".trash" in payload["trash_path"]
        assert (tmp_path / ".trash").exists()
        assert (tmp_path / slug).exists() is False
        assert client.get(f"/studio/projects/{slug}").status_code == 404
    finally:
        get_settings.cache_clear()


def test_studio_delete_series_detaches_volumes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        series_slug = client.post("/studio/series", json={"title": "삭제 시리즈"}).json()["slug"]
        volume = client.post(
            f"/studio/series/{series_slug}/volumes", json={"title": "1권", "volume_index": 1}
        ).json()

        response = client.delete(f"/studio/series/{series_slug}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["container_type"] == "series"
        assert payload["detached_volume_slugs"] == [volume["slug"]]

        assert client.get(f"/studio/series/{series_slug}").status_code == 404
        project = client.get(f"/studio/projects/{volume['slug']}")
        assert project.status_code == 200
        assert project.json()["series_slug"] is None
    finally:
        get_settings.cache_clear()


def test_studio_chapters_list_get_delete_and_finalize_dedupe(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        slug = client.post("/studio/projects", json={"title": "챕터 책"}).json()["slug"]
        client.post(
            f"/studio/projects/{slug}/chapters/finalize",
            json={"chapter_index": 1, "chapter_title": "시작", "content": "본문1"},
        )
        client.post(
            f"/studio/projects/{slug}/chapters/finalize",
            json={"chapter_index": 2, "chapter_title": "전개", "content": "본문2"},
        )

        listed = client.get(f"/studio/projects/{slug}/chapters").json()
        assert listed["chapter_count"] == 2
        assert [chapter["index"] for chapter in listed["chapters"]] == [1, 2]

        single = client.get(f"/studio/projects/{slug}/chapters/2")
        assert single.status_code == 200
        assert single.json()["markdown"].startswith("#")

        replaced = client.post(
            f"/studio/projects/{slug}/chapters/finalize",
            json={"chapter_index": 1, "chapter_title": "새로운 시작", "content": "수정 본문"},
        )
        assert replaced.status_code == 200
        assert replaced.json()["chapter_count"] == 2
        chapter_files = list((tmp_path / slug / "chapter").glob("c-1-*.md"))
        assert [path.name for path in chapter_files] == ["c-1-새로운 시작.md"]

        deleted = client.delete(f"/studio/projects/{slug}/chapters/1")
        assert deleted.status_code == 200
        assert deleted.json()["deleted_file_names"] == ["c-1-새로운 시작.md"]
        assert deleted.json()["chapter_count"] == 1

        assert client.get(f"/studio/projects/{slug}/chapters/1").status_code == 404
        assert client.delete(f"/studio/projects/{slug}/chapters/99").status_code == 404
    finally:
        get_settings.cache_clear()


def test_studio_export_markdown_and_epub(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        slug = client.post("/studio/projects", json={"title": "내보내기 책"}).json()["slug"]
        client.post(
            f"/studio/projects/{slug}/chapters/finalize",
            json={"chapter_index": 1, "chapter_title": "시작", "content": "여행의 시작"},
        )

        markdown = client.get(
            f"/studio/projects/{slug}/export",
            params={"format": "markdown", "include_bible": True},
        )
        assert markdown.status_code == 200
        assert "text/markdown" in markdown.headers["content-type"]
        assert "여행의 시작" in markdown.text

        epub_response = client.get(f"/studio/projects/{slug}/export", params={"format": "epub"})
        assert epub_response.status_code == 200
        assert epub_response.headers["content-type"] == "application/epub+zip"
        assert epub_response.content[:2] == b"PK"

        assert (tmp_path / slug / "export" / f"{slug}.md").exists()
        assert (tmp_path / slug / "export" / f"{slug}.epub").exists()

        invalid = client.get(f"/studio/projects/{slug}/export", params={"format": "pdf"})
        assert invalid.status_code == 400
    finally:
        get_settings.cache_clear()


def test_studio_series_export_includes_volumes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        series_slug = client.post("/studio/series", json={"title": "내보내기 시리즈"}).json()["slug"]
        volume = client.post(
            f"/studio/series/{series_slug}/volumes", json={"title": "1권", "volume_index": 1}
        ).json()
        client.post(
            f"/studio/projects/{volume['slug']}/chapters/finalize",
            json={"chapter_index": 1, "chapter_title": "1권 1장", "content": "1권 내용"},
        )

        markdown = client.get(f"/studio/series/{series_slug}/export")
        assert markdown.status_code == 200
        assert "1권 내용" in markdown.text
        assert "1권" in markdown.text
    finally:
        get_settings.cache_clear()


def test_studio_bible_uses_dedicated_store_and_mirrors(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        slug = client.post("/studio/projects", json={"title": "바이블 책"}).json()["slug"]

        response = client.post(
            f"/studio/projects/{slug}/bible/finalize",
            json={
                "setting_markdown": "# 세계관 v1",
                "characters": [
                    {"name": "주인공", "markdown": "## 주인공\n용사"},
                    {"name": "조력자", "markdown": "## 조력자\n현자"},
                ],
            },
        )
        assert response.status_code == 200

        bible_file = tmp_path / slug / "studio" / "bible.json"
        assert bible_file.exists()
        payload = json.loads(bible_file.read_text(encoding="utf-8"))
        assert payload["setting_markdown"] == "# 세계관 v1"
        assert payload["synced_character_files"] == ["주인공.md", "조력자.md"]
        assert (tmp_path / slug / "setting.md").read_text(encoding="utf-8") == "# 세계관 v1"
        assert (tmp_path / slug / "character" / "주인공.md").exists()

        client.post(
            f"/studio/projects/{slug}/bible/finalize",
            json={"setting_markdown": "# 세계관 v2", "characters": []},
        )
        assert (tmp_path / slug / "setting.md").read_text(encoding="utf-8") == "# 세계관 v2"
        assert (tmp_path / slug / "character" / "주인공.md").exists() is False
        assert (tmp_path / slug / "character" / "조력자.md").exists() is False
    finally:
        get_settings.cache_clear()


def test_studio_bible_legacy_fallback_preserves_summary_outputs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        slug = client.post("/studio/projects", json={"title": "레거시 책"}).json()["slug"]
        book_dir = tmp_path / slug
        (book_dir / "character").mkdir(parents=True, exist_ok=True)
        (book_dir / "setting.md").write_text("# 요약 파이프라인 세계관", encoding="utf-8")
        (book_dir / "character" / "요약캐릭터.md").write_text("## 요약캐릭터\n프로필", encoding="utf-8")

        bible = client.get(f"/studio/projects/{slug}/bible").json()
        assert "요약 파이프라인 세계관" in bible["setting_markdown"]
        assert bible["characters"][0]["name"] == "요약캐릭터"

        client.post(
            f"/studio/projects/{slug}/bible/finalize",
            json={"setting_markdown": "", "characters": []},
        )
        assert (book_dir / "character" / "요약캐릭터.md").exists()
        assert (book_dir / "studio" / "bible.json").exists()
    finally:
        get_settings.cache_clear()
