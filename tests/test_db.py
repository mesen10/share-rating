from datetime import UTC, datetime

from share_rating import db
from share_rating.models import WatchedItem


def item(trakt_id, imdb_id="tt%07d", type="movie", watched=datetime(2024, 1, 1, tzinfo=UTC), tmdb_id=None):
    if imdb_id == "tt%07d":
        imdb_id = imdb_id % trakt_id
    return WatchedItem(type, trakt_id, imdb_id, tmdb_id, f"Title {trakt_id}", 2000, watched)


def candidate_ids(conn):
    return sorted(card.imdb_id for card in db.unrated_candidates(conn))


def test_replace_watched_adds_updates_and_deletes(conn):
    db.replace_watched(conn, [item(1), item(2)])
    newer = datetime(2025, 6, 1, tzinfo=UTC)
    db.replace_watched(conn, [item(2, watched=newer), item(3)])

    cards = {c.imdb_id: c for c in db.unrated_candidates(conn)}
    assert sorted(cards) == ["tt0000002", "tt0000003"]
    assert cards["tt0000002"].last_watched_at == newer


def test_replace_watched_keeps_poster_path(conn):
    db.replace_watched(conn, [item(1, tmdb_id=11)])
    db.set_poster_path(conn, "movie", 11, "/p.jpg")
    db.replace_watched(conn, [item(1, tmdb_id=11, watched=datetime(2025, 1, 1, tzinfo=UTC))])
    assert db.unrated_candidates(conn)[0].poster_path == "/p.jpg"


def test_same_trakt_id_for_movie_and_show_are_distinct(conn):
    db.replace_watched(conn, [item(1, "tt0000001", "movie"), item(1, "tt0000099", "show")])
    assert candidate_ids(conn) == ["tt0000001", "tt0000099"]


def test_candidates_exclude_rated_hidden_and_no_imdb(conn):
    db.replace_watched(conn, [item(1), item(2), item(3, imdb_id=None), item(4)])
    db.replace_imdb_ratings(conn, {"tt0000001": 8})
    db.hide(conn, "tt0000002")
    assert candidate_ids(conn) == ["tt0000004"]


def test_hidden_survives_watched_reconcile(conn):
    db.replace_watched(conn, [item(1)])
    db.hide(conn, "tt0000001")
    db.replace_watched(conn, [])
    db.replace_watched(conn, [item(1)])
    assert candidate_ids(conn) == []


def test_hide_is_idempotent(conn):
    db.hide(conn, "tt0000001")
    db.hide(conn, "tt0000001")


def test_replace_imdb_ratings_replaces_all(conn):
    db.replace_watched(conn, [item(1), item(2)])
    db.replace_imdb_ratings(conn, {"tt0000001": 8})
    db.replace_imdb_ratings(conn, {"tt0000002": 7})
    assert candidate_ids(conn) == ["tt0000001"]


def test_candidate_dates_are_utc_aware(conn):
    db.replace_watched(conn, [item(1)])
    assert db.unrated_candidates(conn)[0].last_watched_at.tzinfo is not None


def test_kv_roundtrip(conn):
    assert db.kv_get(conn, "missing") is None
    db.kv_set(conn, "k", "v1")
    db.kv_set(conn, "k", "v2")
    assert db.kv_get(conn, "k") == "v2"


def test_mark_rated_excludes_and_survives_csv_import(conn):
    db.replace_watched(conn, [item(1), item(2)])
    db.mark_rated(conn, "tt0000001")
    db.mark_rated(conn, "tt0000001")
    db.replace_imdb_ratings(conn, {})
    assert candidate_ids(conn) == ["tt0000002"]
