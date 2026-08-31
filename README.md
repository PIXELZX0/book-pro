# book-pro

`book-pro` is a FastAPI service that turns EPUB books into structured AI outputs and reading assets.

It can generate:
- Chapter summaries (`chapter_summaries`)
- Character summaries (`character_summaries`)
- World summary (`world_summary`)
- Writing style analysis (`writing_style`)

It also provides:
- A web panel (`/panel`) for upload, library, detail, reader, and settings
- A page-flip style reader in Book Detail (Google Play Books-like flow)
- Server-side reading progress persistence for cross-browser/device resume
- Audiobook generation (chapter scripts + Qwen3 Voice Design + Base Voice Clone + TTS synthesis)
- Chat-style novel conversion (messenger-style speaker/text script, rendered as chat bubbles in the web panel)

## Key Features

- EPUB upload and parsing
- Incremental summarization with chapter digest reuse
- Per-book chapter-level parallel processing (`chapter_parallel`)
- Multi-book batch processing (`max_parallel`)
- Reader progress API with server persistence (`.reader-progress.json`)
- Q&A over summarized book content (`/ask`, `/ask/stream`)
- Docker and GitHub Actions CI/CD support

## 1) Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env`.

## 2) Configuration

Main environment variables:

- `OPENAI_API_KEY`: default API key used when request-level key is omitted
- `BOOK_PRO_PROVIDER`: default provider (`openai`, `anthropic`, `openrouter`, `venice`, `kilo-code`, `opencode-go`)
- `BOOK_PRO_MODEL`: default model
- `BOOK_PRO_MAX_CHAPTERS`: optional chapter limit per request (`0`/unset = unlimited)
- `BOOK_PRO_CHAPTER_PARALLEL`: per-book chapter workers (`1` to `8`, default `3`)
- `BOOK_PRO_OUTPUT_DIR`: output root (default `books`)
- `BOOK_PRO_QWEN_TTS_API_KEY`: default Qwen3 TTS key
- `BOOK_PRO_QWEN_TTS_BASE_URL`: default Qwen3 TTS base URL
- `BOOK_PRO_QWEN_TTS_MODEL`: default Qwen3 TTS model

Note: provider aliases like `open-ai` are normalized internally.

## 3) Run

```bash
uvicorn app.main:app --reload --port 8000
```

### Docker

Build:

```bash
docker build -t book-pro:local .
```

Run:

```bash
docker run --rm \
  -p 8000:8000 \
  -e OPENAI_API_KEY=YOUR_OPENAI_KEY \
  -v "$(pwd)/books:/app/books" \
  book-pro:local
```

Or Docker Compose:

```bash
docker compose up --build -d
```

## 4) URLs

- Swagger UI: <http://127.0.0.1:8000/docs>
- Web Panel (Library/Reader): <http://127.0.0.1:8000/panel>
- Studio (AI co-writing): <http://127.0.0.1:8000/studio>
- Agent Skill Doc: <http://127.0.0.1:8000/skill.md>

## 5) API Usage

### Summarize a single EPUB

```bash
curl -X POST "http://127.0.0.1:8000/summaries/from-epub" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/absolute/path/to/book.epub" \
  -F "provider=openai" \
  -F "model=gpt-4.1-mini" \
  -F "api_key=YOUR_PROVIDER_API_KEY" \
  -F "language=en" \
  -F "chapter_parallel=3"
```

### Upload EPUB only (no summary yet)

```bash
curl -X POST "http://127.0.0.1:8000/books/upload-epub" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/absolute/path/to/book.epub"
```

### Summarize an already uploaded book

```bash
curl -X POST "http://127.0.0.1:8000/books/book-your-book-slug/summaries" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "provider=openai" \
  -F "model=gpt-4.1-mini" \
  -F "api_key=YOUR_PROVIDER_API_KEY" \
  -F "language=en" \
  -F "chapter_parallel=4"
```

### Summarize multiple EPUBs (batch)

```bash
curl -X POST "http://127.0.0.1:8000/summaries/from-epubs" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@/absolute/path/to/book1.epub" \
  -F "files=@/absolute/path/to/book2.epub" \
  -F "provider=openrouter" \
  -F "model=openai/gpt-4.1-mini" \
  -F "api_key=YOUR_PROVIDER_API_KEY" \
  -F "language=en" \
  -F "max_parallel=2" \
  -F "chapter_parallel=3"
```

Concurrency behavior:
- `max_parallel`: number of books processed at once in batch endpoint
- `chapter_parallel`: number of chapters processed at once within each single book

### Reader API (original text)

Get parsed reader content:

```bash
curl -X GET "http://127.0.0.1:8000/books/book-your-book-slug/reader"
```

Get server-side saved reading position:

```bash
curl -X GET "http://127.0.0.1:8000/books/book-your-book-slug/reader/progress"
```

Save reading position:

```bash
curl -X PUT "http://127.0.0.1:8000/books/book-your-book-slug/reader/progress" \
  -H "Content-Type: application/json" \
  -d '{
    "page": 17,
    "total_pages": 240,
    "ratio": 0.071
  }'
```

Progress persistence details:
- Saved on the server at `books/book-<title>/.reader-progress.json`
- Web panel also keeps a local cache, then syncs to server
- Resume works across browsers/devices as long as they use the same backend storage

### Ask about a book

```bash
curl -X POST "http://127.0.0.1:8000/books/book-your-book-slug/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the central conflict?",
    "mode": "book",
    "provider": "openai",
    "model": "gpt-4.1-mini",
    "api_key": "YOUR_PROVIDER_API_KEY",
    "language": "en"
  }'
```

### Audiobook generation

