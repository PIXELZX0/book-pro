# book-pro Skill

`book-pro` is an API server for uploading EPUB files, generating structured AI summaries, and reading the original text.

## Base URL

- Local default: `http://127.0.0.1:8000`

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

6. `GET /uploads/active`
- List active uploads (`queued` or `processing`)

7. `GET /books?page=1&page_size=10`
- List stored books

8. `GET /books/{book_slug}`
- Get stored summary detail (`chapter`, `character`, `setting` markdown)

9. `GET /books/{book_slug}/reader`
- Re-parse stored original EPUB and return readable chapter text

10. `GET /skill.md`
- Returns this skill document for agent integration

## Minimal Agent Flow

1. Call `POST /providers/models` to discover available models for the selected provider
2. Call `POST /summaries/from-epub` with an `upload_id`
3. Poll `GET /uploads/{upload_id}/progress` until completion
4. Call `GET /books` and `GET /books/{slug}` for saved summary outputs
5. Call `GET /books/{slug}/reader` when original chapter text is needed
