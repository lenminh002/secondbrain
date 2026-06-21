from __future__ import annotations

import argparse
import json
from pathlib import Path

from ingestion import ingest_source


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a source into the knowledge base.")
    parser.add_argument("type", choices=["note", "pdf"])
    parser.add_argument("--title", default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--url", default=None)
    parser.add_argument("--file", default=None)
    parser.add_argument("--account-id", default="cli-user")
    args = parser.parse_args()

    file_bytes = None
    filename = None
    if args.file:
        path = Path(args.file)
        file_bytes = path.read_bytes()
        filename = path.name

    source = ingest_source(
        account_id=args.account_id,
        source_type=args.type,
        title=args.title,
        text=args.text,
        source_url=args.url,
        file_bytes=file_bytes,
        filename=filename,
    )
    print(json.dumps(source, indent=2))


if __name__ == "__main__":
    main()
