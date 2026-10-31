from datetime import UTC, datetime

import responses

from share_rating import db
from share_rating.models import WatchedItem
from share_rating.tmdb import ensure_posters, poster_url

TMDB = "https://api.themoviedb.org/3"


def seed(conn, type="movie", tmdb_id=11):
    db.replace_watched(conn, [WatchedItem(type, 1, "tt0000001", tmdb_id, "T", 2000, datetime(2024, 1, 1, tzinfo=UTC))])
    return db.unrated_candidates(conn)


def test_poster_url():
    assert poster_url("/abc.jpg") == "https://image.tmdb.org/t/p/w342/abc.jpg"
    assert poster_url("") is None
    assert poster_url(None) is None


@responses.activate
def test_ensure_posters_fetches_and_caches(conn):
    responses.get(f"{TMDB}/movie/11", json={"poster_path": "/p.jpg"})
    result = ensure_posters(conn, seed(conn), "fake-key")
    assert result[0].poster_path == "/p.jpg"
    assert responses.calls[0].request.params["api_key"] == "fake-key"

    again = ensure_posters(conn, db.unrated_candidates(conn), "fake-key")
    assert again[0].poster_path == "/p.jpg"
    assert len(responses.calls) == 1


@responses.activate
def test_ensure_posters_tv_uses_tv_endpoint(conn):
    responses.get(f"{TMDB}/tv/11", json={"poster_path": "/s.jpg"})
    assert ensure_posters(conn, seed(conn, "show"), "fake-key")[0].poster_path == "/s.jpg"


@responses.activate
def test_ensure_posters_null_poster_stores_empty(conn):
    responses.get(f"{TMDB}/movie/11", json={"poster_path": None})
    ensure_posters(conn, seed(conn), "fake-key")
    assert db.unrated_candidates(conn)[0].poster_path == ""


@responses.activate
def test_ensure_posters_404_stores_empty(conn):
    responses.get(f"{TMDB}/movie/11", status=404)
    ensure_posters(conn, seed(conn), "fake-key")
    assert db.unrated_candidates(conn)[0].poster_path == ""


@responses.activate
def test_ensure_posters_500_leaves_null(conn):
    responses.get(f"{TMDB}/movie/11", status=500)
    result = ensure_posters(conn, seed(conn), "fake-key")
    assert result[0].poster_path is None
    assert db.unrated_candidates(conn)[0].poster_path is None


@responses.activate
def test_ensure_posters_network_error_leaves_null(conn):
    import requests
    responses.get(f"{TMDB}/movie/11", body=requests.ConnectionError("down"))
    assert ensure_posters(conn, seed(conn), "fake-key")[0].poster_path is None


@responses.activate
def test_ensure_posters_without_key_or_tmdb_id_skips(conn):
    assert ensure_posters(conn, seed(conn), None)[0].poster_path is None
    assert ensure_posters(conn, seed(conn, tmdb_id=None), "fake-key")[0].poster_path is None
    assert len(responses.calls) == 0
