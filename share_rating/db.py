"""All SQLite access lives here."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from share_rating.models import Card, WatchedItem

SCHEMA = """
CREATE TABLE IF NOT EXISTS watched (
  type TEXT NOT NULL CHECK (type IN ('movie','show')),
  trakt_id INTEGER NOT NULL,
  imdb_id TEXT,
  tmdb_id INTEGER,
  title TEXT NOT NULL,
  year INTEGER,
  last_watched_at TEXT NOT NULL,          -- ISO 8601 UTC
  poster_path TEXT,                       -- NULL = not looked up, '' = none
  PRIMARY KEY (type, trakt_id)
);
CREATE TABLE IF NOT EXISTS imdb_ratings (imdb_id TEXT PRIMARY KEY, rating INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS hidden (imdb_id TEXT PRIMARY KEY, hidden_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS self_rated (imdb_id TEXT PRIMARY KEY, rated_at TEXT NOT NULL);  -- user's "Rated" confirmations
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def replace_watched(conn: sqlite3.Connection, items: list[WatchedItem]) -> None:
    with conn:
        conn.execute("CREATE TEMP TABLE IF NOT EXISTS incoming (type TEXT, trakt_id INTEGER)")
        conn.execute("DELETE FROM incoming")
        for it in items:
            conn.execute(
                """
                INSERT INTO watched (type, trakt_id, imdb_id, tmdb_id, title, year, last_watched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (type, trakt_id) DO UPDATE SET
                  imdb_id = excluded.imdb_id,
                  tmdb_id = excluded.tmdb_id,
                  title = excluded.title,
                  year = excluded.year,
                  last_watched_at = excluded.last_watched_at
                """,
                (it.type, it.trakt_id, it.imdb_id, it.tmdb_id, it.title, it.year,
                 it.last_watched_at.astimezone(UTC).isoformat()),
            )
            conn.execute("INSERT INTO incoming VALUES (?, ?)", (it.type, it.trakt_id))
        conn.execute(
            "DELETE FROM watched WHERE (type, trakt_id) NOT IN (SELECT type, trakt_id FROM incoming)"
        )
        conn.execute("DELETE FROM incoming")


def replace_imdb_ratings(conn: sqlite3.Connection, ratings: dict[str, int]) -> None:
    with conn:
        conn.execute("DELETE FROM imdb_ratings")
        conn.executemany("INSERT INTO imdb_ratings VALUES (?, ?)", ratings.items())


def hide(conn: sqlite3.Connection, imdb_id: str) -> None:
    with conn:
        conn.execute("INSERT OR IGNORE INTO hidden VALUES (?, ?)", (imdb_id, _now()))


def mark_rated(conn: sqlite3.Connection, imdb_id: str) -> None:
    with conn:
        conn.execute("INSERT OR IGNORE INTO self_rated VALUES (?, ?)", (imdb_id, _now()))


def unrated_candidates(conn: sqlite3.Connection) -> list[Card]:
    rows = conn.execute(
        """
        SELECT * FROM watched
        WHERE imdb_id IS NOT NULL
          AND imdb_id NOT IN (SELECT imdb_id FROM imdb_ratings)
          AND imdb_id NOT IN (SELECT imdb_id FROM self_rated)
          AND imdb_id NOT IN (SELECT imdb_id FROM hidden)
        """
    ).fetchall()
    return [
        Card(r["type"], r["imdb_id"], r["tmdb_id"], r["title"], r["year"],
             datetime.fromisoformat(r["last_watched_at"]), r["poster_path"])
        for r in rows
    ]


def set_poster_path(conn: sqlite3.Connection, type: str, tmdb_id: int, poster_path: str) -> None:
    with conn:
        conn.execute(
            "UPDATE watched SET poster_path = ? WHERE type = ? AND tmdb_id = ?",
            (poster_path, type, tmdb_id),
        )


def kv_get(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def kv_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    with conn:
        conn.execute(
            "INSERT INTO kv VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
