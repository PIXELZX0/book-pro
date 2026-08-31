import pytest
from fastapi.testclient import TestClient

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
