"""Telegram can be turned off and disconnected; errors never leak the token (plan S4-4, audit #32)."""
from types import SimpleNamespace

import httpx
import pytest

from app import telegram_notifier

TOKEN = "123456789:AAH-secret_token-value"


@pytest.fixture
def connected(client):
    resp = client.put("/api/settings/telegram", json={"bot_token": TOKEN, "chat_id": "42"})
    assert resp.status_code == 200
    return client


@pytest.fixture
def sent(monkeypatch):
    calls = []
    monkeypatch.setattr(telegram_notifier, "send_message", lambda *a, **k: calls.append(a) or (True, ""))
    return calls


ITEM = SimpleNamespace(id=1, current_title="t", current_artist="a", error_message=None)


def test_enabled_by_default_and_notifies(connected, sent):
    assert connected.get("/api/settings/telegram").json()["enabled"] is True

    telegram_notifier.notify_actionable(ITEM, "pending")

    assert len(sent) == 1


def test_disabled_keeps_credentials_but_sends_nothing(connected, sent):
    resp = connected.put("/api/settings/telegram", json={"chat_id": "42", "enabled": False})

    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["bot_token_set"] is True and body["chat_id"] == "42"

    telegram_notifier.notify_actionable(ITEM, "pending")
    assert sent == []


def test_disconnect_clears_everything(connected, sent):
    resp = connected.delete("/api/settings/telegram")

    assert resp.status_code == 200
    body = connected.get("/api/settings/telegram").json()
    assert body["bot_token_set"] is False
    assert body["chat_id"] is None and body["message_thread_id"] is None

    telegram_notifier.notify_actionable(ITEM, "pending")
    assert sent == []


def test_transport_error_does_not_leak_token(monkeypatch):
    def boom(self, url, **kwargs):
        raise httpx.ConnectError(f"failed to connect to {url}")

    monkeypatch.setattr(httpx.Client, "post", boom)

    ok, error = telegram_notifier.send_message(TOKEN, "42", "hi")

    assert not ok
    assert TOKEN not in error
    assert "secret_token" not in error


def test_api_error_detail_does_not_leak_token(monkeypatch):
    monkeypatch.setattr(
        httpx.Client, "post",
        lambda self, url, **k: httpx.Response(401, json={"description": f"Unauthorized for bot{TOKEN}"}),
    )

    ok, error = telegram_notifier.send_message(TOKEN, "42", "hi")

    assert not ok
    assert "secret_token" not in error
    assert "401" in error


# --- Deep link from the message to its card ---

def test_app_url_is_stored_normalized_and_kept_by_other_updates(connected):
    resp = connected.put("/api/settings/telegram", json={"chat_id": "42", "app_url": " http://nas.tail.ts.net:8090/#/pending "})
    assert resp.json()["app_url"] == "http://nas.tail.ts.net:8090"

    # The on/off switch sends no app_url: it must not wipe it
    connected.put("/api/settings/telegram", json={"chat_id": "42", "enabled": False})
    assert connected.get("/api/settings/telegram").json()["app_url"] == "http://nas.tail.ts.net:8090"

    connected.put("/api/settings/telegram", json={"chat_id": "42", "app_url": ""})
    assert connected.get("/api/settings/telegram").json()["app_url"] is None


def test_app_url_must_be_http(connected):
    resp = connected.put("/api/settings/telegram", json={"chat_id": "42", "app_url": "nas:8090"})
    assert resp.status_code == 400


def test_message_links_to_its_card(connected, monkeypatch):
    calls = []
    monkeypatch.setattr(telegram_notifier, "send_message", lambda *a, **k: calls.append(a) or (True, ""))
    connected.put("/api/settings/telegram", json={"chat_id": "42", "app_url": "http://nas:8090"})

    telegram_notifier.notify_actionable(SimpleNamespace(id=7, current_title="t", current_artist="a", error_message=None), "pending")

    assert calls[0][4] == "http://nas:8090/#/pending/7"


def test_no_app_url_means_no_button(connected, sent):
    telegram_notifier.notify_actionable(ITEM, "pending")
    assert sent[0][4] is None


def _capture_posts(monkeypatch, responses):
    payloads = []

    def post(self, url, json=None, **kwargs):
        payloads.append(json)
        return responses.pop(0)

    monkeypatch.setattr(httpx.Client, "post", post)
    return payloads


def test_refused_button_falls_back_to_a_text_link(monkeypatch):
    payloads = _capture_posts(monkeypatch, [
        httpx.Response(400, json={"ok": False, "description": "Bad Request: wrong HTTP URL"}),
        httpx.Response(200, json={"ok": True}),
    ])

    ok, _ = telegram_notifier.send_message(TOKEN, "42", "hi", None, "http://100.64.0.1:8090/#/pending/3")

    assert ok
    assert "reply_markup" in payloads[0]
    assert "reply_markup" not in payloads[1]
    assert payloads[1]["text"].endswith("http://100.64.0.1:8090/#/pending/3")


def test_button_is_sent_when_accepted(monkeypatch):
    payloads = _capture_posts(monkeypatch, [httpx.Response(200, json={"ok": True})])

    ok, _ = telegram_notifier.send_message(TOKEN, "42", "hi", None, "http://nas:8090/#/pending/3")

    assert ok and len(payloads) == 1
    button = payloads[0]["reply_markup"]["inline_keyboard"][0][0]
    assert button == {"text": "افتح البطاقة", "url": "http://nas:8090/#/pending/3"}


def test_auth_error_is_not_retried(monkeypatch):
    payloads = _capture_posts(monkeypatch, [httpx.Response(401, json={"description": "Unauthorized"})])

    ok, _ = telegram_notifier.send_message(TOKEN, "42", "hi", None, "http://nas:8090/#/pending/3")

    assert not ok and len(payloads) == 1
