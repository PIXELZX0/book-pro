# book-pro Skill

`book-pro` is an API server for uploading EPUB files, generating structured AI summaries, and reading the original text.

It also exposes an MCP server so AI agents can read books and write books in the Studio.

## Interfaces

- REST API base URL (local default): `http://127.0.0.1:8000`
- MCP streamable HTTP endpoint: `http://127.0.0.1:8000/mcp`
- MCP stdio entry point: `python -m app.mcp_server` (same tools, for local agents)

If you are an MCP client, prefer the MCP tools listed at the bottom of this document.

## Core Capabilities

- Run summarization automatically after EPUB upload
- Generate chapter summaries, character summaries, world summaries, and writing-style analysis
- Support precise analysis mode (chapter-level character traits + dialogue-based inferences)
- Process multiple books in parallel
- Persist output files in this structure:
  - `books/book-[book-title]/chapter/c-[chapter-number]-[chapter-title].md`
  - `books/book-[book-title]/character/[character-name].md`
  - `books/book-[book-title]/setting.md`
  - `books/book-[book-title]/*.epub` (original EPUB copy)

## Providers

- `open-ai`
- `anthropic`
- `openrouter`
- `venice`
- `kilo-code`
- `opencode-go`
- `opencode-zen`

Provider, model, and API key can be passed per request via multipart form fields, or read from server defaults in `.env`.

## Important Endpoints

1. `GET /health`
- Health check endpoint

2. `POST /providers/models`
- Form fields: `provider`, `api_key` (optional)
- Fetches provider model list dynamically

3. `POST /summaries/from-epub`
- Form fields:
  - `file` (`.epub`)
  - `upload_id` (optional, recommended for progress polling)
  - `provider`, `api_key`, `model` (optional)
  - `language` (default `ko`)
  - `precise_analysis` (`true|false`)
  - `max_chapters` (optional, unlimited if omitted)

4. `POST /summaries/from-epubs`
- Multi-file summarization endpoint
- Form fields:
  - `files` (multiple)
  - `provider`, `api_key`, `model` (optional)
  - `language` (default `ko`)
  - `precise_analysis` (`true|false`)
  - `max_chapters` (optional)
  - `max_parallel` (optional)

5. `GET /uploads/{upload_id}/progress`
- Get single upload progress

6. `GET /uploads/{upload_id}/stream`
- Server-Sent Events stream of live summarization output
- Events: `progress` (stage/progress snapshot), `chapter` (chapter summary as soon as it is generated), `done`/`failed` (terminal), `timeout`
- Resumable with the `Last-Event-ID` header

7. `GET /uploads/active`
- List active uploads (`queued` or `processing`)

8. `GET /books?page=1&page_size=10`
- List stored books

9. `GET /books/{book_slug}`
- Get stored summary detail (`chapter`, `character`, `setting` markdown)

10. `GET /books/{book_slug}/reader`
- Re-parse stored original EPUB and return readable chapter text

11. `GET /skill.md`
- Returns this skill document for agent integration

## Minimal Agent Flow

1. Call `POST /providers/models` to discover available models for the selected provider
2. Call `POST /summaries/from-epub` with an `upload_id`
3. Poll `GET /uploads/{upload_id}/progress` until completion, or follow
   `GET /uploads/{upload_id}/stream` (SSE) to see chapter summaries as they are generated
4. Call `GET /books` and `GET /books/{slug}` for saved summary outputs
5. Call `GET /books/{slug}/reader` when original chapter text is needed

## MCP Tools

Reading:
- `list_books`, `get_book_overview`, `list_chapters`, `read_chapter_summary`
- `read_original_chapter`, `list_characters`, `read_character`, `read_world_setting`
- `search_book`, `ask_book`, `get_reading_progress`, `update_reading_progress`
- `list_provider_models`

Ingest and summarization (asynchronous):
- `import_epub`
- `summarize_epub_start`, `summarize_book_start`
- `get_upload_progress_state`, `list_active_uploads`

Studio (writing books):
- `create_studio_project`, `create_studio_series`, `add_series_volume`
- `list_studio_projects`, `list_studio_series`, `get_studio_project`, `get_studio_series`
- `studio_chat`, `finalize_chapter`
- `get_bible`, `save_bible`, `bible_chat`

MCP resources: `book://{slug}/overview`, `book://{slug}/chapter/{index}`, `book://{slug}/original/{index}`, `book://{slug}/setting`
MCP prompts: `read_book_guide`, `write_next_chapter`

### Minimal MCP Flow

1. Call `list_books` (or `import_epub` + `summarize_book_start` for a new EPUB) to get a `slug`
2. Call `get_book_overview`, then `read_chapter_summary` / `read_original_chapter` to read
3. Call `ask_book` for questions that need whole-book reasoning
4. To write: `create_studio_project` (or `create_studio_series` + `add_series_volume`) → `studio_chat` → `finalize_chapter`
5. Manage world settings and characters with `get_bible` / `bible_chat` / `save_bible`

Notes:
- Summarization is asynchronous: start it, then poll `get_upload_progress_state` until `completed` or `failed`
- EPUB import by file path requires `BOOK_PRO_MCP_IMPORT_DIR`; otherwise send base64 content
- Resource URIs require URI-safe slugs, so prefer the tools for books with Korean or spaced titles
