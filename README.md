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
- A Studio (`/studio`) for AI co-writing: chat, series/volumes, a setting bible, agentic file tools, chapter finalize, export (Markdown/EPUB), trash + restore
- An MCP server (`/mcp`, plus stdio mode) so AI agents can read books and write books in the Studio

## Key Features

- EPUB upload and parsing
- Incremental summarization with chapter digest reuse
- Per-book chapter-level parallel processing (`chapter_parallel`)
- Multi-book batch processing (`max_parallel`)
- Reader progress API with server persistence (`.reader-progress.json`)
- Q&A over summarized book content (`/ask`, `/ask/stream`)
- Studio co-writing with an agentic file sandbox (`read`/`list`/`write`/`edit`/`delete` inside `books/<project>/` + its series dir, with snapshots/undo and an optional approval mode)
- MCP tools for library reading, Studio co-writing, and asynchronous EPUB summarization
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
- `BOOK_PRO_PROVIDER`: default provider (`openai`, `anthropic`, `openrouter`, `venice`, `kilo-code`, `opencode-go`, `opencode-zen`)
- `BOOK_PRO_MODEL`: default model
- `BOOK_PRO_MAX_CHAPTERS`: optional chapter limit per request (`0`/unset = unlimited)
- `BOOK_PRO_CHAPTER_PARALLEL`: per-book chapter workers (`1` to `8`, default `3`)
- `BOOK_PRO_OUTPUT_DIR`: output root (default `books`)
- `BOOK_PRO_QWEN_TTS_API_KEY`: default Qwen3 TTS key
- `BOOK_PRO_QWEN_TTS_BASE_URL`: default Qwen3 TTS base URL
- `BOOK_PRO_QWEN_TTS_MODEL`: default Qwen3 TTS model
- `BOOK_PRO_MCP_ENABLED`: enable the MCP server (`true`/`false`, default `true`)
- `BOOK_PRO_MCP_PATH`: MCP HTTP mount path (default `/mcp`)
- `BOOK_PRO_MCP_TOKEN`: when set, the MCP HTTP endpoint requires `Authorization: Bearer <token>`
- `BOOK_PRO_MCP_IMPORT_DIR`: when set, MCP agents may import EPUBs by path inside this directory

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
- MCP endpoint (AI agents): <http://127.0.0.1:8000/mcp>
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

### Studio (AI co-writing)

All Studio endpoints live under `/studio`. The web page is at <http://127.0.0.1:8000/studio>.

Create a project, chat with the AI, and finalize chapters:

```bash
curl -X POST "http://127.0.0.1:8000/studio/projects" \
  -H "Content-Type: application/json" \
  -d '{"title": "새 소설", "premise": "도서관의 비밀", "genre": "미스터리", "language": "ko"}'

curl -N -X POST "http://127.0.0.1:8000/studio/projects/book-새-소설/messages/stream" \
  -H "Content-Type: application/json" \
  -d '{"message": "1장을 써 줘", "provider": "open-ai", "model": "gpt-4.1-mini", "api_key": "YOUR_KEY"}'

curl -X POST "http://127.0.0.1:8000/studio/projects/book-새-소설/chapters/finalize" \
  -H "Content-Type: application/json" \
  -d '{"chapter_index": 1, "chapter_title": "시작", "content": "옛날 옛적에..."}'
```

Series, volumes, and the shared setting bible:

```bash
curl -X POST "http://127.0.0.1:8000/studio/series" -H "Content-Type: application/json" -d '{"title": "장편 시리즈"}'
curl -X POST "http://127.0.0.1:8000/studio/series/series-장편-시리즈/volumes" -H "Content-Type: application/json" -d '{"title": "1권", "volume_index": 1}'
curl -X GET  "http://127.0.0.1:8000/studio/series/series-장편-시리즈/bible"
curl -X POST "http://127.0.0.1:8000/studio/series/series-장편-시리즈/bible/finalize" \
  -H "Content-Type: application/json" \
  -d '{"setting_markdown": "# 세계관", "characters": [{"name": "주인공", "markdown": "## 주인공\n용사"}]}'
```

