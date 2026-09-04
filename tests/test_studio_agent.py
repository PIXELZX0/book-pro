import json
from pathlib import Path

import pytest

from app.config import get_settings
from app.studio_agent import MAX_AGENT_STEPS, iter_agent_events, run_agent
from app.storage import save_studio_project


class FakeAgentSummarizer:
    def __init__(self, script: list) -> None:
        self.script = script
        self.calls: list[list[dict]] = []

    def stream_with_tools(self, messages, tools=None, temperature=0.4):
        self.calls.append([dict(m) for m in messages])
        step = self.script.pop(0)
        yield from step

    def stream_with_messages(self, messages):
        yield "일반 응답"


def _text(value: str) -> dict:
    return {"type": "text_delta", "text": value}


def _calls(*calls: dict) -> dict:
    return {"type": "tool_calls", "calls": list(calls)}


@pytest.fixture
def project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("BOOK_PRO_OUTPUT_DIR", str(tmp_path / "books"))
    get_settings.cache_clear()
    save_studio_project("에이전트 책", premise="프리미스", genre="판타지", language="ko", root_dir=tmp_path / "books")
    yield tmp_path / "books"
    get_settings.cache_clear()


def _slug(root: Path) -> str:
    return "book-에이전트 책"


def test_agent_reads_and_writes_files(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.service as service

    summarizer = FakeAgentSummarizer(
        [
            [
                _text("파일을 살펴볼게요.\n"),
                _calls(
                    {
                        "id": "c1",
                        "name": "write_file",
                        "arguments": json.dumps(
                            {"path": "chapter/c-1-시작.md", "content": "# 1장\n옛날 옛적에..."},
                            ensure_ascii=False,
                        ),
                    }
                ),
            ],
            [_text("1장을 저장했습니다.")],
        ]
    )
    monkeypatch.setattr(service, "build_summarizer", lambda **kwargs: summarizer)

    events = list(iter_agent_events(_slug(project_root), "1장 써 줘"))
    types = [event["type"] for event in events]

    assert "start" in types
    assert "text_delta" in types
    assert "tool_call" in types
    assert types[-1] == "done"

    chapter = project_root / _slug(project_root) / "chapter" / "c-1-시작.md"
    assert chapter.exists()
    assert "옛날 옛적에" in chapter.read_text(encoding="utf-8")

    done = events[-1]
    assert done["steps"] == 2
    assert done["actions"][0]["tool"] == "write_file"

    tool_result = [e for e in events if e["type"] == "tool_call"][0]["result"]
    assert tool_result["created"] is True

    second_call_messages = summarizer.calls[1]
    assert second_call_messages[-1]["role"] == "tool"
    assert second_call_messages[-2]["role"] == "assistant"


def test_agent_persists_conversation_with_tool_turns(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.service as service

    summarizer = FakeAgentSummarizer(
        [
            [
                _calls(
                    {
                        "id": "c1",
                        "name": "write_file",
                        "arguments": json.dumps({"path": "notes.md", "content": "메모"}),
                    }
                )
            ],
            [_text("완료했어요.")],
        ]
    )
    monkeypatch.setattr(service, "build_summarizer", lambda **kwargs: summarizer)

    list(iter_agent_events(_slug(project_root), "메모 남겨 줘"))

    from app.storage import read_studio_conversation

    messages = read_studio_conversation(project_root, slug=_slug(project_root))
    roles = [message["role"] for message in messages]
    assert roles == ["user", "tool", "assistant"]
    assert messages[-1]["content"] == "완료했어요."


def test_agent_stops_at_max_steps(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.service as service

    endless_step = [
        _calls(
            {
                "id": "loop",
                "name": "read_file",
                "arguments": json.dumps({"path": "notes.md"}),
            }
        )
    ]
    summarizer = FakeAgentSummarizer([])
    summarizer.script = [endless_step] * 10
    monkeypatch.setattr(service, "build_summarizer", lambda **kwargs: summarizer)

    events = list(iter_agent_events(_slug(project_root), "반복해 줘", max_steps=3))
    notices = [event for event in events if event["type"] == "notice"]
    assert any("최대 도구 사용 횟수" in event["message"] for event in notices)
    tool_calls = [event for event in events if event["type"] == "tool_call"]
    assert len(tool_calls) == 3


def test_agent_approve_mode_stores_pending_action(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.service as service

    summarizer = FakeAgentSummarizer(
        [
            [
                _calls(
                    {
                        "id": "c1",
                        "name": "write_file",
                        "arguments": json.dumps({"path": "chapter/c-1-승인.md", "content": "초안"}),
                    }
                )
            ],
            [_text("승인 요청드립니다.")],
        ]
    )
    monkeypatch.setattr(service, "build_summarizer", lambda **kwargs: summarizer)

    events = list(iter_agent_events(_slug(project_root), "1장 써 줘", mode="approve"))
    tool_event = [event for event in events if event["type"] == "tool_call"][0]
    assert tool_event["result"]["pending"] is True

    chapter = project_root / _slug(project_root) / "chapter" / "c-1-승인.md"
    assert chapter.exists() is False

    from app.studio_files import PendingActionStore

    store = PendingActionStore(project_root, slug=_slug(project_root))
    pending = store.list()
    assert len(pending) == 1
    assert pending[0]["tool"] == "write_file"


def test_agent_invalid_mode_and_empty_message(project_root: Path) -> None:
    with pytest.raises(ValueError, match="메시지"):
        list(iter_agent_events(_slug(project_root), "   "))
    with pytest.raises(ValueError, match="mode"):
        list(iter_agent_events(_slug(project_root), "안녕", mode="chaos"))


def test_stream_with_tools_accumulates_and_falls_back() -> None:
    from types import SimpleNamespace

    from app.summarizer import MultiProviderBookSummarizer, _is_tools_unsupported_error

    summarizer = MultiProviderBookSummarizer(provider="open-ai", api_key="k", model="m")

    class FakeStream:
        def __iter__(self):
            chunks = [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content="안녕",
                                tool_calls=[
                                    SimpleNamespace(
                                        index=0,
                                        id="call-1",
                                        function=SimpleNamespace(name="write_file", arguments='{"pa'),
                                    )
                                ],
                            )
                        )
                    ]
                ),
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content=None,
                                tool_calls=[
                                    SimpleNamespace(
                                        index=0,
                                        id=None,
                                        function=SimpleNamespace(name=None, arguments='th": "a"}'),
                                    )
                                ],
                            )
                        )
                    ]
                ),
            ]
            yield from chunks

    def create_ok(**kwargs):
        assert kwargs.get("tools")
        return FakeStream()

    def create_error(**kwargs):
        if kwargs.get("tools"):
            raise RuntimeError("this model does not support tools")
        return FakeStream()

    summarizer.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create_ok)))
    events = list(summarizer.stream_with_tools([{"role": "user", "content": "hi"}], [{"type": "function"}]))
    assert events[0] == {"type": "text_delta", "text": "안녕"}
    assert events[1]["type"] == "tool_calls"
    assert events[1]["calls"][0]["arguments"] == '{"path": "a"}'

    summarizer.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create_error)))
    events = list(summarizer.stream_with_tools([{"role": "user", "content": "hi"}], [{"type": "function"}]))
    assert events[0] == {"type": "unsupported_tools"}
    assert events[1] == {"type": "text_delta", "text": "안녕"}

    assert _is_tools_unsupported_error(RuntimeError("Tools are not supported"))
    assert not _is_tools_unsupported_error(RuntimeError("rate limit exceeded"))


def test_run_agent_collects_reply_and_actions(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.service as service

    summarizer = FakeAgentSummarizer(
        [
            [
                _calls(
                    {
                        "id": "c1",
                        "name": "write_file",
                        "arguments": json.dumps({"path": "notes.md", "content": "기록"}),
                    }
                )
            ],
            [_text("마무리 답변")],
        ]
    )
    monkeypatch.setattr(service, "build_summarizer", lambda **kwargs: summarizer)

    result = run_agent(_slug(project_root), "기록해 줘")
    assert result["reply"] == "마무리 답변"
    assert result["steps"] == 2
    assert result["actions"][0]["tool"] == "write_file"
    assert (project_root / _slug(project_root) / "notes.md").exists()
