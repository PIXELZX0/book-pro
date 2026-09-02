import json
import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from app.models import BookContent, Chapter
from app.prompts import (
    SYSTEM_PROMPT,
    build_chapter_prompt,
    build_character_prompt,
    build_book_qa_prompt,
    build_writing_style_prompt,
    build_world_prompt,
)
from app.schemas import (
    BookSummary,
    ChapterCharacterTrait,
    ChapterSummary,
    CharacterEvent,
    CharacterSummary,
    WritingStyleSummary,
    WorldSummary,
)

_PROVIDER_ALIASES = {
    "openai": "openai",
    "open-ai": "openai",
    "open_ai": "openai",
    "anthropic": "anthropic",
    "openrouter": "openrouter",
    "open-router": "openrouter",
    "open_router": "openrouter",
    "venice": "venice",
    "kilocode": "kilo-code",
    "kilo-code": "kilo-code",
    "kilo_code": "kilo-code",
    "kilo code": "kilo-code",
    "opencode-go": "opencode-go",
    "opencode_go": "opencode-go",
    "opencode go": "opencode-go",
    "opencodego": "opencode-go",
    "opencode-zen": "opencode-zen",
    "opencode_zen": "opencode-zen",
    "opencode zen": "opencode-zen",
    "opencodezen": "opencode-zen",
    "zen": "opencode-zen",
}

_PROVIDER_BASE_URL = {
    "openai": None,
    "anthropic": "https://api.anthropic.com/v1/",
    "openrouter": "https://openrouter.ai/api/v1",
    "venice": "https://api.venice.ai/api/v1",
    "kilo-code": "https://api.kilo.ai/api/gateway",
    "opencode-go": "https://opencode.ai/zen/go/v1",
    "opencode-zen": "https://opencode.ai/zen/v1",
}

_PROVIDER_DEFAULT_MODEL = {
    "openai": "gpt-4.1-mini",
    "anthropic": "claude-sonnet-4-20250514",
    "openrouter": "openai/gpt-4.1-mini",
    "venice": "venice-uncensored",
    "kilo-code": "anthropic/claude-sonnet-4.5",
    "opencode-go": "claude-sonnet-4-5",
    "opencode-zen": "grok-4.6",
}

logger = logging.getLogger("uvicorn.error")
_REQUEST_TIMEOUT_SEC = 120.0
_REQUEST_MAX_RETRIES = 1
_QA_STREAM_SYSTEM_PROMPT = (
    "You are a literary analysis assistant. "
    "Answer directly in natural language and do not output JSON."
)

ProgressCallback = Callable[[dict[str, Any]], None]
ChapterSummaryCallback = Callable[[ChapterSummary], None]


class _ChapterPayload(BaseModel):
    summary: str
    key_events: list[str] = Field(default_factory=list)
    character_events: list[CharacterEvent] = Field(default_factory=list)
    character_traits: list[ChapterCharacterTrait] = Field(default_factory=list)


class _CharacterPayload(BaseModel):
    characters: list[CharacterSummary] = Field(default_factory=list)


class _WorldPayload(BaseModel):
    summary: str
    settings: list[str] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)


class _BookQaPayload(BaseModel):
    answer: str


class _WritingStylePayload(BaseModel):
    summary: str
    tone: str = "알 수 없음"
    sentence_style: str = "알 수 없음"
    diction: str = "알 수 없음"
    perspective: str = "알 수 없음"
    pacing: str = "알 수 없음"
    dialogue_style: str = "알 수 없음"
    imagery_and_devices: list[str] = Field(default_factory=list)
    continuation_guidelines: list[str] = Field(default_factory=list)


def normalize_provider(provider: str) -> str:
    key = (provider or "").strip().lower()
    normalized = _PROVIDER_ALIASES.get(key)
    if not normalized:
        allowed = ", ".join(sorted(set(_PROVIDER_ALIASES.values())))
        raise ValueError(f"지원하지 않는 provider 입니다: {provider}. 사용 가능: {allowed}")
    return normalized


def resolve_default_model(provider: str, configured_default: str | None = None) -> str:
    if configured_default and configured_default.strip():
        return configured_default.strip()
    return _PROVIDER_DEFAULT_MODEL[provider]


def _truncate_words(text: str, max_words: int = 2200) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def _extract_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    chunks.append(text)
                    continue
            text_attr = getattr(item, "text", None)
            if isinstance(text_attr, str):
                chunks.append(text_attr)
        return "\n".join(chunks)

    text_attr = getattr(content, "text", None)
    if isinstance(text_attr, str):
        return text_attr

    return ""


