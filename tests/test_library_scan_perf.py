"""Tests for library scan performance optimizations."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_collect_audio_files_finds_all_extensions():
    """Single-pass walk finds .mp3, .m4a, .flac, .ogg files."""
    from app.library_scanner import LibraryScanner

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "sub").mkdir()
        (root / "sub" / "song.mp3").write_bytes(b"\x00")
        (root / "sub" / "song.m4a").write_bytes(b"\x00")
        (root / "sub" / "song.flac").write_bytes(b"\x00")
        (root / "sub" / "song.ogg").write_bytes(b"\x00")
        (root / "sub" / "readme.txt").write_bytes(b"\x00")

        exts = {".mp3", ".m4a", ".flac", ".ogg"}
        result = LibraryScanner._collect_audio_files(root, exts)
        assert len(result) == 4
        suffixes = {p.suffix.lower() for p in result}
        assert suffixes == exts


def test_collect_audio_files_walks_all_directories():
    """All directories are walked regardless of mtime."""
    from app.library_scanner import LibraryScanner

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        sub = root / "artist"
        sub.mkdir()
        (sub / "song.mp3").write_bytes(b"\x00")

        result = LibraryScanner._collect_audio_files(root, {".mp3"})
        assert len(result) == 1


def test_cleanup_missing_files_set_based():
    """Tracks not in the scanned set are removed from DB."""
    from app.library_scanner import LibraryScanner
    from app.database import LibraryTrack, Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    track1 = LibraryTrack(file_path="/music/artist1/album1/song1.mp3", title="Song 1")
    track2 = LibraryTrack(file_path="/music/artist1/album1/song2.mp3", title="Song 2")
    track3 = LibraryTrack(file_path="/music/artist2/album2/song3.mp3", title="Song 3")
    db.add_all([track1, track2, track3])
    db.commit()

    scanner = LibraryScanner()
    scanner._cleanup_missing_files(db, {"/music/artist1/album1/song1.mp3", "/music/artist2/album2/song3.mp3"})

    remaining = db.query(LibraryTrack).all()
    paths = {t.file_path for t in remaining}
    assert "/music/artist1/album1/song1.mp3" in paths
    assert "/music/artist1/album1/song2.mp3" not in paths
    assert "/music/artist2/album2/song3.mp3" in paths
