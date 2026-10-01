"""Clearing a field clears it; embedded genre survives import; filenames fit in 255 bytes (plan S4-7, audit #24)."""
import pytest

import app.scanner as scanner_module
from app.config import config
from app.database import LibraryManager, PendingItem
from app.library_scanner import LibraryScanner
from app.metadata_processor import metadata_processor
from app.mover import file_mover
from app.scanner import FileScanner


@pytest.fixture
def track(make_audio, db):
    path = make_audio(".mp3", dir=config.NAVIDROME_ROOT / "a" / "t", name="t")
    assert metadata_processor.update_metadata_safe(
        path, title="t", artist="a", album="t", album_artist="a", genre="لطمية", year=2020
    )
    LibraryScanner()._index_file(db, path, force=True)
    return LibraryManager.get_track_by_path(db, str(path)), path


def _update(client, track_id, **body):
    return client.post(f"/api/library/tracks/{track_id}/update", json=body)


def test_sending_null_clears_year_and_genre(client, db, track):
    row, path = track

    resp = _update(client, row.id, year=None, genre=None)

    assert resp.status_code == 200, resp.text
    meta = metadata_processor.read_metadata(path)
    assert not meta["year"] and not meta["genre"]
    assert meta["title"] == "t"
    db.expire_all()
    assert LibraryManager.get_track_by_id(db, row.id).year is None


def test_sending_empty_string_clears_genre(client, db, track):
    row, path = track

    assert _update(client, row.id, genre="").status_code == 200

    assert not metadata_processor.read_metadata(path)["genre"]


def test_omitted_fields_are_kept(client, db, track):
    row, path = track

    assert _update(client, row.id, title="جديد").status_code == 200

    meta = metadata_processor.read_metadata(path)
    assert meta["title"] == "جديد"
    assert meta["year"] == 2020 and meta["genre"] == "لطمية"
    assert meta["album_artist"] == "a"


def test_artist_edit_does_not_rewrite_album_artist(client, track):
    row, path = track

    assert _update(client, row.id, artist="غيره").status_code == 200

    assert metadata_processor.read_metadata(path)["album_artist"] == "a"


@pytest.mark.parametrize("body", [{"title": ""}, {"artist": "  "}, {"year": -1}, {"year": 10000}, {"title": "x" * 301}])
def test_invalid_values_are_rejected(client, track, body):
    row, path = track
    before = path.read_bytes()

    assert _update(client, row.id, **body).status_code == 422
    assert path.read_bytes() == before


def test_embedded_genre_is_kept_on_the_pending_item(make_audio, monkeypatch, db):
    monkeypatch.setattr(scanner_module, "notify_actionable", lambda *a, **k: None)
    monkeypatch.setattr(FileScanner, "infer_metadata_with_fallback", lambda self, **kw: ("عنوان", "فنان", "فنان", None, "raw"))
    incoming = make_audio(".mp3", dir=config.INCOMING_ROOT, name="title###channel")
    assert metadata_processor.update_metadata_safe(incoming, title="x", artist="y", genre="مواليد")

    FileScanner().process_file(incoming)

    assert db.query(PendingItem).one().genre == "مواليد"


def test_long_arabic_title_fits_in_255_bytes(tmp_path):
    title = "قصيدة " * 60  # ~660 UTF-8 bytes

    dest = file_mover.build_destination_path("فنان " * 60, title, ".m4a")

    for part in dest.relative_to(config.NAVIDROME_ROOT).parts:
        assert len(part.encode("utf-8")) <= 255
    assert dest.name.endswith(".m4a")
    assert "�" not in str(dest)  # never cut inside a character


def test_long_title_still_leaves_room_for_collision_suffix(make_audio):
    title = "ع" * 200  # 400 bytes
    first = file_mover.build_destination_path("فنان", title, ".mp3")
    first.parent.mkdir(parents=True)
    first.write_bytes(b"x")

    second = file_mover.build_destination_path("فنان", title, ".mp3")

    assert second != first
    assert len(second.name.encode("utf-8")) <= 255
