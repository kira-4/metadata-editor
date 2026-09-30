"""Safe writers must not touch the original when verification fails (audit #09)."""
import pytest

from app.metadata_processor import MetadataProcessor, metadata_processor


@pytest.mark.parametrize("ext", [".mp3", ".flac", ".m4a"])
def test_failed_verification_leaves_original_untouched(make_audio, monkeypatch, ext):
    path = make_audio(ext)
    assert metadata_processor.update_metadata_safe(path, title="Before")
    before = path.read_bytes()

    monkeypatch.setattr(MetadataProcessor, "_verify_written_metadata", staticmethod(lambda *_: False))
    assert not metadata_processor.update_metadata_safe(path, title="After")

    assert path.read_bytes() == before
    assert metadata_processor.read_metadata(path)["title"] == "Before"
    assert list(path.parent.iterdir()) == [path]  # temp file cleaned up


@pytest.mark.parametrize("ext", [".mp3", ".flac", ".m4a"])
def test_failed_artwork_verification_leaves_original_untouched(make_audio, monkeypatch, ext):
    path = make_audio(ext)
    before = path.read_bytes()

    monkeypatch.setattr(MetadataProcessor, "read_metadata", staticmethod(lambda *_: {"has_artwork": False}))
    assert not metadata_processor.embed_artwork_safe(path, b"\xff\xd8\xff\xe0fakejpeg", "image/jpeg")

    assert path.read_bytes() == before


@pytest.mark.parametrize("ext", [".mp3", ".flac", ".m4a"])
def test_successful_update_is_applied(make_audio, ext):
    path = make_audio(ext)

    assert metadata_processor.update_metadata_safe(path, title="عنوان", artist="فنان")

    meta = metadata_processor.read_metadata(path)
    assert meta["title"] == "عنوان"
    assert meta["artist"] == "فنان"
