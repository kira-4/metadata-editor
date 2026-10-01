"""The album artist you see is the one you get (plan S4-3, audit #31)."""
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
        channel="قناة باسم ثاني",  # channel matches the second artist
        extension=".mp3",
        inferred_title="عنوان",
        inferred_artist="أول; باسم ثاني",
        status="pending",
    )
    DatabaseManager.update_item(db, item.id, genre="لطمية")
    return item


def test_confirm_uses_chosen_album_artist(client, staged_item):
    resp = client.post(
        f"/api/pending/{staged_item.id}/confirm",
        json={"title": "عنوان", "artist": "أول; باسم ثاني", "album_artist": "أول", "genre": "لطمية"},
    )

    assert resp.status_code == 200, resp.text
    new_path = Path(resp.json()["new_path"])
    assert new_path.relative_to(config.NAVIDROME_ROOT).parts[0] == "أول"
    assert metadata_processor.read_metadata(new_path)["album_artist"] == "أول"


def test_without_choice_album_artist_is_derived_from_channel(client, staged_item):
    resp = client.post(
        f"/api/pending/{staged_item.id}/confirm",
        json={"title": "عنوان", "artist": "أول; باسم ثاني", "genre": "لطمية"},
    )

    assert resp.status_code == 200, resp.text
    assert Path(resp.json()["new_path"]).relative_to(config.NAVIDROME_ROOT).parts[0] == "باسم ثاني"


def test_album_artist_must_be_a_listed_artist(client, staged_item):
    resp = client.post(
        f"/api/pending/{staged_item.id}/confirm",
        json={"title": "عنوان", "artist": "أول; باسم ثاني", "album_artist": "غريب", "genre": "لطمية"},
    )

    assert resp.status_code == 400
    assert not any(config.NAVIDROME_ROOT.rglob("*.mp3"))


def test_saved_choice_survives_until_artist_list_drops_it(client, db, staged_item):
    client.post(f"/api/pending/{staged_item.id}/update", json={"album_artist": "أول"})
    assert client.post(f"/api/pending/{staged_item.id}/update", json={"title": "جديد"}).json()["album_artist"] == "أول"

    # Re-sending the same list keeps the choice; removing the chosen artist re-derives
    assert client.post(
        f"/api/pending/{staged_item.id}/update", json={"artist": "أول; باسم ثاني"}
    ).json()["album_artist"] == "أول"
    assert client.post(
        f"/api/pending/{staged_item.id}/update", json={"artist": "باسم ثاني"}
    ).json()["album_artist"] == "باسم ثاني"


def test_dry_run_previews_the_draft(client, staged_item):
    resp = client.get(
        f"/api/pending/{staged_item.id}/dry-run",
        params={"title": "مسودة", "artist": "أول; باسم ثاني", "album_artist": "أول"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["metadata_preview"]["album_artist"] == "أول"
    dest = Path(body["move_preview"]["destination_path"])
    assert dest.relative_to(config.NAVIDROME_ROOT).parts[:2] == ("أول", "مسودة")
    assert body["move_preview"]["destination_exists"] is False
