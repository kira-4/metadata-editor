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
