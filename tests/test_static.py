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


def test_text_assets_are_gzipped(client):
    """app.js and style.css went over the wire uncompressed (~210 KB) on every cold load."""
    resp = client.get("/app.js", headers={"Accept-Encoding": "gzip"})

    assert resp.headers.get("content-encoding") == "gzip"
    assert resp.headers["cache-control"] == "no-cache"  # still revalidated


def test_gzip_skips_the_event_stream_and_compressed_files():
    """Gzip buffers, so it would hold SSE events back; woff2 and images are already compressed."""
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    from app.main import GZipExceptStreams

    big = PlainTextResponse("x" * 5000)
    inner = Starlette(routes=[Route(p, lambda request: big) for p in
                              ("/api/events", "/api/artwork/1", "/fonts/a.woff2", "/api/pending")])
    client = TestClient(GZipExceptStreams(inner))

    def encoding(path):
        return client.get(path, headers={"Accept-Encoding": "gzip"}).headers.get("content-encoding")

    assert encoding("/api/events") is None
    assert encoding("/api/artwork/1") is None
    assert encoding("/fonts/a.woff2") is None
    assert encoding("/api/pending") == "gzip"


def test_cairo_is_self_hosted_and_cached_for_good(client):
    """No render-blocking stylesheet from Google; the versioned font files never revalidate."""
    html = client.get("/").text
    assert "fonts.googleapis.com" not in html and "fonts.gstatic.com" not in html
    assert 'rel="preload" href="/fonts/cairo-arabic-v31.woff2"' in html
    assert "url('fonts/cairo-arabic-v31.woff2')" in client.get("/style.css").text

    for name in ("cairo-arabic-v31.woff2", "cairo-latin-v31.woff2"):
        resp = client.get(f"/fonts/{name}")
        assert resp.status_code == 200
        assert resp.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert resp.content[:4] == b"wOF2"
    assert client.get("/fonts/OFL.txt").status_code == 200
