# Second Signal

Second Signal is a hackathon MVP for a personal knowledge-base assistant. Add notes or PDFs,
and the app converts them into canonical Markdown, generated posts, graph concepts,
embeddings, and chat-ready retrieval context.

The implementation uses FastAPI, React/Vite, JSON files, Markdown documents, Claude for enrichment
and chat, and OpenAI embeddings when `OPENAI_API_KEY` is configured.

## Install

```bash
uv sync
cd frontend
npm install
```

## Environment

```bash
export ANTHROPIC_API_KEY="your_claude_key"
export OPENAI_API_KEY="your_openai_key"
```

Both keys are optional for local development. Without `ANTHROPIC_API_KEY`, the backend uses a local
fallback enrichment. Without `OPENAI_API_KEY`, it uses deterministic local embeddings.

## Run

```bash
uv run uvicorn api:app --reload
```

In another terminal:

```bash
cd frontend
npm run dev
```

The frontend defaults to `http://localhost:8000`. Override it with:

```bash
VITE_API_BASE_URL="http://localhost:8000" npm run dev
```

## API

- `POST /sources`
  - multipart or JSON
  - fields: `type=note|pdf`, `title`, `text`, `file`
  - video ingestion is currently disabled and to be fixed
- `GET /sources`
- `GET /sources/{id}`
- `GET /posts`
- `GET /graph`
- `POST /chat` with `{ "message": "..." }`

## Data Layout

```text
data/
  sources.json
  chunks.json
  posts.json
  graph.json
  documents/
    {source_id}.md
```

## CLI Ingestion

```bash
uv run python ingest.py note --title "Transformers" --text "Self-attention connects tokens."
uv run python ingest.py pdf --title "Paper" --file ./paper.pdf
```

Video ingestion is currently disabled and to be fixed.

## Test

```bash
uv run pytest
```
