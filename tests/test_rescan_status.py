"""Rescan: one scan at a time, honest status, no deletes after a partial walk (plan S4-2, audit #23)."""
import os
import threading

import pytest

from app.config import config
from app.database import LibraryManager
from app.library_scanner import LibraryScanner, library_scanner
from app.metadata_processor import metadata_processor


@pytest.fixture
def blocked_scan(monkeypatch):
    """Make the scan thread wait until released, so 'scanning' state can be observed."""
    release = threading.Event()
    monkeypatch.setattr(LibraryScanner, "_scan_library", lambda self, *a, **k: release.wait(5))
    yield release
    release.set()
    if library_scanner.scan_thread:
        library_scanner.scan_thread.join(5)
    library_scanner.is_scanning = False


def test_scanning_flag_is_set_before_start_returns(blocked_scan):
    scanner = LibraryScanner()

    assert scanner.start_scan() is True
    assert scanner.is_scanning is True
    assert scanner.start_scan() is False

    blocked_scan.set()
    scanner.scan_thread.join(5)


def test_concurrent_starts_produce_one_scan(blocked_scan):
    scanner = LibraryScanner()
    results = []
    barrier = threading.Barrier(8)

    def start():
        barrier.wait()
        results.append(scanner.start_scan())

    threads = [threading.Thread(target=start) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count(True) == 1
    blocked_scan.set()
    scanner.scan_thread.join(5)


def test_second_rescan_request_is_409(client, blocked_scan):
    assert client.post("/api/library/rescan").status_code == 200
    assert client.post("/api/library/rescan").status_code == 409
    assert client.get("/api/library/rescan/status").json()["is_scanning"] is True


def test_status_reports_counts_and_finish_time(make_audio, db):
    make_audio(".mp3", dir=config.NAVIDROME_ROOT / "a" / "b", name="one")
    scanner = LibraryScanner()

    scanner._scan_library()
    status = scanner.get_status()

    assert status["is_scanning"] is False
    assert status["total"] == 1 and status["processed"] == 1
    assert status["errors"] == []
    assert status["started_at"] and status["finished_at"]
    assert status["finished_at"] >= status["started_at"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_unreadable_directory_never_causes_index_deletion(make_audio, db):
    keep = make_audio(".mp3", dir=config.NAVIDROME_ROOT / "a" / "x", name="one")
    hidden = make_audio(".mp3", dir=config.NAVIDROME_ROOT / "b" / "y", name="two")
    for p in (keep, hidden):
        assert metadata_processor.update_metadata_safe(p, title=p.stem, artist="a")
        LibraryScanner()._index_file(db, p, force=True)
    locked = config.NAVIDROME_ROOT / "b"
    locked.chmod(0)
    try:
        scanner = LibraryScanner()
        scanner._scan_library(force_full=True)
    finally:
        locked.chmod(0o755)

    db.expire_all()
    assert LibraryManager.get_track_by_path(db, str(hidden)) is not None
    assert any("b" in e for e in scanner.get_status()["errors"])


def test_quick_scan_drops_files_moved_outside_the_app(make_audio, db):
    old = make_audio(".mp3", dir=config.NAVIDROME_ROOT / "audio" / "a" / "x", name="one")
    assert metadata_processor.update_metadata_safe(old, title="one", artist="a")
    LibraryScanner()._index_file(db, old, force=True)
    new = config.NAVIDROME_ROOT / "a" / "x" / "one.mp3"
    new.parent.mkdir(parents=True)
    old.rename(new)

    LibraryScanner()._scan_library()  # the rescan button: no force

    db.expire_all()
    assert LibraryManager.get_track_by_path(db, str(old)) is None
    assert LibraryManager.get_track_by_path(db, str(new)) is not None
