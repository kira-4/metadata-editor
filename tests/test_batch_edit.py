"""Batch edit only changes what you touched (plan S4-1, audit #27)."""
import pytest

from app.config import config
from app.database import LibraryManager
from app.library_scanner import LibraryScanner
from app.metadata_processor import metadata_processor


def _track(make_audio, db, title, artist="فنان", album_artist="فنان", genre="لطمية", year=2020, ext=".mp3"):
    path = make_audio(ext, dir=config.NAVIDROME_ROOT / album_artist / title, name=title)
    assert metadata_processor.update_metadata_safe(
        path, title=title, artist=artist, album=title, album_artist=album_artist, genre=genre, year=year
    )
    LibraryScanner()._index_file(db, path, force=True)
    return LibraryManager.get_track_by_path(db, str(path)), path


def _post(client, **body):
    return client.post("/api/library/tracks/batch-update", json=body)


def test_nothing_to_change_is_rejected_without_writes(client, db, make_audio):
    track, path = _track(make_audio, db, "t1")
    before = path.read_bytes()

    resp = _post(client, track_ids=[track.id])

    assert resp.status_code == 400
    assert path.read_bytes() == before


def test_artist_only_edit_leaves_album_artist_alone(client, db, make_audio):
    track, path = _track(make_audio, db, "t1", artist="قديم", album_artist="قديم")

    resp = _post(client, track_ids=[track.id], artist="جديد")

    assert resp.status_code == 200
    assert resp.json()["successful"] == 1
    meta = metadata_processor.read_metadata(path)
    assert meta["artist"] == "جديد"
    assert meta["album_artist"] == "قديم"
    assert meta["genre"] == "لطمية"
    db.expire_all()
    assert LibraryManager.get_track_by_id(db, track.id).album_artist == "قديم"


@pytest.mark.parametrize("ext", [".mp3", ".flac", ".m4a"])
def test_clear_fields_empties_tags_and_db(client, db, make_audio, ext):
    track, path = _track(make_audio, db, "t1", ext=ext)

    resp = _post(client, track_ids=[track.id], clear_fields=["genre", "year"])

    assert resp.status_code == 200, resp.text
    assert resp.json()["successful"] == 1
    meta = metadata_processor.read_metadata(path)
    assert not meta["genre"]
    assert not meta["year"]
    assert meta["title"] == "t1"
    db.expire_all()
    row = LibraryManager.get_track_by_id(db, track.id)
    assert row.genre is None and row.year is None


def test_field_cannot_be_both_set_and_cleared(client, db, make_audio):
    track, _ = _track(make_audio, db, "t1")

    resp = _post(client, track_ids=[track.id], genre="قصيدة", clear_fields=["genre"])

    assert resp.status_code == 422


def test_title_cannot_be_cleared(client, db, make_audio):
    track, _ = _track(make_audio, db, "t1")

    resp = _post(client, track_ids=[track.id], clear_fields=["title"])

    assert resp.status_code == 422


def test_duplicate_ids_are_processed_once(client, db, make_audio):
    track, _ = _track(make_audio, db, "t1")

    resp = _post(client, track_ids=[track.id, track.id, track.id], genre="قصيدة")

    assert resp.json()["total"] == 1
    assert resp.json()["successful"] == 1


def test_batch_size_is_capped(client):
    resp = _post(client, track_ids=list(range(1, 1002)), genre="x")

    assert resp.status_code == 422


def test_per_track_failures_are_reported(client, db, make_audio):
    good, _ = _track(make_audio, db, "t1")
    gone, gone_path = _track(make_audio, db, "t2")
    gone_path.unlink()

    resp = _post(client, track_ids=[good.id, gone.id, 999999], genre="قصيدة")

    body = resp.json()
    assert body["successful"] == 1
    assert body["failed"] == 2
    failed = {e["track_id"]: e for e in body["errors"]}
    assert set(failed) == {gone.id, 999999}
    assert failed[gone.id]["title"] == "t2"
