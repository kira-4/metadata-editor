"""Deployment config: the container must behave on the NAS, not just locally."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _service():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    return compose["services"]["metadata-editor"]


def test_container_runs_as_host_user():
    # Root-owned files in /music can't be edited by the host user or Navidrome.
    assert _service()["user"] == "${PUID:-1000}:${PGID:-1000}"


def test_env_example_documents_puid_pgid():
    example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "PUID=" in example
    assert "PGID=" in example
