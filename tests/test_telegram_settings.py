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
