"""Without an API key, inference must not hit the network (audit #20)."""
import app.openrouter_client as client_module
from app.config import config
from app.openrouter_client import OpenRouterClient


def test_missing_key_skips_request(monkeypatch):
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "")

    def no_network(*a, **k):
        raise AssertionError("request sent without an API key")

    monkeypatch.setattr(client_module.httpx, "post", no_network)

    title, artists, album_artist, error, raw = OpenRouterClient().infer_metadata("عنوان", "قناة")

    assert (title, artists, album_artist, raw) == (None, None, None, "")
    assert "OPENROUTER_API_KEY" in error
