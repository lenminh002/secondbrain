from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import sys

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
else:
    repo_root = Path(__file__).resolve().parents[1]

load_dotenv()

from backend.services.account_service import cleanup_stuck_processing_sources
from backend.services.auth_middleware import FirebaseAuthMiddleware
from backend.routers import chat, misc, sources
from backend.embeddings import embed_text
from backend.services.chat.llm import answer_with_tools


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_stuck_processing_sources()
    yield


app = FastAPI(title="Personal Knowledge Base API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(FirebaseAuthMiddleware)

app.include_router(sources.router)
app.include_router(chat.router)
app.include_router(misc.router)


if __name__ == "__main__":
    uvicorn.run(
        "backend.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        app_dir=str(repo_root),
    )
