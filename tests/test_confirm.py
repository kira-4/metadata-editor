"""Confirm must apply the draft it is sent, not stale saved values (audit #03)."""
import uuid
from pathlib import Path

import pytest

from app.config import config
from app.database import DatabaseManager
from app.metadata_processor import metadata_processor


@pytest.fixture
def staged_item(db, make_audio):
    staged = make_audio(".mp3", dir=config.STAGING_DIR / str(uuid.uuid4()), name="staged")
    original = config.INCOMING_ROOT / f"{uuid.uuid4()}.mp3"
    original.write_bytes(b"original")
    item = DatabaseManager.create_pending_item(
        db=db,
        original_path=str(original),
        current_path=str(staged),
        video_title="video",
        channel="channel",
        extension=".mp3",
        inferred_title="Old title",
        inferred_artist="Old artist",
        status="pending",
    )
    DatabaseManager.update_item(db, item.id, genre="لطمية")
    return item


def test_confirm_uses_submitted_draft(client, staged_item):
    resp = client.post(
        f"/api/pending/{staged_item.id}/confirm",
        json={"title": "New title", "artist": "فنان أ; فنان ب", "genre": "قصيدة"},
    )

    assert resp.status_code == 200, resp.text
    meta = metadata_processor.read_metadata(resp.json()["new_path"])
    assert meta["title"] == "New title"
    assert "فنان ب" in meta["artist"]
    assert meta["genre"] == "قصيدة"


def test_confirm_without_body_uses_saved_values(client, staged_item):
    resp = client.post(f"/api/pending/{staged_item.id}/confirm")

    assert resp.status_code == 200, resp.text
    assert metadata_processor.read_metadata(resp.json()["new_path"])["title"] == "Old title"


def test_confirm_rejects_invalid_draft_without_moving(client, staged_item):
    resp = client.post(f"/api/pending/{staged_item.id}/confirm", json={"title": "x" * 301})

    assert resp.status_code == 400
    assert not any(config.NAVIDROME_ROOT.rglob("*.mp3"))


def test_confirmed_track_is_indexed_immediately(client, staged_item):
    resp = client.post(
        f"/api/pending/{staged_item.id}/confirm",
        json={"title": "Indexed", "artist": "فنان", "genre": "قصيدة"},
    )
    assert resp.status_code == 200, resp.text

    body = client.get("/api/library/tracks", params={"search": "Indexed"}).json()

    assert body["total"] == 1
    track = body["tracks"][0]
    assert track["file_path"] == resp.json()["new_path"]
    assert track["genre"] == "قصيدة"


DRAFT = {"title": "Dup", "artist": "فنان", "genre": "قصيدة"}


@pytest.fixture
def existing_track():
    from app.mover import FileMover
    path = FileMover.build_destination_path("فنان", "Dup", ".mp3", dedupe=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"old recording")
    return path


def test_existing_destination_asks_first_and_changes_nothing(client, db, staged_item, existing_track):
    staged = staged_item.current_path

    resp = client.post(f"/api/pending/{staged_item.id}/confirm", json=DRAFT)

    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "destination_exists"
    assert existing_track.read_bytes() == b"old recording"
    assert list(existing_track.parent.iterdir()) == [existing_track]
    db.expire_all()
    item = DatabaseManager.get_item_by_id(db, staged_item.id)
    assert item.status == "pending"
    assert item.current_title == "Dup"  # the draft was still saved
    assert Path(staged).exists()


def test_keep_both_adds_numbered_copy(client, staged_item, existing_track):
    resp = client.post(f"/api/pending/{staged_item.id}/confirm", json={**DRAFT, "on_conflict": "keep_both"})

    assert resp.status_code == 200, resp.text
    assert Path(resp.json()["new_path"]).name == "Dup (1).mp3"
    assert existing_track.read_bytes() == b"old recording"


def test_replace_overwrites_existing_file(client, staged_item, existing_track):
    resp = client.post(f"/api/pending/{staged_item.id}/confirm", json={**DRAFT, "on_conflict": "replace"})

    assert resp.status_code == 200, resp.text
    assert Path(resp.json()["new_path"]) == existing_track
    assert existing_track.read_bytes() != b"old recording"
    assert metadata_processor.read_metadata(existing_track)["title"] == "Dup"
    assert list(existing_track.parent.iterdir()) == [existing_track]