Project management (list / update / delete / chapters / export):

```bash
curl -X GET    "http://127.0.0.1:8000/studio/projects"
curl -X PATCH  "http://127.0.0.1:8000/studio/projects/book-새-소설" -H "Content-Type: application/json" -d '{"genre": "판타지"}'
curl -X DELETE "http://127.0.0.1:8000/studio/projects/book-새-소설"            # moves to books/.trash/
curl -X GET    "http://127.0.0.1:8000/studio/projects/book-새-소설/chapters"
curl -X DELETE "http://127.0.0.1:8000/studio/projects/book-새-소설/chapters/1"
curl -OJ       "http://127.0.0.1:8000/studio/projects/book-새-소설/export?format=epub&include_bible=true"
curl -OJ       "http://127.0.0.1:8000/studio/series/series-장편-시리즈/export?format=markdown"
```

### Studio agentic file tools

With `mode: "auto"`, the agent reads/writes project files itself and streams NDJSON events
(`text_delta`, `tool_call`, `notice`, `error`, `done`):

```bash
curl -N -X POST "http://127.0.0.1:8000/studio/projects/book-새-소설/agent/stream" \
  -H "Content-Type: application/json" \
  -d '{"message": "기존 챕터를 읽고 2장 초안을 써 줘", "mode": "auto", "api_key": "YOUR_KEY"}'
```

- The sandbox is limited to the project directory (and its series directory for volumes).
- Allowed files: `.md`, `.json`, `.txt` (no hidden files; `studio.json`/`series.json` are read-only).
- Every `write`/`edit` keeps a snapshot under `books/<project>/.studio-history/` and deletes go to `books/.trash/`.

```bash
curl -X GET  "http://127.0.0.1:8000/studio/projects/book-새-소설/agent/history"
curl -X POST "http://127.0.0.1:8000/studio/projects/book-새-소설/agent/history/restore" \
  -H "Content-Type: application/json" -d '{"entry_id": "<entry id>"}'
```

With `mode: "approve"`, write/edit/delete calls become pending actions that must be confirmed:

```bash
curl -X GET  "http://127.0.0.1:8000/studio/projects/book-새-소설/agent/actions"
curl -X POST "http://127.0.0.1:8000/studio/projects/book-새-소설/agent/actions/<action_id>/apply"
curl -X POST "http://127.0.0.1:8000/studio/projects/book-새-소설/agent/actions/<action_id>/reject"
```

## 6) MCP Server (AI Agents)

`book-pro` ships an MCP server so AI agents can read books from the library and write books in the Studio.

Two transports share the same tools:

- Streamable HTTP: `http://127.0.0.1:8000/mcp` (mounted inside the FastAPI app, stateless so no session handshake is required)
- stdio: `python -m app.mcp_server` (for local agents that spawn the process themselves)

### Tools

Reading:

| Tool | Description |
| --- | --- |
| `list_books` | List the library (optionally only Studio books) |
| `get_book_overview` | Chapter/character previews + world settings |
| `list_chapters`, `read_chapter_summary` | Chapter summaries (markdown) |
| `read_original_chapter` | Original EPUB text with `offset`/`max_chars` paging |
| `list_characters`, `read_character` | Character profiles |
| `read_world_setting` | World/setting markdown |
| `search_book` | Snippet search over summaries and/or original text |
| `ask_book` | AI Q&A grounded in the book summaries (`book` or `character` mode) |
| `get_reading_progress`, `update_reading_progress` | Remember/resume a reading position |
| `list_provider_models` | Discover models for a provider |

Ingest and summarization (asynchronous):

| Tool | Description |
| --- | --- |
| `import_epub` | Store an EPUB in the library without summarizing it |
| `summarize_epub_start` | Start a background summarization job from base64 or an allowed path |
| `summarize_book_start` | Start summarizing an EPUB already stored in the library |
| `get_upload_progress_state`, `list_active_uploads` | Poll job progress |

Studio (writing books):

