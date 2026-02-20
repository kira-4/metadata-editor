#!/usr/bin/env python3
"""Verify artist suggestion behavior against the local database."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("DATA_DIR", str(WORKSPACE_ROOT / "data"))
sys.path.insert(0, str(WORKSPACE_ROOT))

from app.api import suggest_artists
from app.database import get_db


async def run(query: str, limit: int) -> dict:
    db_gen = get_db()
    db = next(db_gen)
    try:
        return await suggest_artists(q=query, limit=limit, db=db)
    finally:
        db_gen.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify fuzzy artist suggestions.")
    parser.add_argument("--query", required=True, help="Artist query text")
    parser.add_argument("--limit", type=int, default=10, help="Maximum suggestions")
    parser.add_argument(
        "--expect-top",
        default="",
        help="Optional exact expected top suggestion name",
    )
    args = parser.parse_args()

    result = asyncio.run(run(args.query, args.limit))
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.expect_top:
        suggestions = result.get("suggestions") or []
        actual = suggestions[0]["name"] if suggestions else ""
        if actual != args.expect_top:
            print(
                f"\nExpected top suggestion '{args.expect_top}', got '{actual}'",
                file=sys.stderr,
            )
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
