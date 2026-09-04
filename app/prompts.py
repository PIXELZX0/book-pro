from typing import Iterable

from app.schemas import ChapterSummary


SYSTEM_PROMPT = (
    "You are a literary analysis assistant. "
    "Always return strict JSON only, with no markdown and no extra commentary."
)


def build_chapter_prompt(
    *,
    chapter_title: str,
    chapter_text: str,
    language: str,
    precise_analysis: bool = False,
) -> str:
    precise_note = (
        "정밀 분석 모드다. 챕터에 등장한 인물별로 이 장에서 드러난 특징을 character_traits에 반드시 정리하고, "
        "각 인물의 말/대사에서 알 수 있는 성향·심리·관계 정보도 speech_inferences에 반드시 포함하라."
        if precise_analysis
        else "정밀 분석 모드가 아니므로 character_traits는 생략하거나 빈 배열로 반환해도 된다."
    )
    precise_schema = (
        ',\n  "character_traits": [\n'
        '    {"character": "인물명", "traits": ["이 챕터에서 드러난 특징1", "특징2"], '
        '"speech_inferences": ["말/대사에서 추론한 정보1", "정보2"]}\n'
        "  ]"
    )

    return f"""
다음은 소설/서사 텍스트의 챕터 내용이다.
요약 결과는 반드시 {language}로 작성하라.
{precise_note}

[챕터 제목]
{chapter_title}

[챕터 본문]
{chapter_text}

아래 JSON 스키마를 정확히 지켜서 반환하라.
{{
  "summary": "챕터 핵심 요약 (4~8문장)",
  "key_events": ["핵심 사건 1", "핵심 사건 2"],
  "character_events": [
    {{"character": "인물명", "event": "무슨 일이 일어났는지", "impact": "해당 인물에 준 영향"}}
  ]{precise_schema}
}}
""".strip()


def _chapter_compact_lines(chapter_summaries: Iterable[ChapterSummary]) -> str:
    rows: list[str] = []
    for chapter in chapter_summaries:
        rows.append(
            f"챕터 {chapter.chapter_index} - {chapter.chapter_title}: {chapter.summary} | "
            f"사건={'; '.join(chapter.key_events[:5])}"
        )
        if chapter.character_traits:
            trait_rows: list[str] = []
            for row in chapter.character_traits:
                if not row.traits and not row.speech_inferences:
                    continue
                merged = row.traits[:3] + [f"대사:{item}" for item in row.speech_inferences[:2]]
                trait_rows.append(f"{row.character}({', '.join(merged)})")
            if trait_rows:
                rows.append(f"  캐릭터 특징={'; '.join(trait_rows)}")
    return "\n".join(rows)


def build_character_prompt(
    *,
    book_title: str,
    chapter_summaries: list[ChapterSummary],
    language: str,
) -> str:
    compact = _chapter_compact_lines(chapter_summaries)
    return f"""
책 제목: {book_title}
아래 챕터 요약과 챕터별 캐릭터 특징 관찰을 함께 사용해 캐릭터 프로필을 추출하라.
결과는 반드시 {language}로 작성하라.

[챕터 요약 모음]
{compact}

반드시 아래 JSON 형태를 지켜라.
{{
  "characters": [
    {{
      "name": "이름",
      "age": "나이 또는 추정",
      "sinsang": "신상(정체성/배경/사회적 위치)",
      "growth_background": "성장 배경",
      "voice": "말투/목소리 인상",
      "feeling": "전반적 느낌",
      "traits": ["특징1", "특징2"]
    }}
  ]
}}
""".strip()


def build_writing_style_prompt(
    *,
    book_title: str,
    chapter_summaries: list[ChapterSummary],
    language: str,
) -> str:
    compact = _chapter_compact_lines(chapter_summaries)
    return f"""
책 제목: {book_title}
아래 정보를 바탕으로 작가의 필체를 분석하라.
결과는 반드시 {language}로 작성하라.

[챕터 요약/특징 모음]
{compact}

이어쓰기(후속 집필)에 쓸 수 있도록 문체 패턴을 구체적으로 정리하라.
아래 JSON 스키마를 지켜라.
{{
  "summary": "필체 핵심 요약 (4~8문장)",
  "tone": "문체 톤",
  "sentence_style": "문장 길이/리듬/호흡 특징",
  "diction": "어휘 선택 특징",
  "perspective": "시점/서술 거리",
  "pacing": "전개 속도/장면 전환",
  "dialogue_style": "대사 운용 방식",
  "imagery_and_devices": ["이미지/비유/반복 패턴"],
  "continuation_guidelines": ["이어쓰기 가이드 1", "가이드 2"]
}}
""".strip()


def build_world_prompt(
    *,
    book_title: str,
    chapter_summaries: list[ChapterSummary],
    language: str,
) -> str:
    compact = _chapter_compact_lines(chapter_summaries)
    return f"""
책 제목: {book_title}
아래 요약 정보를 바탕으로 세계관을 정리하라.
결과는 반드시 {language}로 작성하라.

[챕터 요약 모음]
{compact}

아래 JSON 스키마를 지켜라.
{{
  "summary": "세계관 핵심 요약 (4~8문장)",
  "settings": ["시대/장소/사회 구조"],
  "rules": ["세계관 규칙/제약"],
  "themes": ["핵심 테마"]
}}
""".strip()


