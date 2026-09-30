"""Moves into the library must never expose a partial file (N1)."""
import errno
import os
import shutil

import pytest

from app.config import config
from app.mover import FileMover


def _cross_device(monkeypatch):
    def fake_rename(src, dst):
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(os, "rename", fake_rename)


def _source(tmp_path):
    src = tmp_path / "staged.mp3"
    src.write_bytes(b"audio-bytes" * 1000)
    return src


def _library_files():
    return sorted(p.name for p in config.NAVIDROME_ROOT.rglob("*") if p.is_file())


@pytest.fixture(autouse=True)
def clean_library():
    shutil.rmtree(config.NAVIDROME_ROOT, ignore_errors=True)
    config.NAVIDROME_ROOT.mkdir(parents=True)


def test_same_filesystem_move(tmp_path):
    src = _source(tmp_path)
    data = src.read_bytes()

    dest = FileMover.move_to_navidrome(src, "فنان", "عنوان", ".mp3")

    assert dest.read_bytes() == data
    assert not src.exists()


def test_cross_device_move_copies_then_renames(tmp_path, monkeypatch):
    src = _source(tmp_path)
    data = src.read_bytes()
    _cross_device(monkeypatch)

    dest = FileMover.move_to_navidrome(src, "فنان", "عنوان", ".mp3")

    assert dest.read_bytes() == data
    assert not src.exists()
    assert _library_files() == ["عنوان.mp3"]


def test_cross_device_copy_failure_leaves_nothing_in_library(tmp_path, monkeypatch):
    src = _source(tmp_path)
    _cross_device(monkeypatch)

    def failing_copy(s, d, **kw):
        with open(d, "wb") as f:
            f.write(b"half")
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(shutil, "copy2", failing_copy)

    assert FileMover.move_to_navidrome(src, "فنان", "عنوان", ".mp3") is None
    assert src.exists()
    assert _library_files() == []
