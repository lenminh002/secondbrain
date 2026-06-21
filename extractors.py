from __future__ import annotations

import re
from io import BytesIO
from typing import Any
from urllib.parse import parse_qs, urlparse


def extract_pdf_text(file_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF support requires the pypdf package. Run `uv sync`.") from exc

    reader = PdfReader(BytesIO(file_bytes))
    text = "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if not text:
        raise ValueError("No readable text was found in this PDF.")
    return text


def extract_youtube_id(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/")
    elif "youtube.com" in parsed.netloc:
        video_id = parse_qs(parsed.query).get("v", [""])[0]
        if not video_id and parsed.path.startswith("/shorts/"):
            video_id = parsed.path.split("/")[2]
    else:
        video_id = url
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,}", video_id or ""):
        raise ValueError("Could not find a valid YouTube video id.")
    return video_id


def fetch_youtube_transcript(url: str) -> str:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as exc:
        raise RuntimeError("YouTube support requires youtube-transcript-api. Run `uv sync`.") from exc

    video_id = extract_youtube_id(url)
    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        transcript = YouTubeTranscriptApi.get_transcript(
            video_id,
            languages=["en", "en-US", "en-GB"],
        )
    else:
        transcript = list(
            YouTubeTranscriptApi().fetch(
                video_id,
                languages=["en", "en-US", "en-GB"],
            )
        )
    lines = []
    for item in transcript:
        if isinstance(item, dict):
            start = float(item.get("start", 0))
            text = str(item.get("text", "")).replace("\n", " ").strip()
        else:
            start = float(getattr(item, "start", 0))
            text = str(getattr(item, "text", "")).replace("\n", " ").strip()
        minutes = int(start // 60)
        seconds = int(start % 60)
        if text:
            lines.append(f"[{minutes:02d}:{seconds:02d}] {text}")
    if not lines:
        raise ValueError("Transcript was empty.")
    return "\n".join(lines)
