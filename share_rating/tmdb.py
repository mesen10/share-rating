"""Poster lookup via TMDB. Failures never break the page; the card shows a placeholder."""

import dataclasses
import sqlite3

import requests

from share_rating import db
from share_rating.models import Card

API = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w342"
TIMEOUT = 3


def poster_url(poster_path: str | None) -> str | None:
    return f"{IMAGE_BASE}{poster_path}" if poster_path else None


def ensure_posters(
    conn: sqlite3.Connection,
    cards: list[Card],
    api_key: str | None,
    session: requests.Session | None = None,
) -> list[Card]:
    if not api_key:
        return cards
    session = session or requests.Session()
    reachable = True
    result = []
    for card in cards:
        if reachable and card.poster_path is None and card.tmdb_id is not None:
            try:
                path = _lookup(session, card, api_key)
            except requests.RequestException:
                reachable = False  # don't make the page wait on every remaining card
                path = None
            if path is not None:
                db.set_poster_path(conn, card.type, card.tmdb_id, path)
                card = dataclasses.replace(card, poster_path=path)
        result.append(card)
    return result


def _lookup(session: requests.Session, card: Card, api_key: str) -> str | None:
    """Return the poster path, "" if TMDB has none, or None if the answer was unusable."""
    kind = "tv" if card.type == "show" else "movie"
    resp = session.get(f"{API}/{kind}/{card.tmdb_id}", params={"api_key": api_key}, timeout=TIMEOUT)
    if resp.status_code == 404:
        return ""
    if resp.status_code != 200:
        return None
    try:
        return resp.json().get("poster_path") or ""
    except ValueError:
        return None