| Tool | Description |
| --- | --- |
| `create_studio_project`, `create_studio_series` | Create a single book or a multi-volume series |
| `add_series_volume` | Add a volume (inherits series premise/genre/bible) |
| `list_studio_projects`, `list_studio_series`, `get_studio_project`, `get_studio_series` | Browse projects/series |
| `update_studio_project` | Update project premise/genre/language |
| `studio_chat` | Co-write with the Studio assistant (conversation is persisted) |
| `studio_agent_chat` | Agentic co-writing: the assistant reads/writes project files via file tools before answering |
| `studio_list_files`, `studio_read_file`, `studio_write_file`, `studio_edit_file`, `studio_delete_file` | File tools inside the project sandbox (delete moves to `books/.trash`) |
| `finalize_chapter` | Save a chapter as a finalized markdown file |
| `get_bible`, `save_bible`, `bible_chat` | Manage world settings and character sheets |
| `export_studio_book` | Export a project/series to Markdown or EPUB |
| `delete_studio_project` | Move a project or series to `books/.trash` |

MCP resources (`book://{slug}/overview`, `book://{slug}/chapter/{index}`, `book://{slug}/original/{index}`, `book://{slug}/setting`) and prompts (`read_book_guide`, `write_next_chapter`) are also exposed. Resource URIs must be URI-safe, so books whose slug contains spaces or non-ASCII characters (common for Korean titles) are best read through the tools.

### Client configuration

opencode (`~/.config/opencode/opencode.json`):

```json
{
  "mcp": {
    "book-pro": {
      "type": "remote",
      "url": "http://127.0.0.1:8000/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_TOKEN"
      }
    }
  }
}
```

Claude Code CLI:

```bash
claude mcp add --transport http book-pro http://127.0.0.1:8000/mcp \
  --header "Authorization: Bearer YOUR_MCP_TOKEN"
```

Omit the `Authorization` header/`headers` block when `BOOK_PRO_MCP_TOKEN` is not set.

Claude Desktop (stdio mode):

```json
{
  "mcpServers": {
    "book-pro": {
      "command": "/absolute/path/to/book-pro/.venv/bin/python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/absolute/path/to/book-pro"
    }
  }
}
```

### Security and limits

- Set `BOOK_PRO_MCP_TOKEN` to require a Bearer token on the HTTP endpoint. Without it, the endpoint is open: use it only on a trusted/local network.
- `BOOK_PRO_MCP_IMPORT_DIR` is the only directory agents may read EPUBs from by path. Leave it empty to allow base64 payloads only.
- Set `BOOK_PRO_MCP_ENABLED=false` to disable MCP completely.
- Summarization tools return an `upload_id` immediately; poll `get_upload_progress_state` until `completed`/`failed`. Progress is stored in memory, so it is lost when the server restarts.

## 7) Local vLLM-Omni for Qwen3 TTS

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

## 8) Response Shape (example)

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

## 9) Output Directory Layout

After successful processing, files are stored like:

```text
books/
  book-<title>/
    <uploaded-book>.epub
    studio.json                  (Studio projects only)
    .chapter-digests.json
    .reader-progress.json
    chapter/
      c-<index>-<chapter-title>.md
    character/
      <character-name>.md
    setting.md
    studio/
      conversation.json          (Studio projects only)
      bible.json                 (Studio projects only)
      bible-conversation.json
      pending-actions.json       (approval-mode agent actions)
    .studio-history/             (agentic file snapshots + index.json)
    export/
      <slug>.md / <slug>.epub    (Studio export output)
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
  series-<title>/
    series.json
    setting.md
    character/
      <character-name>.md
    studio/
      bible.json
      bible-conversation.json
    export/
      <slug>.md / <slug>.epub
  .trash/                       (deleted Studio projects/series and files)
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
3. `Publish GHCR image`: build `linux/amd64,linux/arm64` and push to `ghcr.io/<owner>/<repo>`
   - push to `main`/`master` or manual dispatch: `test-latest`, `test-<short-sha>`
   - `v*` tag push or published release: `rc-latest`, `rc-<version>` (+ GitHub Release on tag push)

Pull an image:

```bash
docker pull ghcr.io/pixelzx0/book-pro:test-latest
docker pull ghcr.io/pixelzx0/book-pro:rc-latest
```
