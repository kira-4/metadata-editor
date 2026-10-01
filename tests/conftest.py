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


@pytest.fixture(autouse=True)
def clean_dirs():
    """Every test starts with empty incoming/staging/library dirs."""
    import shutil

    for d in (config.INCOMING_ROOT, config.STAGING_DIR, config.NAVIDROME_ROOT, config.TRASH_DIR):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)


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


_CODECS = {".mp3": ["libmp3lame", "-b:a", "128k"], ".flac": ["flac"], ".m4a": ["aac", "-b:a", "128k"]}


@pytest.fixture
def make_audio(tmp_path):
    """Factory: make_audio(".mp3", dir=None) -> Path to a 1s generated audio file."""
    import shutil
    import subprocess

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg not available")

    def _make(ext=".mp3", dir=None, name="track"):
        target_dir = Path(dir) if dir else tmp_path
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{name}{ext}"
        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=1", "-c:a", *_CODECS[ext], str(path)],
            check=True, capture_output=True,
        )
        return path

    return _make