def _parse_json_object(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    try:
        loaded = json.loads(raw)
        if isinstance(loaded, dict):
            return loaded
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = raw[start : end + 1]
        loaded = json.loads(candidate)
        if isinstance(loaded, dict):
            return loaded

    raise ValueError("JSON 객체를 파싱할 수 없습니다.")


class MultiProviderBookSummarizer:
    def __init__(self, *, provider: str, api_key: str, model: str | None = None) -> None:
        self.provider = normalize_provider(provider)
        if not api_key:
            raise ValueError(f"{self.provider} provider용 API key가 비어 있습니다.")

        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": _REQUEST_TIMEOUT_SEC,
            "max_retries": _REQUEST_MAX_RETRIES,
        }
        base_url = _PROVIDER_BASE_URL[self.provider]
        if base_url:
            kwargs["base_url"] = base_url

        self.client = OpenAI(**kwargs)
        self.model = (model or "").strip() or resolve_default_model(self.provider)

    @staticmethod
    def _emit_progress(
        progress_callback: ProgressCallback | None,
        **payload: Any,
    ) -> None:
        if not progress_callback:
            return
        try:
            progress_callback(payload)
        except Exception:  # noqa: BLE001
            logger.exception("진행률 콜백 처리 중 오류가 발생했습니다.")

    @staticmethod
    def _emit_chapter_summary(
        chapter_callback: ChapterSummaryCallback | None,
        chapter_summary: ChapterSummary,
    ) -> None:
        if not chapter_callback:
            return
        try:
            chapter_callback(chapter_summary)
        except Exception:  # noqa: BLE001
            logger.exception("챕터 완료 콜백 처리 중 오류가 발생했습니다.")

    def summarize(
        self,
        book: BookContent,
        *,
        language: str = "ko",
        precise_analysis: bool = False,
        progress_callback: ProgressCallback | None = None,
        chapter_callback: ChapterSummaryCallback | None = None,
        chapter_parallel: int = 1,
    ) -> BookSummary:
        refresh_all = {chapter.index for chapter in book.chapters}
        return self.summarize_incremental(
            book,
            existing_chapter_summaries={},
            chapters_to_refresh=refresh_all,
            language=language,
            precise_analysis=precise_analysis,
            progress_callback=progress_callback,
            chapter_callback=chapter_callback,
            chapter_parallel=chapter_parallel,
        )

    def summarize_incremental(
        self,
        book: BookContent,
        *,
        existing_chapter_summaries: dict[int, ChapterSummary] | None = None,
        chapters_to_refresh: set[int] | None = None,
        language: str = "ko",
        precise_analysis: bool = False,
        progress_callback: ProgressCallback | None = None,
        chapter_callback: ChapterSummaryCallback | None = None,
        chapter_parallel: int = 1,
    ) -> BookSummary:
        chapter_count = len(book.chapters)
        existing_map = existing_chapter_summaries or {}
        refresh_set = set(chapters_to_refresh or set())
        for chapter in book.chapters:
            if chapter.index not in refresh_set and chapter.index not in existing_map:
                refresh_set.add(chapter.index)

        refresh_total = len(refresh_set)
        chapter_parallel = max(1, min(int(chapter_parallel), max(refresh_total, 1)))
        total_steps = max(1, refresh_total + 3)
        logger.info(
            "[증분 요약 시작] 책='%s' provider='%s' model='%s' chapters=%d refresh=%d chapter_parallel=%d precise=%s",
            book.title,
            self.provider,
            self.model,
            chapter_count,
            refresh_total,
            chapter_parallel,
            precise_analysis,
        )
        self._emit_progress(
            progress_callback,
            status="processing",
            progress=1,
            stage="start",
            message="요약 시작",
            chapter_total=chapter_count,
        )

        refresh_chapters = [chapter for chapter in book.chapters if chapter.index in refresh_set]
        refreshed_map: dict[int, ChapterSummary] = {}
        refreshed = 0

        if refresh_chapters and chapter_parallel > 1:
            logger.info(
                "[증분 요약 병렬 처리] 책='%s' refresh=%d workers=%d",
                book.title,
                len(refresh_chapters),
                chapter_parallel,
            )
            with ThreadPoolExecutor(max_workers=chapter_parallel) as executor:
                future_to_chapter = {
                    executor.submit(
                        self._summarize_chapter,
                        chapter,
                        language=language,
                        precise_analysis=precise_analysis,
                    ): chapter
                    for chapter in refresh_chapters
                }

                for future in as_completed(future_to_chapter):
                    chapter = future_to_chapter[future]
                    chapter_summary = future.result()
                    refreshed += 1
                    refreshed_map[chapter.index] = chapter_summary
                    self._emit_chapter_summary(chapter_callback, chapter_summary)

                    chapter_done = int((refreshed / total_steps) * 100)
                    logger.info(
                        "[증분 요약 진행률 %3d%%] 책='%s' 챕터 요약 완료 (%d/%d): %s",
                        chapter_done,
                        book.title,
                        refreshed,
                        refresh_total,
                        chapter.title,
                    )
                    self._emit_progress(
                        progress_callback,
                        status="processing",
                        progress=chapter_done,
                        stage="chapter",
                        message="챕터 요약 완료" if not precise_analysis else "챕터 정밀 요약 완료",
                        chapter_index=chapter.index,
                        chapter_total=chapter_count,
                        chapter_title=chapter.title,
                    )
        else:
            for chapter in refresh_chapters:
                refreshed += 1
                chapter_start = int(((refreshed - 1) / total_steps) * 100)
                logger.info(
                    "[증분 요약 진행률 %3d%%] 책='%s' 챕터 요약 중 (%d/%d): %s",
                    chapter_start,
                    book.title,
                    refreshed,
                    refresh_total,
                    chapter.title,
                )
                self._emit_progress(
                    progress_callback,
                    status="processing",
                    progress=chapter_start,
                    stage="chapter",
                    message="챕터 요약 중" if not precise_analysis else "챕터 정밀 요약 중",
                    chapter_index=chapter.index,
                    chapter_total=chapter_count,
                    chapter_title=chapter.title,
                    character_index=None,
                    character_total=None,
                    character_name=None,
                )
                chapter_summary = self._summarize_chapter(
                    chapter,
                    language=language,
                    precise_analysis=precise_analysis,
                )
                refreshed_map[chapter.index] = chapter_summary
                self._emit_chapter_summary(chapter_callback, chapter_summary)
                chapter_done = int((refreshed / total_steps) * 100)
                logger.info(
                    "[증분 요약 진행률 %3d%%] 책='%s' 챕터 요약 완료 (%d/%d): %s",
                    chapter_done,
                    book.title,
                    refreshed,
                    refresh_total,
                    chapter.title,
                )
                self._emit_progress(
                    progress_callback,
                    status="processing",
                    progress=chapter_done,
                    stage="chapter",
                    message="챕터 요약 완료" if not precise_analysis else "챕터 정밀 요약 완료",
                    chapter_index=chapter.index,
                    chapter_total=chapter_count,
                    chapter_title=chapter.title,
                )

        chapter_summaries: list[ChapterSummary] = []
        for chapter in book.chapters:
            if chapter.index in refresh_set:
                chapter_summaries.append(refreshed_map[chapter.index])
                continue

            existing = existing_map[chapter.index]
            if (
                existing.chapter_index != chapter.index
                or existing.chapter_title != chapter.title
            ):
                existing = existing.model_copy(
                    update={
                        "chapter_index": chapter.index,
                        "chapter_title": chapter.title,
                    }
                )
            chapter_summaries.append(existing)

        character_step = refresh_total + 1
        character_start = int(((character_step - 1) / total_steps) * 100)
        logger.info(
            "[증분 요약 진행률 %3d%%] 책='%s' 캐릭터 요약 중",
            character_start,
            book.title,
        )
        self._emit_progress(
            progress_callback,
            status="processing",
            progress=character_start,
            stage="character",
            message="캐릭터 요약 중",
            chapter_index=None,
            chapter_title=None,
        )
        character_summaries = self._summarize_characters(
            book_title=book.title,
            chapter_summaries=chapter_summaries,
            language=language,
        )
        character_done = int((character_step / total_steps) * 100)
        if character_summaries:
            total_characters = len(character_summaries)
            for index, character in enumerate(character_summaries, start=1):
                if total_characters == 1:
                    progress = character_done
                else:
                    progress = int(
                        character_start
                        + ((character_done - character_start) * index / total_characters)
                    )
                logger.info(
                    "[증분 요약 진행률 %3d%%] 책='%s' 캐릭터 처리 중 (%d/%d): %s",
                    progress,
                    book.title,
                    index,
                    total_characters,
                    (character.name or "알 수 없음"),
                )
                self._emit_progress(
                    progress_callback,
                    status="processing",
                    progress=progress,
                    stage="character",
                    message="캐릭터 처리 중",
                    character_index=index,
                    character_total=total_characters,
                    character_name=(character.name or "알 수 없음"),
                )
        logger.info(
            "[증분 요약 진행률 %3d%%] 책='%s' 캐릭터 요약 완료 (총 %d명)",
            character_done,
            book.title,
            len(character_summaries),
        )
        self._emit_progress(
            progress_callback,
            status="processing",
            progress=character_done,
            stage="character",
            message="캐릭터 요약 완료",
            character_index=len(character_summaries) if character_summaries else None,
            character_total=len(character_summaries) if character_summaries else None,
        )

        world_step = refresh_total + 2
        world_start = int(((world_step - 1) / total_steps) * 100)
        logger.info(
            "[증분 요약 진행률 %3d%%] 책='%s' 세계관 요약 중",
            world_start,
            book.title,
        )
        self._emit_progress(
            progress_callback,
            status="processing",
            progress=world_start,
            stage="world",
            message="세계관 요약 중",
            chapter_index=None,
            chapter_title=None,
            character_index=None,
            character_total=None,
            character_name=None,
        )
        world_summary = self._summarize_world(
            book_title=book.title,
            chapter_summaries=chapter_summaries,
            language=language,
        )
        world_done = int((world_step / total_steps) * 100)
        logger.info(
            "[증분 요약 진행률 %3d%%] 책='%s' 세계관 요약 완료",
            world_done,
            book.title,
        )
        self._emit_progress(
            progress_callback,
            status="processing",
            progress=world_done,
            stage="world",
            message="세계관 요약 완료",
        )

        style_step = refresh_total + 3
        style_start = int(((style_step - 1) / total_steps) * 100)
        logger.info(
            "[증분 요약 진행률 %3d%%] 책='%s' 작가 필체 분석 중",
            style_start,
            book.title,
        )
        self._emit_progress(
            progress_callback,
            status="processing",
            progress=style_start,
            stage="style",
            message="작가 필체 분석 중",
        )
        writing_style = self._summarize_writing_style(
            book_title=book.title,
            chapter_summaries=chapter_summaries,
            language=language,
        )
        style_done = int((style_step / total_steps) * 100)
        logger.info(
            "[증분 요약 진행률 %3d%%] 책='%s' 작가 필체 분석 완료",
            style_done,
            book.title,
        )
        logger.info("[증분 요약 완료] 책='%s' refresh=%d", book.title, refresh_total)
        self._emit_progress(
            progress_callback,
            status="processing",
            progress=style_done,
            stage="style",
            message="작가 필체 분석 완료",
        )

        return BookSummary(
            book_title=book.title,
            chapter_summaries=chapter_summaries,
            character_summaries=character_summaries,
            world_summary=world_summary,
            writing_style=writing_style,
        )

    def _chat_json(self, user_prompt: str) -> dict[str, Any]:
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        }

        if self.provider == "openai":
            request_kwargs["response_format"] = {"type": "json_object"}

        if self.provider == "openrouter":
            request_kwargs["extra_headers"] = {
                "HTTP-Referer": "http://localhost",
                "X-Title": "book-pro",
            }

        response = self.client.chat.completions.create(**request_kwargs)

        content = _extract_content_text(response.choices[0].message.content)
        return _parse_json_object(content or "{}")

    def _stream_chat(self, request_kwargs: dict[str, Any]) -> Iterator[str]:
        stream = self.client.chat.completions.create(**request_kwargs)
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            text = _extract_content_text(getattr(delta, "content", None))
            if text:
                yield text

    def _chat_text_stream(self, user_prompt: str, *, system_prompt: str) -> Iterator[str]:
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.2,
            "stream": True,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        if self.provider == "openrouter":
            request_kwargs["extra_headers"] = {
                "HTTP-Referer": "http://localhost",
                "X-Title": "book-pro",
            }

        yield from self._stream_chat(request_kwargs)

    def stream_with_messages(self, messages: list[dict[str, str]]) -> Iterator[str]:
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.4,
            "stream": True,
            "messages": messages,
        }

        if self.provider == "openrouter":
            request_kwargs["extra_headers"] = {
                "HTTP-Referer": "http://localhost",
                "X-Title": "book-pro",
            }

        yield from self._stream_chat(request_kwargs)

    def answer_about_book(
        self,
        *,
        book_title: str,
        chapter_summaries: list[ChapterSummary],
        character_summaries_text: str,
        setting_markdown: str,
        question: str,
        language: str,
        character_name: str | None = None,
    ) -> str:
        prompt = build_book_qa_prompt(
            book_title=book_title,
            chapter_summaries=chapter_summaries,
            character_summaries_text=character_summaries_text,
            setting_markdown=setting_markdown,
            question=question,
            language=language,
            character_name=character_name,
        )
        try:
            payload = _BookQaPayload.model_validate(self._chat_json(prompt))
            return payload.answer
        except (ValidationError, ValueError, json.JSONDecodeError):
            return "질문에 대한 답변을 생성하지 못했습니다. 질문을 더 구체적으로 입력해 주세요."

    def answer_about_book_stream(
        self,
        *,
        book_title: str,
        chapter_summaries: list[ChapterSummary],
        character_summaries_text: str,
        setting_markdown: str,
        question: str,
        language: str,
        character_name: str | None = None,
    ) -> Iterator[str]:
        prompt = build_book_qa_prompt(
            book_title=book_title,
            chapter_summaries=chapter_summaries,
            character_summaries_text=character_summaries_text,
            setting_markdown=setting_markdown,
            question=question,
            language=language,
            character_name=character_name,
            json_response=False,
        )

        emitted = False
        for text in self._chat_text_stream(prompt, system_prompt=_QA_STREAM_SYSTEM_PROMPT):
            emitted = True
            yield text

        if not emitted:
            yield "질문에 대한 답변을 생성하지 못했습니다. 질문을 더 구체적으로 입력해 주세요."

    def _summarize_chapter(
        self,
        chapter: Chapter,
        *,
        language: str,
        precise_analysis: bool,
    ) -> ChapterSummary:
        prompt = build_chapter_prompt(
            chapter_title=chapter.title,
            chapter_text=_truncate_words(chapter.text, max_words=2200),
            language=language,
            precise_analysis=precise_analysis,
        )

        try:
            payload = _ChapterPayload.model_validate(self._chat_json(prompt))
        except (ValidationError, ValueError, json.JSONDecodeError):
            payload = _ChapterPayload(
                summary=_truncate_words(chapter.text, max_words=120),
                key_events=[],
                character_events=[],
                character_traits=[],
            )

        return ChapterSummary(
            chapter_index=chapter.index,
            chapter_title=chapter.title,
            summary=payload.summary,
            key_events=payload.key_events,
            character_events=payload.character_events,
            character_traits=payload.character_traits,
        )

    def _summarize_characters(
        self,
        *,
        book_title: str,
        chapter_summaries: list[ChapterSummary],
        language: str,
    ) -> list[CharacterSummary]:
        prompt = build_character_prompt(
            book_title=book_title,
            chapter_summaries=chapter_summaries,
            language=language,
        )
        try:
            payload = _CharacterPayload.model_validate(self._chat_json(prompt))
            return payload.characters
        except (ValidationError, ValueError, json.JSONDecodeError):
            return []

    def _summarize_world(
        self,
        *,
        book_title: str,
        chapter_summaries: list[ChapterSummary],
        language: str,
    ) -> WorldSummary:
        prompt = build_world_prompt(
            book_title=book_title,
            chapter_summaries=chapter_summaries,
            language=language,
        )

        try:
            payload = _WorldPayload.model_validate(self._chat_json(prompt))
            return WorldSummary(
                summary=payload.summary,
                settings=payload.settings,
                rules=payload.rules,
                themes=payload.themes,
            )
        except (ValidationError, ValueError, json.JSONDecodeError):
            fallback = "챕터 요약 기반의 세계관 정보를 파싱하지 못했습니다."
            return WorldSummary(summary=fallback, settings=[], rules=[], themes=[])

    def _summarize_writing_style(
        self,
        *,
        book_title: str,
        chapter_summaries: list[ChapterSummary],
        language: str,
    ) -> WritingStyleSummary:
        prompt = build_writing_style_prompt(
            book_title=book_title,
            chapter_summaries=chapter_summaries,
            language=language,
        )

        try:
            payload = _WritingStylePayload.model_validate(self._chat_json(prompt))
            return WritingStyleSummary(
                summary=payload.summary,
                tone=payload.tone,
                sentence_style=payload.sentence_style,
                diction=payload.diction,
                perspective=payload.perspective,
                pacing=payload.pacing,
                dialogue_style=payload.dialogue_style,
                imagery_and_devices=payload.imagery_and_devices,
                continuation_guidelines=payload.continuation_guidelines,
            )
        except (ValidationError, ValueError, json.JSONDecodeError):
            fallback = "필체 분석 정보를 파싱하지 못했습니다."
            return WritingStyleSummary(
                summary=fallback,
                tone="알 수 없음",
                sentence_style="알 수 없음",
                diction="알 수 없음",
                perspective="알 수 없음",
                pacing="알 수 없음",
                dialogue_style="알 수 없음",
                imagery_and_devices=[],
                continuation_guidelines=[],
            )
