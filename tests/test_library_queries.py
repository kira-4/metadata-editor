"""Library listing: SQL sort before pagination, filtered totals (audit #07)."""
from datetime import datetime, timezone

import pytest

from app.database import LibraryManager


def add(db, n, title, artist="A", album="X", year=None, genre="G", album_artist=None):
    LibraryManager.create_or_update_track(
        db, f"/music/{n}.mp3",
        {"title": title, "artist": artist, "album": album, "year": year, "genre": genre,
         "album_artist": album_artist or artist},
        {"size": 1, "modified": datetime.now(timezone.utc)},
    )


@pytest.fixture
def library(db):
    add(db, 1, "Zulu", artist="B")
    add(db, 2, "Alpha", artist="C", year=2001)
    add(db, 3, "Mike", artist="A", year=1999, genre="H")
    add(db, 4, "Alpha", artist="A")  # tie on title
    add(db, 5, "100% Pure", artist="A", album="Y")
    add(db, 6, "under_score", artist="A", album="Y")
    return db


def all_pages(client, **params):
    titles, offset = [], 0
    while True:
        body = client.get("/api/library/tracks", params={**params, "limit": 2, "offset": offset}).json()
        titles += [t["title"] for t in body["tracks"]]
        offset += 2
        if offset >= body["total"]:
            return titles, body["total"]


@pytest.mark.parametrize("order", ["asc", "desc"])
def test_pages_match_full_sort(client, library, order):
    titles, total = all_pages(client, sort_by="title", sort_order=order)

    expected = sorted(["Zulu", "Alpha", "Mike", "Alpha", "100% Pure", "under_score"],
                      key=str.lower, reverse=(order == "desc"))
    assert titles == expected
    assert total == 6


def test_first_page_is_globally_first(client, library):
    body = client.get("/api/library/tracks", params={"sort_by": "title", "limit": 1}).json()

    assert body["tracks"][0]["title"] == "100% Pure"


def test_total_counts_only_filtered_tracks(client, library):
    body = client.get("/api/library/tracks", params={"genre": "H"}).json()

    assert [t["title"] for t in body["tracks"]] == ["Mike"]
    assert body["total"] == 1


@pytest.mark.parametrize("term,expected", [("%", ["100% Pure"]), ("_", ["under_score"])])
def test_search_wildcards_are_literal(client, library, term, expected):
    body = client.get("/api/library/tracks", params={"search": term}).json()

    assert [t["title"] for t in body["tracks"]] == expected
    assert body["total"] == len(expected)


@pytest.mark.parametrize("params", [{"limit": -1}, {"limit": 0}, {"offset": -1}, {"sort_by": "name"}, {"sort_order": "up"}])
def test_invalid_params_rejected(client, library, params):
    assert client.get("/api/library/tracks", params=params).status_code == 422
