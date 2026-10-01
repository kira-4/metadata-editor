"""/api/health is what the Docker healthcheck polls."""
import pytest
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import app


def test_health_ok(client):
    resp = client.get("/api/health")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert "scanner_running" in resp.json()


def test_health_reports_unreachable_database(client):
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("disk I/O error"))

    app.dependency_overrides[get_db] = lambda: BrokenSession()
    try:
        resp = client.get("/api/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 503
    assert resp.json()["status"] == "error"


def _compose_service():
    from pathlib import Path

    import yaml

    path = Path(__file__).resolve().parent.parent / "docker-compose.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))["services"]["metadata-editor"]


def test_compose_healthcheck_uses_python_not_curl():
    # python:3.11-slim ships no curl, so a curl healthcheck is always unhealthy.
    test = " ".join(_compose_service()["healthcheck"]["test"])

    assert "curl" not in test
    assert "/api/health" in test


@pytest.mark.parametrize("var", ["OPENROUTER_MODEL", "OPENROUTER_FALLBACK_MODELS", "OPENROUTER_BASE_URL"])
def test_compose_forwards_inference_settings(var):
    env = _compose_service()["environment"]

    assert any(e.startswith(f"{var}=") for e in env)


def test_blank_inference_env_falls_back_to_defaults():
    # Compose forwards unset vars as "", which must not override the defaults.
    import os
    import subprocess
    import sys

    env = {**os.environ, "OPENROUTER_MODEL": "", "OPENROUTER_BASE_URL": ""}
    out = subprocess.run(
        [sys.executable, "-c",
         "from app.config import config; print(config.OPENROUTER_MODEL); print(config.OPENROUTER_BASE_URL)"],
        env=env, capture_output=True, text=True, check=True,
    ).stdout.split()

    assert out == ["deepseek/deepseek-v4-flash", "https://openrouter.ai/api/v1"]
