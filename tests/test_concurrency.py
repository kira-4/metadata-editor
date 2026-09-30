"""Event-loop safety and confirm claiming (audit #05, review N5)."""
import asyncio
import threading
import uuid

import pytest

from app import events
from app.config import config
from app.database import DatabaseManager, PendingItem, SessionLocal
from app.metadata_processor import metadata_processor


def test_publish_event_from_worker_thread_reaches_client():
    async def scenario():
        stream = events.event_stream()
        first = asyncio.ensure_future(stream.__anext__())
        await asyncio.sleep(0)  # let the client register

        t = threading.Thread(target=events.publish_event, args=({"type": "new_item", "id": 7},))
        t.start()
        t.join()

        msg = await asyncio.wait_for(first, timeout=1)
        await stream.aclose()
        return msg

    assert '"new_item"' in asyncio.run(scenario())


def test_publish_event_without_loop_is_a_noop(monkeypatch):
    monkeypatch.setattr(events, "_loop", None)
    events.publish_event({"type": "x"})  # must not raise


@pytest.fixture
def item(db, make_audio):
    staged = make_audio(".mp3", dir=config.STAGING_DIR / str(uuid.uuid4()), name="staged")
    item = DatabaseManager.create_pending_item(
        db=db, original_path=str(config.INCOMING_ROOT / "gone.mp3"), current_path=str(staged),
        video_title="v", channel="c", extension=".mp3",
        inferred_title="t", inferred_artist="a", status="pending",
    )
    DatabaseManager.update_item(db, item.id, genre="لطمية")
    return item


def test_only_one_claim_wins(item):
    results = []
    barrier = threading.Barrier(8)

    def worker():
        s = SessionLocal()
        try:
            barrier.wait()
            results.append(DatabaseManager.claim_for_processing(s, item.id, ("pending",)))
        finally:
            s.close()

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count(True) == 1


def test_confirm_while_processing_is_rejected(client, db, item):
    DatabaseManager.claim_for_processing(db, item.id, ("pending",))

    assert client.post(f"/api/pending/{item.id}/confirm").status_code == 409
    assert client.delete(f"/api/pending/{item.id}").status_code == 409


def test_failed_validation_releases_claim(client, db, item):
    resp = client.post(f"/api/pending/{item.id}/confirm", json={"title": "   "})

    assert resp.status_code == 400
    db.expire_all()
    assert db.get(PendingItem, item.id).status == "pending"


def test_failed_write_records_error_not_processing(client, db, item, monkeypatch):
    monkeypatch.setattr(metadata_processor, "update_metadata_safe", lambda *a, **k: False)

    assert client.post(f"/api/pending/{item.id}/confirm").status_code == 500
    db.expire_all()
    assert db.get(PendingItem, item.id).status == "error"


def test_interrupted_processing_is_reset_on_startup(db, item):
    DatabaseManager.claim_for_processing(db, item.id, ("pending",))

    assert DatabaseManager.reset_interrupted_processing(db) == 1
    db.expire_all()
    assert db.get(PendingItem, item.id).status == "error"
