"""Rescan must be read-only by default; repair must index what it saved (audit #10)."""
import pytest
from mutagen import File as MutagenFile

from app.config import config
from app.database import LibraryManager
from app.library_scanner import LibraryScanner
from app.metadata_processor import metadata_processor


def _untagged(make_audio, ext):
    path = make_audio(ext, dir=config.NAVIDROME_ROOT / "Artist" / "Album", name="song")
    audio = MutagenFile(path)
    if audio.tags is not None:
        audio.delete()
    return path


@pytest.mark.parametrize("ext", [".mp3", ".flac", ".m4a"])
def test_rescan_does_not_modify_files(make_audio, db, ext):
    path = _untagged(make_audio, ext)
    before = path.read_bytes()

    LibraryScanner()._index_file(db, path, force=True)

    assert path.read_bytes() == before
    track = LibraryManager.get_track_by_path(db, str(path))
    assert track.title == "song"  # path-inferred display fallback


@pytest.mark.parametrize("ext", [".mp3", ".flac", ".m4a"])
def test_repair_writes_tags_and_index_matches_file(make_audio, db, ext):
    path = _untagged(make_audio, ext)

    LibraryScanner()._index_file(db, path, force=True, repair=True)

    on_disk = metadata_processor.read_metadata(path)
    track = LibraryManager.get_track_by_path(db, str(path))
    assert on_disk["title"] == "song"
    assert on_disk["album"] == "Album"
    assert track.title == on_disk["title"]
    assert track.album == on_disk["album"]
