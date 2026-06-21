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

`.env` and `.env.example` mirror each other key-for-key — fill in the blanks in `.env`.
Run commands from the **repo root**, so relative credential paths like
`./firebase-service-account.json` resolve correctly.

## Credentials Setup

For the default mock-data mode (`SECONDBRAIN_STORAGE_BACKEND=memory`) you need no Google
credentials, and **note** ingestion works fully offline. **PDF** ingestion always uploads the
original file to Google Drive, so it requires Drive credentials regardless of storage backend.
Switching to `firestore` additionally requires Firebase credentials.

All key files go in the **repo root** and are gitignored.

### Google Drive (required for PDF uploads)

The backend uploads each original PDF using a **service account** (scope `drive.file`).

1. **Google Cloud Console** → create or select a project.
2. **APIs & Services → Library** → enable **Google Drive API**.
3. **APIs & Services → Credentials → Create credentials → Service account** → create it.
4. Open the service account → **Keys → Add key → Create new key → JSON**. Note the
   `client_email` inside the downloaded file.
5. Save the file as `google-drive-service-account.json` in the repo root
   (`GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE` already points there). Or paste the JSON into
   `GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON`.
6. Create a Drive folder, copy its ID from the URL (`…/folders/<FOLDER_ID>`), and set
   `GOOGLE_DRIVE_FOLDER_ID`.
7. **Share that folder with the service account's `client_email`** (Editor). This step is
   easy to miss — the service account has no Drive of its own and writes into the folder you
   share with it.

> If you hit a *"service accounts do not have storage quota"* error on a personal Google
> account, point `GOOGLE_DRIVE_FOLDER_ID` at a folder inside a **Shared Drive** (Google
> Workspace). The upload already passes `supportsAllDrives=True`.

### Firebase / Firestore (required when `SECONDBRAIN_STORAGE_BACKEND=firestore`)

1. **Firebase Console** → your project → ⚙ **Project settings → Service accounts** →
   **Generate new private key** → downloads a JSON file.
2. Save it as `firebase-service-account.json` in the repo root
   (`FIREBASE_SERVICE_ACCOUNT_FILE` already points there). Or use
   `FIREBASE_SERVICE_ACCOUNT_JSON` inline, or `FIRESTORE_EMULATOR_HOST` for the local emulator.
3. **Build → Firestore Database → Create database** if Firestore isn't enabled yet.
4. Set `FIREBASE_PROJECT_ID` to your project id and restart the backend.

### AI providers

`ANTHROPIC_API_KEY` and `OPENAI_API_KEY` are optional locally: without the Anthropic key the
backend uses local fallback enrichment (and the agent path is skipped), and without the OpenAI
key it uses deterministic local embeddings.

## Run

```bash
uv run uvicorn api:app --reload --app-dir backend
```

In another terminal:

```bash
cd frontend
npm run dev
```

## Agentic Processing

Second-Brain uses a **Knowledge Librarian Agent** powered by Claude tool calling.

When a PDF is uploaded, the backend starts an agent run. Claude receives a goal and
chooses backend tools such as:

- `inspect_source`
- `extract_pdf_pages`
- `clean_extracted_pages`
- `chunk_clean_pages`
- `embed_and_save_chunks`
- `generate_and_save_memory_posts`
- `build_and_save_graph`
- `finalize_source`

Claude acts as the controller. Python executes the tools. OpenAI creates embeddings.
Firestore stores chunks, vectors, graph data, and agent runs. Memory posts are stored
alongside sources. The deterministic pipeline remains as a fallback (used for notes, and
for PDFs when `AGENT_ENABLED=false` or no `ANTHROPIC_API_KEY` is set).

This gives the app an agentic layer without requiring MCP, LangChain, or any other
orchestration framework — just direct Anthropic tool calling.

Configure via `.env` (see `.env.example`): `AGENT_ENABLED`, `AGENT_MAX_STEPS`,
`AGENT_PROCESSING_MODE`, `AGENT_SAVE_TRACE`.

Agent run status is available at:

- `GET /agent/runs/{run_id}`
- `GET /sources/{source_id}/agent-runs`
- `POST /sources/{source_id}/agent-retry`

Local run:

```bash
uv sync
uv run uvicorn api:app --reload --app-dir backend --port 8000
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
uv run python backend/ingest.py note --account-id "cli-user" --title "Transformers" --text "Self-attention connects tokens."
uv run python backend/ingest.py pdf --account-id "cli-user" --title "Paper" --file ./paper.pdf
```

Video ingestion is currently disabled and to be fixed.

## Test

```bash
uv run pytest
```
