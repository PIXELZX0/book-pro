import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app import service
from app.config import Settings, get_settings
from app.prompts import build_studio_agent_prompt
from app.studio_files import (
    TOOL_SCHEMAS,
    PendingActionStore,
    StudioFileSandbox,
    execute_tool,
)
from app.storage import (
    extract_section,
    read_bible,
    read_book_detail,
    read_series,
    read_studio_conversation,
    read_studio_project,
    save_studio_conversation,
)

logger = logging.getLogger("uvicorn.error")

MAX_AGENT_STEPS = 12
_MAX_TOOL_RESULT_CHARS = 8000


def _truncate_tool_result(result: dict[str, Any]) -> str:
    payload = json.dumps(result, ensure_ascii=False)
    if len(payload) <= _MAX_TOOL_RESULT_CHARS:
        return payload
    return payload[:_MAX_TOOL_RESULT_CHARS] + "...(잘림)"


def _history_messages(history: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {"role": turn["role"], "content": turn["content"]}
        for turn in history
        if turn.get("role") in {"user", "assistant"} and turn.get("content")
    ]


@dataclass
class _AgentPrep:
    settings: Settings
    slug: str
    mode: str
    max_steps: int
    language: str
    sandbox: StudioFileSandbox
    pending_store: PendingActionStore
    summarizer: Any
    llm_messages: list[dict[str, Any]]
    updated_history: list[dict[str, Any]]


def _prepare_agent(
    slug: str,
    message: str,
    *,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    language: str | None = None,
    mode: str = "auto",
    max_steps: int = MAX_AGENT_STEPS,
) -> _AgentPrep:
    settings = get_settings()
    clean_message = (message or "").strip()
    if not clean_message:
        raise ValueError("메시지를 입력해 주세요.")

    resolved_mode = (mode or "auto").strip().lower()
    if resolved_mode not in {"auto", "approve"}:
        raise ValueError("mode는 auto 또는 approve만 가능합니다.")
    resolved_steps = max(min(int(max_steps or MAX_AGENT_STEPS), 24), 1)

    project = read_studio_project(settings.output_dir, slug=slug)
    detail = read_book_detail(settings.output_dir, slug=slug)
    history = read_studio_conversation(settings.output_dir, slug=slug)

    series_slug = project.get("series_slug")
    series_title = None
    if series_slug:
        series = read_series(settings.output_dir, slug=series_slug)
        series_title = series.get("series_title")

    bible = read_bible(settings.output_dir, slug=slug)
    summarizer = service.build_summarizer(provider=provider, api_key=api_key, model=model)
    resolved_language = (language or project.get("language") or "ko").strip() or "ko"

    finalized_chapters = [
        {
            "chapter_index": chapter["index"],
            "chapter_title": chapter["title"],
            "summary": extract_section(chapter["markdown"], "요약") or "",
        }
        for chapter in detail["chapters"]
    ]

    sandbox_roots = [f"./ (프로젝트: {slug})"]
    if series_slug:
        sandbox_roots.append(f"./ (시리즈: {series_slug})")

    system_prompt = build_studio_agent_prompt(
        book_title=project["book_title"],
        premise=project.get("premise", ""),
        genre=project.get("genre", ""),
        language=resolved_language,
        finalized_chapters=finalized_chapters,
        setting_markdown=bible["setting_markdown"],
        characters=bible["characters"],
        sandbox_roots=sandbox_roots,
        mode=resolved_mode,
        series_title=series_title,
    )

    sandbox = StudioFileSandbox(settings.output_dir, slug=slug, series_slug=series_slug)
    pending_store = PendingActionStore(settings.output_dir, slug=slug)

    llm_messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    llm_messages.extend(_history_messages(history))

    now = datetime.now(tz=timezone.utc).isoformat()
    updated_history = history + [
        {"role": "user", "content": clean_message, "created_at": now}
    ]
    save_studio_conversation(settings.output_dir, slug=slug, messages=updated_history)
    llm_messages.append({"role": "user", "content": clean_message})

    return _AgentPrep(
        settings=settings,
        slug=slug,
        mode=resolved_mode,
        max_steps=resolved_steps,
        language=resolved_language,
        sandbox=sandbox,
        pending_store=pending_store,
        summarizer=summarizer,
        llm_messages=llm_messages,
        updated_history=updated_history,
    )


