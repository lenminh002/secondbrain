from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from services.account_service import cleanup_stuck_processing_sources
from routers import chat, misc, sources


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

app.include_router(sources.router)
app.include_router(chat.router)
app.include_router(misc.router)


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
