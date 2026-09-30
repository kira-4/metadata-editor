"""Shared test setup: isolate every configured path in a temp dir.

Env vars must be set before any `app.*` import, because `app.config` and the
SQLAlchemy engine read them at import time.
"""
import os
import tempfile
from pathlib import Path

_ROOT = Path(tempfile.mkdtemp(prefix="metadata-editor-tests-"))
os.environ["DATA_DIR"] = str(_ROOT / "data")
os.environ["INCOMING_ROOT"] = str(_ROOT / "incoming")
os.environ["NAVIDROME_ROOT"] = str(_ROOT / "music")
os.environ["OPENROUTER_API_KEY"] = ""

import pytest  # noqa: E402

from app.config import config  # noqa: E402
from app.database import Base, engine, init_db, SessionLocal  # noqa: E402

config.ensure_directories()
config.INCOMING_ROOT.mkdir(parents=True, exist_ok=True)
config.NAVIDROME_ROOT.mkdir(parents=True, exist_ok=True)
init_db()


@pytest.fixture
def db():
    """Fresh database session with empty tables."""
    for table in reversed(Base.metadata.sorted_tables):
        with engine.begin() as conn:
            conn.execute(table.delete())
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    """API client without lifespan (no background scanner)."""
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)
