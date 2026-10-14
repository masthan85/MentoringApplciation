"""Load the repository's /content/sources into the Mentor Encyclopedia.

Run from apps/api:  uv run python scripts/ingest_content.py [--activate]

Documents are embedded with the configured embeddings route (OpenAI by default). Without a key
they are stored without vectors and retrieved by full-text search only; run it again later, or use
the admin page, to add vectors. Content that the scan flagged stays a draft until an admin
activates it, even with --activate.
"""

import argparse
import asyncio
from pathlib import Path

from app.core.db import dispose_engine, session_scope
from app.modules.encyclopedia.ingestion import ingest_document

CONTENT = Path(__file__).resolve().parents[3] / "content" / "sources"


async def main(activate: bool) -> None:
    for path in sorted(CONTENT.glob("*.md")):
        async with session_scope(admin=True) as session:
            report = await ingest_document(session, path.read_text(), activate=activate)
        note = (
            "unchanged"
            if report.unchanged
            else f"{report.chunks} chunks, {report.embedded} embedded"
        )
        flags = f"  FLAGS: {', '.join(report.findings)}" if report.findings else ""
        print(f"{report.slug:36} {report.status:8} {note}{flags}")
    await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--activate", action="store_true", help="make clean sources available straight away"
    )
    asyncio.run(main(parser.parse_args().activate))
