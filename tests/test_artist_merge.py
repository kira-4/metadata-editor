"""Artist spelling variants: grouping and merge (plan S2-9)."""
import pytest

from app.artist_merge import variant_key
from app.config import config
from app.database import LibraryManager, LibraryTrack
from app.library_scanner import LibraryScanner
from app.metadata_processor import metadata_processor


# Real pairs from the library
@pytest.mark.parametrize("a,b", [
    ("الشيخ حسين الأكرف", "الشيخ حسين الاكرف"),
    ("الشيخ مصطفى إسماعيل", "الشيخ مصطفي اسماعيل"),
    ("دانيال بو جبارة", "دانيال بوجبارة"),
    ("السيد شرف الستراوي", "سيد شرف الستراوي"),
    ("كرار ليث البرزنجي", "الحافظ كرار ليث البرزنجي"),
])
def test_real_variants_share_a_key(a, b):
    assert variant_key(a) == variant_key(b)


@pytest.mark.parametrize("a,b", [
    ("حاتم العبدالله", "بسام العبدالله"),
    ("محمد بوجبارة", "دانيال بوجبارة"),
    ("علي غريب", "حسين غريب"),
    ("الشيخ", "السيد"),  # a lone honorific is kept, not stripped to nothing
])
def test_different_artists_never_share_a_key(a, b):
    assert variant_key(a) != variant_key(b)


def _library_track(make_audio, db, folder, title, artist, album_artist=None):
    album_artist = album_artist or artist
    path = make_audio(".mp3", dir=config.NAVIDROME_ROOT / folder / title, name=title)
    assert metadata_processor.update_metadata_safe(
        path, title=title, artist=artist, album=title, album_artist=album_artist
    )
    LibraryScanner()._index_file(db, path, force=True)
    return path


@pytest.fixture
def split_artist(make_audio, db):
    a = _library_track(make_audio, db, "الشيخ حسين الأكرف", "t1", "الشيخ حسين الأكرف")
    b = _library_track(make_audio, db, "الشيخ حسين الأكرف", "t2", "الشيخ حسين الأكرف; ضيف")
    c = _library_track(make_audio, db, "الشيخ حسين الاكرف", "t3", "الشيخ حسين الاكرف")
    other = _library_track(make_audio, db, "حاتم العبدالله", "t4", "حاتم العبدالله")
    return a, b, c, other


def test_variant_groups_suggest_most_used_name(client, split_artist):
    groups = client.get("/api/library/artist-variants").json()["groups"]

    assert len(groups) == 1
    assert groups[0]["suggested"] == "الشيخ حسين الأكرف"
    assert {v["name"] for v in groups[0]["variants"]} == {"الشيخ حسين الأكرف", "الشيخ حسين الاكرف"}


def test_preview_changes_nothing(client, split_artist):
    before = {p: p.read_bytes() for p in split_artist}

    body = client.post("/api/library/artist-merge", json={
        "sources": ["الشيخ حسين الاكرف"], "target": "الشيخ حسين الأكرف"}).json()

    assert body["track_count"] == 1 and body["move_count"] == 1
    assert body["changes"][0]["new_path"].endswith("الشيخ حسين الأكرف/t3/t3.mp3")
    assert all(p.read_bytes() == data for p, data in before.items())


def test_apply_retags_moves_and_reindexes(client, db, split_artist):
    _, _, variant_file, other = split_artist

    body = client.post("/api/library/artist-merge", json={
        "sources": ["الشيخ حسين الاكرف"], "target": "الشيخ حسين الأكرف", "apply": True}).json()

    assert body["results"] == {"successful": 1, "failed": 0, "errors": [], "moved": 1}
    moved = config.NAVIDROME_ROOT / "الشيخ حسين الأكرف" / "t3" / "t3.mp3"
    assert moved.exists() and not variant_file.exists()
    assert not (config.NAVIDROME_ROOT / "الشيخ حسين الاكرف").exists()  # empty folder removed
    meta = metadata_processor.read_metadata(moved)
    assert meta["artist"] == "الشيخ حسين الأكرف"
    assert meta["album_artist"] == "الشيخ حسين الأكرف"
    assert other.exists()
    db.expire_all()
    paths = {t.file_path for t in db.query(LibraryTrack).all()}
    assert str(moved) in paths and str(variant_file) not in paths
    names = [a["name"] for a in LibraryManager.get_all_artists(db)]
    assert "الشيخ حسين الاكرف" not in names


def test_merge_keeps_featured_artists_and_dedupes(client, db, make_audio):
    path = _library_track(make_audio, db, "A", "duet", "A; B; A2", album_artist="A")

    client.post("/api/library/artist-merge", json={"sources": ["A2"], "target": "A", "apply": True})

    assert metadata_processor.read_metadata(path)["artist"] == "A; B"


def test_existing_destination_is_not_overwritten(client, db, make_audio):
    _library_track(make_audio, db, "X", "same", "X")
    variant = _library_track(make_audio, db, "X2", "same", "X2")
    target_file = config.NAVIDROME_ROOT / "X" / "same" / "same.mp3"
    original = target_file.read_bytes()

    body = client.post("/api/library/artist-merge", json={"sources": ["X2"], "target": "X", "apply": True}).json()

    assert body["blocked_count"] == 1
    assert body["results"]["successful"] == 1 and body["results"]["moved"] == 0
    assert target_file.read_bytes() == original
    assert variant.exists()  # retagged in place, not moved
    assert metadata_processor.read_metadata(variant)["artist"] == "X"
