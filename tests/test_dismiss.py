"""Deleting a pending item keeps the original in trash, recoverable (finding N4)."""
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import app.api as api_module
import app.scanner as scanner_module
from app.config import config
from app.database import DatabaseManager, PendingItem
from app.scanner import FileScanner


def _make_item(db, name="title###channel.mp3"):
    staging_dir = config.STAGING_DIR / str(uuid.uuid4())
    staging_dir.mkdir(parents=True)
    staged = staging_dir / name
    staged.write_bytes(b"staged")
    original = config.INCOMING_ROOT / name
    original.write_bytes(b"original")
    item = DatabaseManager.create_pending_item(
        db=db, original_path=str(original), current_path=str(staged),
        video_title="title", channel="channel", extension=".mp3", status="pending",
    )
    return item, staged, original


def test_delete_moves_original_to_trash_and_dismisses(client, db):
    item, staged, original = _make_item(db)

    resp = client.delete(f"/api/pending/{item.id}")

    assert resp.status_code == 200
    trashed = config.TRASH_DIR / str(item.id) / original.name
    assert trashed.read_bytes() == b"original"
    assert not original.exists()
    assert not staged.parent.exists()
    db.expire_all()
    row = DatabaseManager.get_item_by_id(db, item.id)
    assert row.status == "dismissed"
    assert row.current_path == str(trashed)
    assert all(i["id"] != item.id for i in client.get("/api/pending").json())


def test_failed_trash_move_changes_nothing(client, db, monkeypatch):
    item, staged, original = _make_item(db)

    def fail(*a, **k):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(api_module.shutil, "move", fail)

    resp = client.delete(f"/api/pending/{item.id}")

    assert resp.status_code == 500
    assert original.exists() and staged.exists()
    db.expire_all()
    assert DatabaseManager.get_item_by_id(db, item.id).status == "pending"


def test_restored_file_is_imported_again(client, db, make_audio, monkeypatch):
    monkeypatch.setattr(scanner_module, "notify_actionable", lambda *a, **k: None)
    monkeypatch.setattr(
        FileScanner, "infer_metadata_with_fallback",
        lambda self, **kw: ("عنوان", "فنان", "فنان", None, "raw"),
    )
    scanner = FileScanner()
    incoming = make_audio(".mp3", dir=config.INCOMING_ROOT, name="title###channel")
    scanner.process_file(incoming)
    item = db.query(PendingItem).one()
    assert client.delete(f"/api/pending/{item.id}").status_code == 200

    # Restore = move the file back from trash
    shutil.move(str(config.TRASH_DIR / str(item.id) / incoming.name), str(incoming))
    scanner.process_file(incoming)

    db.expire_all()
    statuses = [i.status for i in db.query(PendingItem).all()]
    assert statuses.count("pending") == 1


def test_redownloaded_file_clears_stale_trash(client, db, make_audio, monkeypatch):
    # Pinchflat re-downloads a dismissed file: the trashed copy must not be orphaned
    monkeypatch.setattr(scanner_module, "notify_actionable", lambda *a, **k: None)
    monkeypatch.setattr(
        FileScanner, "infer_metadata_with_fallback",
        lambda self, **kw: ("عنوان", "فنان", "فنان", None, "raw"),
    )
    scanner = FileScanner()
    incoming = make_audio(".mp3", dir=config.INCOMING_ROOT, name="title###channel")
    scanner.process_file(incoming)
    item = db.query(PendingItem).one()
    client.delete(f"/api/pending/{item.id}")
    make_audio(".mp3", dir=config.INCOMING_ROOT, name="title###channel")

    scanner.process_file(incoming)

    assert not (config.TRASH_DIR / str(item.id)).exists()


def test_purge_removes_only_expired_trash(client, db):
    old, _, _ = _make_item(db, "old###channel.mp3")
    new, _, _ = _make_item(db, "new###channel.mp3")
    client.delete(f"/api/pending/{old.id}")
    client.delete(f"/api/pending/{new.id}")
    db.query(PendingItem).filter(PendingItem.id == old.id).update(
        {"updated_at": datetime.now(timezone.utc) - timedelta(days=config.TRASH_RETENTION_DAYS + 1)},
        synchronize_session=False,
    )
    db.commit()

    purged = DatabaseManager.purge_expired_trash(db)

    assert purged == 1
    assert not (config.TRASH_DIR / str(old.id)).exists()
    assert (config.TRASH_DIR / str(new.id) / "new###channel.mp3").exists()
    db.expire_all()
    assert DatabaseManager.get_item_by_id(db, old.id) is None
    assert DatabaseManager.get_item_by_id(db, new.id).status == "dismissed"


def test_scanner_purges_trash_at_most_hourly(monkeypatch):
    calls = []
    monkeypatch.setattr(DatabaseManager, "purge_expired_trash", staticmethod(lambda db: calls.append(1) or 0))
    scanner = FileScanner()

    scanner.purge_trash_if_due()
    scanner.purge_trash_if_due()

    assert len(calls) == 1
