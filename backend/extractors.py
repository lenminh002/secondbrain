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


def scrape_url_to_html(url: str) -> str:
    import httpx

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    scrape_url = url
    # Handle Twitter/X links by attempting to fetch from a public Nitter instance first
    if "x.com" in url or "twitter.com" in url:
        scrape_url = url.replace("x.com", "nitter.privacydev.net").replace("twitter.com", "nitter.privacydev.net")

    try:
        with httpx.Client(follow_redirects=True, timeout=20) as client:
            response = client.get(scrape_url, headers=headers)
            response.raise_for_status()
            return response.text
    except Exception as exc:
        # Fallback to the original URL if Nitter/replacement failed
        if scrape_url != url:
            try:
                with httpx.Client(follow_redirects=True, timeout=20) as client:
                    response = client.get(url, headers=headers)
                    response.raise_for_status()
                    return response.text
            except Exception:
                pass
        raise RuntimeError(f"Failed to scrape webpage content: {exc}")


