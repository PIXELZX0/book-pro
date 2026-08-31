import base64
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field

from app.schemas import AudioScriptLine, ChapterSummary

logger = logging.getLogger("uvicorn.error")

_CUSTOMIZATION_ENDPOINT_SUFFIX = "/api/v1/services/audio/tts/customization"
_NARRATOR_ALIASES = {"narrator", "내레이터", "나레이터", "해설자"}


class ChapterAudioScript(BaseModel):
    chapter_index: int
    chapter_title: str
    lines: list[AudioScriptLine] = Field(default_factory=list)


class ChapterAudioScriptBundle(BaseModel):
    title: str
    chapters: list[ChapterAudioScript] = Field(default_factory=list)


class _ChapterAudioScriptEnvelope(BaseModel):
    title: str
    chapters: list[ChapterAudioScript] = Field(default_factory=list)


class _VoiceDesignSpec(BaseModel):
    character: str
    voice_prompt: str
    preview_text: str


class _VoiceDesignSpecEnvelope(BaseModel):
    voices: list[_VoiceDesignSpec] = Field(default_factory=list)


@dataclass
class AudiobookSynthesisArtifacts:
    script_bundle_path: Path
    chapter_script_dir: Path
    segment_dir: Path
    chapter_audio_dir: Path
    voice_profile_path: Path
    final_audio_path: Path
    line_count: int
    chapter_count: int
    voice_count: int


def _safe_name(name: str, fallback: str) -> str:
    safe = re.sub(r"[^\w\-.가-힣 ]+", "-", name or "").strip(" .-")
    return safe or fallback


def _json_object(raw: str) -> dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("오디오북 생성 응답이 비어 있습니다.")

    try:
        loaded = json.loads(raw)
        if isinstance(loaded, dict):
            return loaded
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        return json.loads(raw[start : end + 1])

    raise ValueError("오디오북 JSON 파싱에 실패했습니다.")


def _resolve_qwen_customization_endpoint(tts_base_url: str) -> str:
    parsed = urllib.parse.urlparse((tts_base_url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Qwen3 TTS base URL이 유효하지 않습니다: {tts_base_url}")

    path = (parsed.path or "").rstrip("/")
    if path.endswith("/compatible-mode/v1"):
        prefix = path[: -len("/compatible-mode/v1")]
    elif path.endswith("/api/v1"):
        prefix = path[: -len("/api/v1")]
    elif path.endswith("/v1"):
        prefix = path[: -len("/v1")]
    else:
        prefix = path

    prefix = prefix.rstrip("/")
    endpoint_path = f"{prefix}{_CUSTOMIZATION_ENDPOINT_SUFFIX}" if prefix else _CUSTOMIZATION_ENDPOINT_SUFFIX

    return urllib.parse.urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            endpoint_path,
            "",
            "",
            "",
        )
    )


def _decode_audio_data(data: str) -> bytes:
    raw = (data or "").strip()
    if not raw:
        raise ValueError("음성 미리보기 데이터가 비어 있습니다.")

    if raw.startswith("data:"):
        marker = "base64,"
        marker_index = raw.find(marker)
        if marker_index == -1:
            raise ValueError("data URI 형식의 base64 오디오를 해석할 수 없습니다.")
        raw = raw[marker_index + len(marker) :]

    try:
        return base64.b64decode(raw, validate=True)
    except ValueError as exc:
        raise ValueError("base64 오디오 디코딩에 실패했습니다.") from exc