def build_book_qa_prompt(
    *,
    book_title: str,
    chapter_summaries: list[ChapterSummary],
    character_summaries_text: str,
    setting_markdown: str,
    question: str,
    language: str,
    character_name: str | None = None,
    json_response: bool = True,
) -> str:
    compact = _chapter_compact_lines(chapter_summaries)
    mode_note = (
        f"너는 반드시 '{character_name}' 캐릭터의 말투와 관점을 최대한 흉내 내어 답해야 한다."
        if character_name
        else "책 내용 기반 분석가로 답하라."
    )
    response_block = (
        """반드시 아래 JSON 스키마로만 답하라.
{
  "answer": "질문에 대한 답변"
}"""
        if json_response
        else "JSON으로 답하지 말고, 최종 답변만 자연스러운 문장으로 작성하라."
    )

    return f"""
책 제목: {book_title}
질문: {question}
{mode_note}
결과는 반드시 {language}로 작성하라.

[챕터 요약]
{compact}

[캐릭터 요약]
{character_summaries_text}

[세계관/설정]
{setting_markdown}

{response_block}
""".strip()


def build_studio_system_prompt(
    *,
    book_title: str,
    premise: str,
    genre: str,
    language: str,
    finalized_chapters: list[dict],
) -> str:
    if finalized_chapters:
        chapters_block = "\n".join(
            f"{chapter['chapter_index']}장 '{chapter['chapter_title']}': {chapter['summary']}"
            for chapter in finalized_chapters
        )
    else:
        chapters_block = "아직 확정된 챕터가 없다."

    return f"""
너는 사용자와 함께 새 소설을 집필하는 공동 작가다.
제목: {book_title}
장르: {genre or '미정'}
줄거리/기획 의도: {premise or '미정'}
모든 답변은 {language}로 작성하라.

사용자와 대화하며 다음 화의 스토리를 제안하고, 요청받으면 실제 본문을 초안으로 작성하라.
이미 확정된 챕터와 설정이 어긋나지 않도록 일관성을 유지하라.

[이미 확정된 챕터]
{chapters_block}
""".strip()


def build_studio_bible_prompt(
    *,
    title: str,
    premise: str,
    genre: str,
    language: str,
    existing_setting: str,
    existing_characters: list[dict],
) -> str:
    if existing_characters:
        characters_block = "\n".join(
            f"- {character['name']}: {character['markdown']}" for character in existing_characters
        )
    else:
        characters_block = "아직 없음"

    return f"""
너는 사용자와 함께 소설의 세계관/캐릭터 설정집을 만드는 공동 기획자다.
제목: {title}
장르: {genre or '미정'}
기획 의도: {premise or '미정'}
모든 답변은 {language}로 작성하라.

사용자와 대화하며 세계관 설정과 캐릭터 프로필을 구체화하라. 캐릭터를 제안할 때는
'## 캐릭터이름' 제목으로 구분해 정리하라.

[기존 세계관 설정]
{existing_setting or '아직 없음'}

[기존 캐릭터]
{characters_block}
""".strip()


def build_studio_agent_prompt(
    *,
    book_title: str,
    premise: str,
    genre: str,
    language: str,
    finalized_chapters: list[dict],
    setting_markdown: str,
    characters: list[dict],
    sandbox_roots: list[str],
    mode: str,
    series_title: str | None = None,
) -> str:
    if finalized_chapters:
        chapters_block = "\n".join(
            f"{chapter['chapter_index']}장 '{chapter['chapter_title']}': {chapter['summary']}"
            for chapter in finalized_chapters
        )
    else:
        chapters_block = "아직 확정된 챕터가 없다."

    if characters:
        characters_block = "\n".join(
            f"- {character['name']}: {character['markdown']}" for character in characters
        )
    else:
        characters_block = "아직 없음"

    if series_title:
        series_block = f"소속 시리즈: {series_title}\n"
    else:
        series_block = ""

    if mode == "approve":
        mode_block = (
            "쓰기/편집/삭제 도구는 즉시 적용되지 않고 사용자 승인 대기 상태가 된다. "
            "승인 전에도 작업 내용을 명확히 설명하라."
        )
    else:
        mode_block = "쓰기/편집/삭제 도구는 즉시 적용된다."

    roots_block = "\n".join(f"- {root}" for root in sandbox_roots)

    return f"""
너는 사용자와 함께 새 소설을 집필하는 공동 작가이며, 파일 도구를 직접 사용할 수 있다.
제목: {book_title}
{series_block}장르: {genre or '미정'}
줄거리/기획 의도: {premise or '미정'}
모든 답변은 {language}로 작성하라.

[사용 가능한 파일 도구]
- list_files(path): 파일/디렉터리 목록 조회
- read_file(path, offset, max_chars): 파일 읽기
- write_file(path, content): 파일 생성/덮어쓰기
- edit_file(path, find, replace, count): 정확한 부분 문자열 치환
- delete_file(path): 파일 삭제 (휴지통으로 이동)

[샌드박스 규칙]
도구의 path는 항상 아래 루트 기준의 상대 경로다. 루트 밖이나 숨김 파일, studio.json/series.json은 접근할 수 없다.
{roots_block}

[작업 지침]
- 챕터 본문은 chapter/c-<번호>-<제목>.md 파일로 저장하라. 저장 전에 기존 챕터를 읽고 흐름을 이어받아라.
- 파일을 수정하기 전에는 반드시 read_file로 현재 내용을 확인하라.
- 세계관/캐릭터 정보가 필요하면 setting.md와 character/ 폴더를 읽어라.
- {mode_block}
- studio.json, series.json은 직접 수정하지 말고 메타 수정은 사용자에게 안내하라.

[이미 확정된 챕터]
{chapters_block}

[세계관 설정]
{setting_markdown or '아직 없음'}

[캐릭터]
{characters_block}
""".strip()
