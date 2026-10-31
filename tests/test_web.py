import io
import random
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from share_rating import db
from share_rating.config import Config
from share_rating.models import WatchedItem
from share_rating.trakt import TraktAuthError
from share_rating.web import create_app

NOW = datetime(2026, 10, 31, tzinfo=UTC)
SAMPLE = (Path(__file__).parent / "fixtures" / "imdb_ratings_sample.csv").read_bytes()
LINK = re.compile(r'href="https://www\.imdb\.com/title/(tt\d+)/"[^>]*target="_blank"')


class FakeTrakt:
    def __init__(self, config, conn):
        pass

    def fetch_watched(self):
        raise TraktAuthError()


@pytest.fixture
def setup(tmp_path):
    config = Config(trakt_client_id="fake-id", trakt_client_secret="fake-secret", db_path=tmp_path / "web.db")
    app = create_app(config, trakt_factory=FakeTrakt, rng=random.Random(0), now_fn=lambda: NOW)
    app.config["TESTING"] = True
    conn = db.connect(config.db_path)
    db.init_db(conn)
    yield app.test_client(), conn
    conn.close()


def seed(conn, imdb_ids):
    db.replace_watched(conn, [
        WatchedItem("movie", i, imdb_id, None, f"Title {imdb_id}", 2000, NOW - timedelta(days=30))
        for i, imdb_id in enumerate(imdb_ids, start=1)
    ])


def shown_ids(client):
    return set(LINK.findall(client.get("/").get_data(as_text=True)))


def test_index_shows_10_cards_with_imdb_links(setup):
    client, conn = setup
    seed(conn, [f"tt{i:07d}" for i in range(30)])
    html = client.get("/").get_data(as_text=True)
    assert len(set(LINK.findall(html))) == 10
    assert "30 unrated" in html


def test_index_excludes_rated_confirmed_and_hidden(setup):
    client, conn = setup
    seed(conn, ["tt0000001", "tt0000002", "tt0000003", "tt0000004"])
    db.replace_imdb_ratings(conn, {"tt0000001": 7})
    db.mark_rated(conn, "tt0000002")
    db.hide(conn, "tt0000003")
    assert shown_ids(client) == {"tt0000004"}


def test_index_empty_state(setup):
    client, _ = setup
    assert "All caught up" in client.get("/").get_data(as_text=True)


def test_index_shows_import_hint_until_first_import(setup):
    client, conn = setup
    hint = "Import your IMDb ratings CSV once"
    assert hint in client.get("/").get_data(as_text=True)
    client.post("/import", data={"csv": (io.BytesIO(SAMPLE), "ratings.csv")}, content_type="multipart/form-data")
    assert hint not in client.get("/").get_data(as_text=True)


def test_index_renders_without_tmdb_key(setup):
    client, conn = setup
    seed(conn, ["tt0000001"])
    resp = client.get("/")
    assert resp.status_code == 200
    assert "placeholder" in resp.get_data(as_text=True)


def test_hide_and_rated_endpoints(setup):
    client, conn = setup
    seed(conn, ["tt0000001", "tt0000002", "tt0000003"])
    assert client.post("/hide/tt0000001").status_code == 204
    assert client.post("/rated/tt0000002").status_code == 204
    assert shown_ids(client) == {"tt0000003"}
    assert client.post("/rated/notanid").status_code == 400
    assert client.post("/hide/notanid").status_code == 400


def test_import_csv_success(setup):
    client, conn = setup
    seed(conn, ["tt0111161", "tt0068646", "tt0000009"])
    resp = client.post("/import", data={"csv": (io.BytesIO(SAMPLE), "ratings.csv")},
                       content_type="multipart/form-data", follow_redirects=True)
    assert "Imported 3 IMDb ratings" in resp.get_data(as_text=True)
    assert shown_ids(client) == {"tt0000009"}


def test_import_csv_bad_file_keeps_ratings(setup):
    client, conn = setup
    seed(conn, ["tt0000001", "tt0000002"])
    db.replace_imdb_ratings(conn, {"tt0000001": 7})
    resp = client.post("/import", data={"csv": (io.BytesIO(b"\x89PNG\x00"), "x.png")},
                       content_type="multipart/form-data", follow_redirects=True)
    assert "CSV import failed, kept previous ratings" in resp.get_data(as_text=True)
    assert shown_ids(client) == {"tt0000002"}


def test_import_without_file(setup):
    client, _ = setup
    resp = client.post("/import", data={}, follow_redirects=True)
    assert "Choose a CSV file first" in resp.get_data(as_text=True)


def test_sync_flashes_message(setup):
    client, _ = setup
    resp = client.post("/sync", follow_redirects=True)
    assert "Trakt login expired" in resp.get_data(as_text=True)
