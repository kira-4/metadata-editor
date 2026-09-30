"""Scanner failure paths must leave a recoverable queue item (audit #04)."""
from pathlib import Path

import pytest

from app.config import config
from app.database import PendingItem
from app.scanner import FileScanner
import app.scanner as scanner_module


@pytest.fixture
def scanner(monkeypatch):
    monkeypatch.setattr(scanner_module, "notify_actionable", lambda *a, **k: None)
    monkeypatch.setattr(
        FileScanner,
        "infer_metadata_with_fallback",
        lambda self, **kw: ("عنوان", "فنان", "فنان", None, "raw"),
    )
    return FileScanner()


def _incoming(make_audio):
    return make_audio(".mp3", dir=config.INCOMING_ROOT, name="title###channel")


def test_metadata_write_failure_creates_one_recoverable_item(scanner, make_audio, monkeypatch, db):
    incoming = _incoming(make_audio)
    monkeypatch.setattr(scanner_module.metadata_processor, "apply_metadata", lambda *a, **k: False)

    scanner.process_file(incoming)

    items = db.query(PendingItem).all()
    assert len(items) == 1
    assert items[0].status == "needs_manual"
    assert Path(items[0].current_path).exists()
    assert incoming.exists()


def test_unexpected_error_keeps_staged_file_referenced_by_item(scanner, make_audio, monkeypatch, db):
    incoming = _incoming(make_audio)

    def boom(*a, **k):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(scanner_module.metadata_processor, "apply_metadata", boom)

    scanner.process_file(incoming)

    items = db.query(PendingItem).all()
    assert len(items) == 1
    assert items[0].status == "error"
    assert Path(items[0].current_path).exists()


def test_happy_path_creates_pending_item(scanner, make_audio, db):
    incoming = _incoming(make_audio)

    scanner.process_file(incoming)

    items = db.query(PendingItem).all()
    assert len(items) == 1
    assert items[0].status == "pending"
    assert items[0].current_title == "عنوان"
    assert Path(items[0].current_path).is_relative_to(config.STAGING_DIR)
