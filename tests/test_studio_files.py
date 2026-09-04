from pathlib import Path

import pytest

from app.config import get_settings
from app.studio_files import (
    PendingActionStore,
    StudioFileSandbox,
    execute_pending_action,
    execute_tool,
    list_history,
    list_files,
    read_file,
    restore_history_entry,
    write_file,
)
from app.storage import save_studio_project


@pytest.fixture
def project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path / "books"))
    get_settings.cache_clear()
    save_studio_project("샌드박스 책", premise="", genre="", language="ko", root_dir=tmp_path / "books")
    (tmp_path / "books" / "book-샌드박스 책" / "chapter").mkdir(parents=True, exist_ok=True)
    yield tmp_path / "books"
    get_settings.cache_clear()


def _sandbox(root: Path) -> StudioFileSandbox:
    return StudioFileSandbox(root, slug="book-샌드박스 책")


def test_resolve_rejects_path_escape(project_root: Path) -> None:
    sandbox = _sandbox(project_root)

    with pytest.raises(ValueError, match="상위 디렉터리"):
        sandbox.resolve("../other-book/chapter/c-1.md")
    with pytest.raises(ValueError, match="상대 경로"):
        sandbox.resolve("/etc/passwd")
    with pytest.raises(ValueError, match="숨김"):
        sandbox.resolve(".chapter-digests.json")


def test_resolve_rejects_disallowed_extensions(project_root: Path) -> None:
    sandbox = _sandbox(project_root)
    target = sandbox.resolve("evil.epub")
    assert target.name == "evil.epub"
    with pytest.raises(ValueError, match="파일 형식"):
        sandbox.check_readable(target)


def test_write_read_edit_delete_flow(project_root: Path) -> None:
    sandbox = _sandbox(project_root)

    result = execute_tool(sandbox, name="write_file", arguments={"path": "chapter/c-1-시작.md", "content": "1장 본문"})
    assert result["created"] is True

    read = execute_tool(sandbox, name="read_file", arguments={"path": "chapter/c-1-시작.md"})
    assert read["content"] == "1장 본문"

    edited = execute_tool(
        sandbox,
        name="edit_file",
        arguments={"path": "chapter/c-1-시작.md", "find": "1장", "replace": "첫 장"},
    )
    assert edited["replaced"] == 1

    deleted = execute_tool(sandbox, name="delete_file", arguments={"path": "chapter/c-1-시작.md"})
    assert (project_root / "book-샌드박스 책" / "chapter" / "c-1-시작.md").exists() is False
    assert ".trash" in deleted["trash_path"]


def test_write_overwrite_keeps_snapshot_and_restore(project_root: Path) -> None:
    sandbox = _sandbox(project_root)
    execute_tool(sandbox, name="write_file", arguments={"path": "notes.md", "content": "v1"})

    first_history = list_history(project_root, slug="book-샌드박스 책")
    assert first_history == []

    execute_tool(sandbox, name="write_file", arguments={"path": "notes.md", "content": "v2"})
    history = list_history(project_root, slug="book-샌드박스 책")
    assert len(history) == 1
    assert history[0]["path"] == "notes.md"

    restored = restore_history_entry(
        project_root, slug="book-샌드박스 책", entry_id=history[0]["id"]
    )
    assert restored["restored"] is True
    content = (project_root / "book-샌드박스 책" / "notes.md").read_text(encoding="utf-8")
    assert content == "v1"


def test_protected_and_unknown_tools(project_root: Path) -> None:
    sandbox = _sandbox(project_root)

    blocked = execute_tool(sandbox, name="write_file", arguments={"path": "studio.json", "content": "{}"})
    assert "보호된 파일" in blocked["error"]

    unknown = execute_tool(sandbox, name="rm_rf", arguments={})
    assert "알 수 없는 도구" in unknown["error"]


def test_list_files_skips_hidden(project_root: Path) -> None:
    sandbox = _sandbox(project_root)
    book_dir = project_root / "book-샌드박스 책"
    (book_dir / ".studio-history").mkdir(exist_ok=True)
    (book_dir / ".studio-history" / "index.json").write_text("{}", encoding="utf-8")
    (book_dir / "chapter" / "c-1-시작.md").write_text("본문", encoding="utf-8")

    listing = list_files(sandbox, "")
    assert "chapter/c-1-시작.md" in listing["files"]
    assert all(not path.startswith(".") for path in listing["files"] + listing["directories"])


def test_series_root_fallback(project_root: Path) -> None:
    from app.storage import save_series, save_bible

    save_series("샌드박스 시리즈", premise="", genre="", language="ko", root_dir=project_root)
    save_bible(
        project_root,
        slug="series-샌드박스 시리즈",
        setting_markdown="# 시리즈 세계관",
        characters=[],
    )

    sandbox = StudioFileSandbox(
        project_root, slug="book-샌드박스 책", series_slug="series-샌드박스 시리즈"
    )
    read = read_file(sandbox, "setting.md")
    assert "시리즈 세계관" in read["content"]


def test_pending_action_store_approve_flow(project_root: Path) -> None:
    sandbox = _sandbox(project_root)
    store = PendingActionStore(project_root, slug="book-샌드박스 책")

    result = execute_tool(
        sandbox,
        name="write_file",
        arguments={"path": "chapter/c-2-승인.md", "content": "내용"},
        mode="approve",
        pending_store=store,
    )
    assert result["pending"] is True
    assert (project_root / "book-샌드박스 책" / "chapter" / "c-2-승인.md").exists() is False

    pending = store.list()
    assert len(pending) == 1
    assert pending[0]["path"] == "chapter/c-2-승인.md"

    action = store.take(pending[0]["id"])
    applied = execute_pending_action(sandbox, action)
    assert applied.get("created") is True
    assert store.list() == []

    with pytest.raises(FileNotFoundError):
        store.take("missing-id")


def test_read_file_offset_and_limit(project_root: Path) -> None:
    sandbox = _sandbox(project_root)
    write_file(sandbox, "long.md", "0123456789" * 3)

    chunk = read_file(sandbox, "long.md", offset=5, max_chars=7)
    assert chunk["content"] == "5678901"
    assert chunk["total_chars"] == 30
