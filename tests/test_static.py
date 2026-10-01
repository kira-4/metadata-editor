"""Static assets must be revalidated so redeploys reach browsers (phones)."""
import pytest


@pytest.mark.parametrize("path", ["/", "/app.js", "/style.css"])
def test_static_assets_require_revalidation(client, path):
    resp = client.get(path)

    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-cache"
    assert resp.headers.get("etag")


def test_unchanged_asset_revalidates_with_304(client):
    etag = client.get("/app.js").headers["etag"]

    resp = client.get("/app.js", headers={"If-None-Match": etag})

    assert resp.status_code == 304


def test_ci_checks_frontend_and_runs_audio_tests():
    from pathlib import Path

    import yaml

    ci = yaml.safe_load((Path(__file__).resolve().parent.parent / ".github/workflows/ci.yml").read_text())
    steps = [s.get("run", "") for job in ci["jobs"].values() for s in job["steps"]]

    assert any("node --check app/static/app.js" in r for r in steps)
    assert any("ffmpeg" in r for r in steps)
    assert any("pytest" in r for r in steps)