```bash
curl -X POST "http://127.0.0.1:8000/books/book-your-book-slug/audiobook" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4.1-mini",
    "api_key": "YOUR_LLM_KEY",
    "tts_api_key": "YOUR_QWEN_TTS_KEY",
    "tts_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "tts_model": "qwen3-tts-vc-2026-01-22",
    "narrator_voice": "Cherry",
    "character_voices": {},
    "character_voice_prompts": {
      "Lina": "차분하지만 강인한 여성 톤, 중간 속도, 문장 끝을 또렷하게"
    },
    "enable_voice_design": true,
    "enable_base_voice_clone": true,
    "voice_design_model": "qwen-voice-design",
    "voice_clone_model": "qwen-voice-enrollment",
    "voice_target_model": "qwen3-tts-vc-2026-01-22",
    "target_minutes": 20,
    "language": "en"
  }'
```

Outputs are stored under `books/book-<title>/audiobook/`:
- `script.json`
- `chapter-scripts/c-*.json`
- `voices.json`
- `voice-previews/*.wav`
- `segments/c-*/0001-*.wav`
- `chapters/c-*.wav`
- `audiobook.wav`

Pipeline summary:
- `LLM`: chapter-wise script generation (`script.json`)
- `Qwen3 Voice Design`: character voice design shared across all chapters
- `Qwen3 Base Voice Clone`: clone the designed base voices
- `Qwen3 TTS synthesis`: per-line -> per-chapter -> final audiobook merge

### Chat-style conversion

Generate a chat-style script (speaker/text lines, same generator as the audiobook script step, no TTS):

```bash
curl -X POST "http://127.0.0.1:8000/books/book-your-book-slug/chat-script" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4.1-mini",
    "api_key": "YOUR_PROVIDER_API_KEY",
    "language": "en"
  }'
```

Fetch a previously generated script:

```bash
curl -X GET "http://127.0.0.1:8000/books/book-your-book-slug/chat-script"
```

Output stored at `books/book-<title>/chat/script.json`. In the web panel, open a book and use the **Chat** tab to generate/view it as a chat-bubble reading mode.

## 6) Local vLLM-Omni for Qwen3 TTS

If `tts_base_url` points to localhost/127.0.0.1, missing `tts_api_key` is automatically treated as `none`.

1. Install `vllm-omni` (recommended: Linux + CUDA GPU):

```bash
git clone https://github.com/vllm-project/vllm-omni.git
cd vllm-omni
python -m venv .venv
source .venv/bin/activate
python -m pip install -v --no-build-isolation .
```

2. Start Qwen3-TTS server from `book-pro` root:

```bash
cd /absolute/path/to/book-pro
source /absolute/path/to/vllm-omni/.venv/bin/activate
./scripts/run_qwen3_tts_vllm_omni.sh
```

Optional model/port override:

```bash
QWEN3_TTS_MODEL=Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice QWEN3_TTS_PORT=8091 ./scripts/run_qwen3_tts_vllm_omni.sh
```

3. Set `.env` in `book-pro`:

```bash
BOOK_PRO_QWEN_TTS_BASE_URL=http://127.0.0.1:8091/v1
BOOK_PRO_QWEN_TTS_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
BOOK_PRO_QWEN_TTS_API_KEY=none
```

## 7) Response Shape (example)

```json
{
  "data": {
    "book_title": "Book Title",
    "chapter_summaries": [
      {
        "chapter_index": 1,
        "chapter_title": "Chapter Title",
        "summary": "...",
        "key_events": ["..."],
        "character_events": [
          {
            "character": "Name",
            "event": "What happened",
            "impact": "Impact"
          }
        ],
        "character_traits": [
          {
            "character": "Name",
            "traits": ["..."],
            "speech_inferences": ["..."]
          }
        ]
      }
    ],
    "character_summaries": [
      {
        "name": "Name",
        "age": "Unknown",
        "sinsang": "Profile",
        "growth_background": "...",
        "voice": "...",
        "feeling": "...",
        "traits": ["..."]
      }
    ],
    "world_summary": {
      "summary": "...",
      "settings": ["..."],
      "rules": ["..."],
      "themes": ["..."]
    },
    "writing_style": {
      "summary": "...",
      "tone": "...",
      "sentence_style": "...",
      "diction": "...",
      "perspective": "...",
      "pacing": "...",
      "dialogue_style": "...",
      "imagery_and_devices": ["..."],
      "continuation_guidelines": ["..."]
    }
  }
}
```

## 8) Output Directory Layout

After successful processing, files are stored like:

```text
books/
  book-<title>/
    <uploaded-book>.epub
    .chapter-digests.json
    .reader-progress.json
    chapter/
      c-<index>-<chapter-title>.md
    character/
      <character-name>.md
    setting.md
    chat/
      script.json
    audiobook/
      script.json
      chapter-scripts/
        c-*.json
      voices.json
      voice-previews/
        *.wav
      segments/
        c-*/
          0001-*.wav
      chapters/
        c-*.wav
      audiobook.wav
```

## Notes

- Summary quality depends on source text quality, chapter segmentation, and selected model.
- For very large EPUBs, use `max_chapters` to reduce cost/latency.
- Per-book chapter parallelism can be set by request (`chapter_parallel`) or env (`BOOK_PRO_CHAPTER_PARALLEL`).
- Recommended `chapter_parallel` range is usually `2` to `4` (hard max is `8`).

## CI/CD

Workflow file: `.github/workflows/ci-cd.yml`

Pipeline stages:
1. `Test`: run `pytest`
2. `Build`: validate Docker image build
3. `Release`: on `v*` tag/release, publish GHCR image and create GitHub Release
