"""Regression tests for DELETE /api/pending/{id} (audit #01)."""
import uuid

from app.config import config
from app.database import DatabaseManager


def _make_item(db, status="pending"):
    staging_dir = config.STAGING_DIR / str(uuid.uuid4())
    staging_dir.mkdir(parents=True)
    staged = staging_dir / "song.mp3"
    staged.write_bytes(b"staged")
    original = config.INCOMING_ROOT / f"{uuid.uuid4()}.mp3"
    original.write_bytes(b"original")
    item = DatabaseManager.create_pending_item(
        db=db,
        original_path=str(original),
        current_path=str(staged),
        video_title="song",
        channel="channel",
        extension=".mp3",
        status=status,
    )
    return item, staged, original


def test_delete_pending_removes_staged_and_original(client, db):
    item, staged, original = _make_item(db)

    resp = client.delete(f"/api/pending/{item.id}")

    assert resp.status_code == 200
    assert not staged.exists()
    assert not staged.parent.exists()
    assert not original.exists()


def test_delete_done_item_is_rejected_and_library_file_kept(client, db):
    item, _, _ = _make_item(db)
    library_file = config.NAVIDROME_ROOT / "artist" / "song" / "song.mp3"
    library_file.parent.mkdir(parents=True, exist_ok=True)
    library_file.write_bytes(b"library")
    DatabaseManager.mark_as_done(db, item.id, str(library_file))

    resp = client.delete(f"/api/pending/{item.id}")

    assert resp.status_code == 409
    assert library_file.exists()
    db.expire_all()
    assert DatabaseManager.get_item_by_id(db, item.id) is not None


def test_delete_never_unlinks_outside_staging(client, db):
    item, _, _ = _make_item(db)
    outside = config.NAVIDROME_ROOT / "stray.mp3"
    outside.write_bytes(b"library")
    item.current_path = str(outside)
    db.commit()

    resp = client.delete(f"/api/pending/{item.id}")

    assert resp.status_code == 200
    assert outside.exists()


def test_delete_missing_item_returns_404(client):
    resp = client.delete("/api/pending/999999")

    assert resp.status_code == 404