class AudiobookGenerator:
    def __init__(
        self,
        *,
        llm_client: OpenAI,
        llm_model: str,
        tts_client: OpenAI | None = None,
        tts_model: str = "",
        tts_base_url: str = "",
        tts_api_key: str = "",
    ) -> None:
        self.llm_client = llm_client
        self.llm_model = llm_model
        self.tts_client = tts_client
        self.tts_model = tts_model
        self.tts_base_url = tts_base_url
        self.tts_api_key = tts_api_key

    def generate_chapter_scripts(
        self,
        *,
        book_title: str,
        chapter_summaries: list[ChapterSummary],
        character_summaries_text: str,
        language: str,
        target_minutes: int,
    ) -> ChapterAudioScriptBundle:
        if not chapter_summaries:
            raise ValueError("오디오북 대본 생성을 위한 챕터 요약이 없습니다.")

        compact_chapters = [
            {
                "chapter_index": ch.chapter_index,
                "chapter_title": ch.chapter_title,
                "summary": ch.summary,
                "key_events": ch.key_events,
            }
            for ch in chapter_summaries
        ]

        chapter_count = max(1, len(compact_chapters))
        min_lines_per_chapter = max(6, int((target_minutes * 3) / chapter_count))
        prompt = (
            "아래 소설 요약을 챕터별 오디오북 대본으로 변환하라. 반드시 JSON 객체만 응답하라.\n"
            "스키마: {title:string, chapters:[{chapter_index:int, chapter_title:string, lines:[{speaker:string, text:string}]}]}\n"
            "규칙:\n"
            f"- language는 {language}\n"
            f"- target_minutes={target_minutes} 분 분량\n"
            "- chapter_summaries의 모든 chapter_index를 정확히 1번씩 포함\n"
            "- speaker는 narrator 또는 캐릭터 이름\n"
            "- line은 20~120자 내외\n"
            f"- 각 chapter의 lines는 최소 {min_lines_per_chapter}개\n"
            "- 설명 문장 금지, JSON 이외 텍스트 금지\n\n"
            f"book_title: {book_title}\n"
            f"chapter_summaries: {json.dumps(compact_chapters, ensure_ascii=False)}\n"
            f"character_summaries: {character_summaries_text[:12000]}"
        )

        response = self.llm_client.responses.create(
            model=self.llm_model,
            input=prompt,
            temperature=0.7,
        )
        raw = getattr(response, "output_text", "")
        envelope = _ChapterAudioScriptEnvelope.model_validate(_json_object(raw))
        return self._normalize_chapter_scripts(
            envelope=envelope,
            chapter_summaries=chapter_summaries,
            book_title=book_title,
        )

    def _normalize_chapter_scripts(
        self,
        *,
        envelope: _ChapterAudioScriptEnvelope,
        chapter_summaries: list[ChapterSummary],
        book_title: str,
    ) -> ChapterAudioScriptBundle:
        by_index = {row.chapter_index: row for row in envelope.chapters}
        normalized: list[ChapterAudioScript] = []

        for chapter in chapter_summaries:
            candidate = by_index.get(chapter.chapter_index)
            candidate_lines = (candidate.lines if candidate else []) if candidate else []

            lines = [
                AudioScriptLine(
                    speaker=(line.speaker or "narrator").strip() or "narrator",
                    text=(line.text or "").strip(),
                )
                for line in candidate_lines
                if (line.text or "").strip()
            ]

            if not lines:
                lines = self._fallback_chapter_lines(chapter)

            normalized.append(
                ChapterAudioScript(
                    chapter_index=chapter.chapter_index,
                    chapter_title=chapter.chapter_title,
                    lines=lines,
                )
            )

        if not normalized:
            raise ValueError("생성된 챕터 대본이 비어 있습니다.")

        return ChapterAudioScriptBundle(
            title=(envelope.title or "").strip() or book_title,
            chapters=normalized,
        )

    @staticmethod
    def _fallback_chapter_lines(chapter: ChapterSummary) -> list[AudioScriptLine]:
        lines = [
            AudioScriptLine(
                speaker="narrator",
                text=(
                    f"{chapter.chapter_title}. "
                    f"{(chapter.summary or '이 장면은 중요한 전환점으로 이어진다.').strip()}"
                ),
            )
        ]
        for event in chapter.key_events[:5]:
            event_text = (event or "").strip()
            if event_text:
                lines.append(AudioScriptLine(speaker="narrator", text=event_text))

        while len(lines) < 4:
            lines.append(
                AudioScriptLine(
                    speaker="narrator",
                    text="장면의 감정선이 이어지며 다음 사건을 향해 흐른다.",
                )
            )

        return lines

    def _generate_voice_design_specs(
        self,
        *,
        book_title: str,
        character_names: list[str],
        character_summaries_text: str,
        language: str,
    ) -> dict[str, _VoiceDesignSpec]:
        if not character_names:
            return {}

        prompt = (
            "아래 캐릭터 목록을 Qwen3 TTS Voice Design용 보이스 설명으로 변환하라. 반드시 JSON 객체만 응답하라.\n"
            "스키마: {voices:[{character:string, voice_prompt:string, preview_text:string}]}\n"
            "규칙:\n"
            f"- language는 {language}\n"
            "- voice_prompt는 목소리 톤/속도/발성/감정 표현을 구체적으로 기술\n"
            "- preview_text는 1~2문장, 자연스러운 대사\n"
            "- character는 입력 목록의 이름과 정확히 일치\n"
            "- JSON 이외 텍스트 금지\n\n"
            f"book_title: {book_title}\n"
            f"characters: {json.dumps(character_names, ensure_ascii=False)}\n"
            f"character_summaries: {character_summaries_text[:12000]}"
        )

        try:
            response = self.llm_client.responses.create(
                model=self.llm_model,
                input=prompt,
                temperature=0.6,
            )
            raw = getattr(response, "output_text", "")
            envelope = _VoiceDesignSpecEnvelope.model_validate(_json_object(raw))
        except Exception:  # noqa: BLE001
            logger.exception("[오디오북] 보이스 스펙 생성 실패, 기본 프롬프트로 대체")
            envelope = _VoiceDesignSpecEnvelope(voices=[])

        available = {spec.character.strip(): spec for spec in envelope.voices if spec.character.strip()}
        output: dict[str, _VoiceDesignSpec] = {}
        for name in character_names:
            found = available.get(name)
            if found:
                output[name] = found
                continue
            output[name] = _VoiceDesignSpec(
                character=name,
                voice_prompt=self._fallback_voice_prompt(name, language),
                preview_text=self._fallback_preview_text(name, language),
            )

        return output

    @staticmethod
    def _fallback_voice_prompt(character_name: str, language: str) -> str:
        if language.lower().startswith("ko"):
            return (
                f"{character_name}의 말투를 반영해 또렷하고 안정적인 발음, 과장되지 않은 감정선, "
                "문장 끝을 명확히 처리하는 자연스러운 낭독 톤으로 말한다."
            )
        if language.lower().startswith("ja"):
            return (
                f"{character_name}らしい話し方で、明瞭な発音と自然な抑揚、"
                "落ち着いたテンポで感情を丁寧に表現する。"
            )
        return (
            f"Speak as {character_name} with clear articulation, controlled pacing, "
            "and expressive but natural emotional emphasis."
        )

    @staticmethod
    def _fallback_preview_text(character_name: str, language: str) -> str:
        if language.lower().startswith("ko"):
            return f"나는 {character_name}. 지금부터 이야기를 시작해 볼게."
        if language.lower().startswith("ja"):
            return f"私は{character_name}。ここから物語を始めよう。"
        return f"I am {character_name}, and this story begins now."

    @staticmethod
    def _is_narrator(speaker: str) -> bool:
        normalized = (speaker or "").strip().lower()
        return not normalized or normalized in _NARRATOR_ALIASES

    def _collect_script_characters(self, script_bundle: ChapterAudioScriptBundle) -> list[str]:
        names: set[str] = set()
        for chapter in script_bundle.chapters:
            for line in chapter.lines:
                speaker = (line.speaker or "").strip()
                if not speaker or self._is_narrator(speaker):
                    continue
                names.add(speaker)
        return sorted(names, key=lambda value: value.casefold())

    def _build_character_voice_map(
        self,
        *,
        script_bundle: ChapterAudioScriptBundle,
        out_dir: Path,
        book_title: str,
        language: str,
        character_summaries_text: str,
        manual_character_voices: dict[str, str],
        character_voice_prompts: dict[str, str],
        enable_voice_design: bool,
        enable_base_voice_clone: bool,
        voice_design_model: str,
        voice_clone_model: str,
        voice_target_model: str,
    ) -> tuple[dict[str, str], list[dict[str, str]]]:
        character_names = self._collect_script_characters(script_bundle)
        resolved = {
            name: voice.strip()
            for name, voice in manual_character_voices.items()
            if (name or "").strip() and (voice or "").strip()
        }
        details: list[dict[str, str]] = [
            {
                "character": name,
                "voice": voice,
                "source": "manual",
            }
            for name, voice in sorted(resolved.items(), key=lambda item: item[0].casefold())
        ]

        if not enable_voice_design:
            return resolved, details

        pending_names = [name for name in character_names if name not in resolved]
        if not pending_names:
            return resolved, details

        specs = self._generate_voice_design_specs(
            book_title=book_title,
            character_names=pending_names,
            character_summaries_text=character_summaries_text,
            language=language,
        )

        previews_dir = out_dir / "voice-previews"
        previews_dir.mkdir(parents=True, exist_ok=True)
        base_name = _safe_name(out_dir.parent.name, "book")

        for index, name in enumerate(pending_names, start=1):
            spec = specs.get(name)
            prompt = (character_voice_prompts.get(name) or (spec.voice_prompt if spec else "")).strip()
            if not prompt:
                prompt = self._fallback_voice_prompt(name, language)

            preview_text = (spec.preview_text if spec else "").strip() or self._fallback_preview_text(
                name,
                language,
            )

            preferred_design_name = f"{base_name}-design-{index:02d}-{_safe_name(name, 'character')}"
            designed_voice, preview_audio = self._qwen_voice_design_create(
                voice_design_model=voice_design_model,
                voice_target_model=voice_target_model,
                preferred_name=preferred_design_name,
                voice_prompt=prompt,
                preview_text=preview_text,
                language=language,
            )

            preview_path = previews_dir / f"{_safe_name(name, f'character-{index:02d}')}.wav"
            preview_path.write_bytes(preview_audio)

            final_voice = designed_voice
            source = "voice_design"
            clone_voice = ""
            if enable_base_voice_clone:
                preferred_clone_name = f"{base_name}-clone-{index:02d}-{_safe_name(name, 'character')}"
                clone_voice = self._qwen_voice_clone_create(
                    voice_clone_model=voice_clone_model,
                    voice_target_model=voice_target_model,
                    preferred_name=preferred_clone_name,
                    reference_audio=preview_audio,
                    reference_text=preview_text,
                    language=language,
                )
                final_voice = clone_voice
                source = "voice_design+base_clone"

            resolved[name] = final_voice
            details.append(
                {
                    "character": name,
                    "voice": final_voice,
                    "source": source,
                    "designed_voice": designed_voice,
                    "cloned_voice": clone_voice,
                    "preview_audio_path": str(preview_path),
                }
            )

        return resolved, details

    def _qwen_voice_design_create(
        self,
        *,
        voice_design_model: str,
        voice_target_model: str,
        preferred_name: str,
        voice_prompt: str,
        preview_text: str,
        language: str,
    ) -> tuple[str, bytes]:
        response = self._call_qwen_customization(
            {
                "model": voice_design_model,
                "input": {
                    "action": "create",
                    "target_model": voice_target_model,
                    "preferred_name": preferred_name,
                    "voice_prompt": voice_prompt,
                    "preview_text": preview_text,
                    "language": language,
                },
                "parameters": {
                    "sample_rate": 24000,
                    "response_format": "wav",
                },
            }
        )

        output = response.get("output")
        if not isinstance(output, dict):
            raise ValueError("Qwen3 Voice Design 응답에 output이 없습니다.")

        voice = str(output.get("voice") or "").strip()
        preview_audio = output.get("preview_audio")
        preview_data = ""
        if isinstance(preview_audio, dict):
            preview_data = str(preview_audio.get("data") or "").strip()

        if not voice:
            raise ValueError("Qwen3 Voice Design 응답에 voice가 없습니다.")
        if not preview_data:
            raise ValueError("Qwen3 Voice Design 응답에 preview_audio.data가 없습니다.")

        return voice, _decode_audio_data(preview_data)

    def _qwen_voice_clone_create(
        self,
        *,
        voice_clone_model: str,
        voice_target_model: str,
        preferred_name: str,
        reference_audio: bytes,
        reference_text: str,
        language: str,
    ) -> str:
        data_uri = f"data:audio/wav;base64,{base64.b64encode(reference_audio).decode('ascii')}"

        response = self._call_qwen_customization(
            {
                "model": voice_clone_model,
                "input": {
                    "action": "create",
                    "target_model": voice_target_model,
                    "preferred_name": preferred_name,
                    "audio": {"data": data_uri},
                    "text": reference_text,
                    "language": language,
                },
            }
        )

        output = response.get("output")
        if not isinstance(output, dict):
            raise ValueError("Qwen3 Base Voice Clone 응답에 output이 없습니다.")

        voice = str(output.get("voice") or "").strip()
        if not voice:
            raise ValueError("Qwen3 Base Voice Clone 응답에 voice가 없습니다.")

        return voice

    def _call_qwen_customization(self, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = _resolve_qwen_customization_endpoint(self.tts_base_url)
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.tts_api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Qwen3 TTS customization 요청 실패 (HTTP {exc.code}): {message[:300]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Qwen3 TTS customization 네트워크 오류: {exc.reason}") from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Qwen3 TTS customization 응답을 JSON으로 파싱할 수 없습니다.") from exc

        if not isinstance(parsed, dict):
            raise RuntimeError("Qwen3 TTS customization 응답 형식이 올바르지 않습니다.")

        return parsed

    def synthesize(
        self,
        *,
        script_bundle: ChapterAudioScriptBundle,
        out_dir: Path,
        book_title: str,
        language: str,
        narrator_voice: str,
        character_voices: dict[str, str],
        character_summaries_text: str,
        character_voice_prompts: dict[str, str],
        enable_voice_design: bool,
        enable_base_voice_clone: bool,
        voice_design_model: str,
        voice_clone_model: str,
        voice_target_model: str,
    ) -> AudiobookSynthesisArtifacts:
        out_dir.mkdir(parents=True, exist_ok=True)

        script_bundle_path = out_dir / "script.json"
        script_bundle_path.write_text(
            script_bundle.model_dump_json(indent=2),
            encoding="utf-8",
        )

        chapter_script_dir = out_dir / "chapter-scripts"
        chapter_script_dir.mkdir(parents=True, exist_ok=True)
        for chapter in script_bundle.chapters:
            chapter_path = chapter_script_dir / (
                f"c-{chapter.chapter_index:03d}-{_safe_name(chapter.chapter_title, 'chapter')}.json"
            )
            chapter_path.write_text(
                chapter.model_dump_json(indent=2),
                encoding="utf-8",
            )

        resolved_character_voices, voice_details = self._build_character_voice_map(
            script_bundle=script_bundle,
            out_dir=out_dir,
            book_title=book_title,
            language=language,
            character_summaries_text=character_summaries_text,
            manual_character_voices=character_voices,
            character_voice_prompts=character_voice_prompts,
            enable_voice_design=enable_voice_design,
            enable_base_voice_clone=enable_base_voice_clone,
            voice_design_model=voice_design_model,
            voice_clone_model=voice_clone_model,
            voice_target_model=voice_target_model,
        )

        voice_profile_path = out_dir / "voices.json"
        voice_profile_path.write_text(
            json.dumps(
                {
                    "narrator_voice": narrator_voice,
                    "character_voices": resolved_character_voices,
                    "details": voice_details,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        segment_dir = out_dir / "segments"
        chapter_audio_dir = out_dir / "chapters"
        segment_dir.mkdir(parents=True, exist_ok=True)
        chapter_audio_dir.mkdir(parents=True, exist_ok=True)

        chapter_audio_paths: list[Path] = []
        total_line_count = 0

        for chapter in script_bundle.chapters:
            chapter_segment_dir = segment_dir / f"c-{chapter.chapter_index:03d}"
            chapter_segment_dir.mkdir(parents=True, exist_ok=True)

            chapter_segment_paths: list[Path] = []
            for line_index, line in enumerate(chapter.lines, start=1):
                speaker = (line.speaker or "narrator").strip() or "narrator"
                voice = (
                    narrator_voice
                    if self._is_narrator(speaker)
                    else resolved_character_voices.get(speaker, narrator_voice)
                )

                segment_path = chapter_segment_dir / (
                    f"{line_index:04d}-{_safe_name(speaker, 'narrator')}.wav"
                )

                with self.tts_client.audio.speech.with_streaming_response.create(
                    model=self.tts_model,
                    voice=voice,
                    input=line.text,
                    response_format="wav",
                ) as response:
                    response.stream_to_file(segment_path)

                chapter_segment_paths.append(segment_path)
                total_line_count += 1

            chapter_audio_path = chapter_audio_dir / (
                f"c-{chapter.chapter_index:03d}-{_safe_name(chapter.chapter_title, 'chapter')}.wav"
            )
            self._merge_wav(chapter_segment_paths, chapter_audio_path)
            chapter_audio_paths.append(chapter_audio_path)

        final_audio = out_dir / "audiobook.wav"
        self._merge_wav(chapter_audio_paths, final_audio)

        logger.info("[오디오북 생성 완료] path='%s' chapters=%d", final_audio, len(chapter_audio_paths))
        return AudiobookSynthesisArtifacts(
            script_bundle_path=script_bundle_path,
            chapter_script_dir=chapter_script_dir,
            segment_dir=segment_dir,
            chapter_audio_dir=chapter_audio_dir,
            voice_profile_path=voice_profile_path,
            final_audio_path=final_audio,
            line_count=total_line_count,
            chapter_count=len(script_bundle.chapters),
            voice_count=len(resolved_character_voices),
        )

    @staticmethod
    def _merge_wav(parts: list[Path], destination: Path) -> None:
        if not parts:
            raise ValueError("병합할 오디오 세그먼트가 없습니다.")

        with wave.open(str(parts[0]), "rb") as first:
            params = first.getparams()
            frames = [first.readframes(first.getnframes())]

        for part in parts[1:]:
            with wave.open(str(part), "rb") as current:
                if current.getparams()[:3] != params[:3]:
                    raise ValueError("오디오 파라미터가 서로 달라 WAV 병합이 불가능합니다.")
                frames.append(current.readframes(current.getnframes()))

        with wave.open(str(destination), "wb") as out:
            out.setparams(params)
            for frame in frames:
                out.writeframes(frame)
