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


def test_icons_are_small_and_linked(client):
    """The 1024px favicon was 347 KB on every first load (plan S4-5, audit #34)."""
    html = client.get("/").text
    assert 'rel="icon"' in html and 'href="/favicon-32.png"' in html
    assert 'rel="apple-touch-icon"' in html and 'href="/apple-touch-icon.png"' in html

    for path in ("/favicon-32.png", "/apple-touch-icon.png"):
        resp = client.get(path)
        assert resp.status_code == 200
        assert len(resp.content) < 10_000