def iter_agent_events(
    slug: str,
    message: str,
    *,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    language: str | None = None,
    mode: str = "auto",
    max_steps: int = MAX_AGENT_STEPS,
) -> Iterator[dict[str, Any]]:
    prep = _prepare_agent(
        slug,
        message,
        provider=provider,
        api_key=api_key,
        model=model,
        language=language,
        mode=mode,
        max_steps=max_steps,
    )

    def _generate() -> Iterator[dict[str, Any]]:
        yield {"type": "start", "slug": prep.slug, "mode": prep.mode, "max_steps": prep.max_steps}

        new_turns: list[dict[str, Any]] = []
        used_tools: list[dict[str, Any]] = []
        reply_parts: list[str] = []
        steps_used = 0

        for step in range(1, prep.max_steps + 1):
            steps_used = step
            step_text_parts: list[str] = []
            tool_calls: list[dict[str, str]] = []

            try:
                for event in prep.summarizer.stream_with_tools(prep.llm_messages, TOOL_SCHEMAS):
                    event_type = event.get("type")
                    if event_type == "text_delta":
                        text = event.get("text", "")
                        if text:
                            step_text_parts.append(text)
                            reply_parts.append(text)
                            yield {"type": "text_delta", "text": text}
                    elif event_type == "tool_calls":
                        tool_calls = event.get("calls", [])
                    elif event_type == "unsupported_tools":
                        yield {
                            "type": "notice",
                            "message": "이 모델은 파일 도구를 지원하지 않아 일반 대화로 동작합니다.",
                        }
            except Exception as exc:  # noqa: BLE001
                logger.exception("[스튜디오 에이전트 실패] slug='%s'", prep.slug)
                yield {"type": "error", "message": service.normalize_error_message(exc)}
                return

            step_text = "".join(step_text_parts).strip()
            if not tool_calls:
                if step_text:
                    new_turns.append(
                        {
                            "role": "assistant",
                            "content": step_text,
                            "created_at": datetime.now(tz=timezone.utc).isoformat(),
                        }
                    )
                break

            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": step_text or None,
                "tool_calls": [
                    {
                        "id": call.get("id") or f"call_{step}_{index}",
                        "type": "function",
                        "function": {
                            "name": call.get("name", ""),
                            "arguments": call.get("arguments") or "{}",
                        },
                    }
                    for index, call in enumerate(tool_calls)
                ],
            }
            prep.llm_messages.append(assistant_message)
            if step_text:
                new_turns.append(
                    {
                        "role": "assistant",
                        "content": step_text,
                        "created_at": datetime.now(tz=timezone.utc).isoformat(),
                    }
                )

            for call in tool_calls:
                tool_name = call.get("name", "")
                try:
                    arguments = json.loads(call.get("arguments") or "{}")
                    if not isinstance(arguments, dict):
                        arguments = {}
                except json.JSONDecodeError:
                    arguments = {}

                result = execute_tool(
                    prep.sandbox,
                    name=tool_name,
                    arguments=arguments,
                    mode=prep.mode,
                    pending_store=prep.pending_store,
                )
                used_tools.append({"tool": tool_name, "arguments": arguments, "result": result})
                yield {
                    "type": "tool_call",
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": result,
                    "step": step,
                }

                new_turns.append(
                    {
                        "role": "tool",
                        "content": f"[도구] {tool_name} {json.dumps(arguments, ensure_ascii=False)} → {_truncate_tool_result(result)}",
                        "created_at": datetime.now(tz=timezone.utc).isoformat(),
                    }
                )
                prep.llm_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id") or f"call_{step}_{tool_name}",
                        "content": _truncate_tool_result(result),
                    }
                )

        if steps_used >= prep.max_steps and new_turns and new_turns[-1]["role"] == "tool":
            yield {
                "type": "notice",
                "message": f"최대 도구 사용 횟수({prep.max_steps}회)에 도달해 중단했습니다.",
            }

        if new_turns:
            save_studio_conversation(
                prep.settings.output_dir,
                slug=prep.slug,
                messages=prep.updated_history + new_turns,
            )

        yield {
            "type": "done",
            "reply": "".join(reply_parts).strip(),
            "steps": steps_used,
            "actions": used_tools,
            "language": prep.language,
        }

    return _generate()


def run_agent(
    slug: str,
    message: str,
    *,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    language: str | None = None,
    mode: str = "auto",
    max_steps: int = MAX_AGENT_STEPS,
) -> dict[str, Any]:
    reply_parts: list[str] = []
    actions: list[dict[str, Any]] = []
    steps = 0
    for event in iter_agent_events(
        slug,
        message,
        provider=provider,
        api_key=api_key,
        model=model,
        language=language,
        mode=mode,
        max_steps=max_steps,
    ):
        if event["type"] == "text_delta":
            reply_parts.append(event["text"])
        elif event["type"] == "tool_call":
            actions.append(
                {
                    "tool": event["tool"],
                    "arguments": event["arguments"],
                    "result": event["result"],
                }
            )
        elif event["type"] == "done":
            steps = event["steps"]
    return {
        "slug": slug,
        "reply": "".join(reply_parts).strip(),
        "actions": actions,
        "steps": steps,
    }
