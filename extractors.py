from __future__ import annotations

from io import BytesIO


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

