# SecondBrain

SecondBrain is a hackathon MVP for a personal knowledge-base assistant. Add notes or PDFs,
and the app converts them into canonical Markdown, generated posts, graph concepts,
embeddings, and chat-ready retrieval context.

The implementation uses FastAPI, React/Vite, Firebase Auth, Firebase Cloud Firestore,
Claude for enrichment and chat, and OpenAI embeddings when `OPENAI_API_KEY` is configured.

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
export FIREBASE_SERVICE_ACCOUNT_FILE="/path/to/firebase-service-account.json"
```

Both keys are optional for local development. Without `ANTHROPIC_API_KEY`, the backend uses a local
fallback enrichment. Without `OPENAI_API_KEY`, it uses deterministic local embeddings.
Firebase credentials are required for the backend storage layer and Firebase ID token
verification. You can also set `GOOGLE_APPLICATION_CREDENTIALS` instead of
`FIREBASE_SERVICE_ACCOUNT_FILE`.

The frontend also needs Firebase web app config for Google sign-in. Copy
`frontend/.env.example` to `frontend/.env.local` and fill in:

```bash
VITE_FIREBASE_API_KEY="your_firebase_web_api_key"
VITE_FIREBASE_AUTH_DOMAIN="your_project.firebaseapp.com"
VITE_FIREBASE_PROJECT_ID="your_project_id"
VITE_FIREBASE_APP_ID="your_firebase_web_app_id"
```

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

All API endpoints require `Authorization: Bearer <Firebase ID token>`.

- `POST /sources`
  - multipart or JSON
  - fields: `type=note|pdf`, `title`, `text`, `file`
  - video ingestion is currently disabled and to be fixed
- `GET /sources`
- `GET /sources/{id}`
- `GET /account`
- `GET /posts`
- `GET /graph`
- `POST /chat` with `{ "message": "..." }`

## Firestore Layout

```text
accounts/{account_id}
sources/{source_id}
posts/{post_id}
chunks/{chunk_id}
documents/{source_id}
graphs/{account_id}
```

## CLI Ingestion

```bash
uv run python ingest.py note --account-id "cli-user" --title "Transformers" --text "Self-attention connects tokens."
uv run python ingest.py pdf --account-id "cli-user" --title "Paper" --file ./paper.pdf
```

Video ingestion is currently disabled and to be fixed.

## Test

```bash
uv run pytest
```
