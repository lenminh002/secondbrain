# SecondBrain

SecondBrain is a hackathon MVP for a personal knowledge-base assistant. Add notes or PDFs,
and the app converts them into canonical Markdown, generated posts, graph concepts,
embeddings, and chat-ready retrieval context.

The implementation uses FastAPI, React/Vite, in-memory mock storage by default,
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
```

Both keys are optional for local development. Without `ANTHROPIC_API_KEY`, the backend uses a local
fallback enrichment. Without `OPENAI_API_KEY`, it uses deterministic local embeddings.
No login or Firebase setup is required for the default mock-data mode. PDF ingestion requires
Google Drive upload configuration because the original PDF is stored in Drive and linked from
source metadata.

Copy `.env.example` to `.env` if you want file-based local configuration:

```bash
cp .env.example .env
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

- `POST /sources`
  - multipart or JSON
  - fields: `type=note|pdf`, `title`, `text`, `file`
- `GET /sources`
- `GET /sources/{id}`
- `GET /account`
- `GET /posts`
- `GET /graph`
- `POST /chat` with `{ "message": "..." }`

## Storage

The backend defaults to seeded in-memory mock data. Set
`SECONDBRAIN_STORAGE_BACKEND=firestore` only if you intentionally want to use the optional
Firestore backend.

Original PDF uploads are stored in Google Drive before text extraction. Create a Google Cloud
service account with Drive API access, create or choose a Drive folder, share that folder with
the service account email, then configure:

```bash
GOOGLE_DRIVE_FOLDER_ID="your-drive-folder-id"
GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE="/absolute/path/to/drive-service-account.json"
# or:
GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
```

The backend stores the restricted Drive `webViewLink` as `source_url` and as
`metadata.original_file.drive_web_view_link`. It does not make uploaded files public; users need
Drive permission to open the original PDF link.

To store ingested sources, chunks, generated posts, graph nodes, and graph edges in Firebase
Firestore, create a Firebase project with Firestore enabled, create a service account JSON
key, then configure:

```bash
SECONDBRAIN_STORAGE_BACKEND=firestore
FIREBASE_PROJECT_ID="your-firebase-project-id"
FIREBASE_SERVICE_ACCOUNT_FILE="/absolute/path/to/service-account.json"
```

For hosted environments where mounting a JSON file is awkward, set
`FIREBASE_SERVICE_ACCOUNT_JSON` to the full service account JSON string instead of
`FIREBASE_SERVICE_ACCOUNT_FILE`.

For local emulator development:

```bash
SECONDBRAIN_STORAGE_BACKEND=firestore
FIREBASE_PROJECT_ID="secondbrain-local"
FIRESTORE_EMULATOR_HOST="127.0.0.1:8080"
```

Firestore collections used by the backend are `accounts`, `sources`, `chunks`, `posts`, and
`graphs`. Each ingested record is scoped by `account_id`; the MVP currently uses the mock
account id `mock-user`.

## CLI Ingestion

```bash
uv run python ingest.py note --account-id "cli-user" --title "Transformers" --text "Self-attention connects tokens."
uv run python ingest.py pdf --account-id "cli-user" --title "Paper" --file ./paper.pdf
```

## Test

```bash
uv run pytest
```
