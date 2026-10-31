"""Trakt API client: device-code login, token refresh, and the watched lists."""

import json
import sqlite3
import time
from datetime import datetime
from typing import Callable

import requests

from share_rating import db
from share_rating.config import Config
from share_rating.models import WatchedItem

API = "https://api.trakt.tv"
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
TOKENS_KEY = "trakt_tokens"
REFRESH_MARGIN_SECONDS = 60
TIMEOUT = 30


class TraktAuthError(Exception):
    def __init__(self, reason: str = "Not logged in to Trakt"):
        super().__init__(f"{reason}. Run: python -m share_rating auth")


class TraktClient:
    def __init__(self, config: Config, conn: sqlite3.Connection, session: requests.Session | None = None):
        self.config = config
        self.conn = conn
        self.session = session or requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": config.trakt_client_id,
            "User-Agent": "share-rating/0.1",
        })

    # --- tokens -------------------------------------------------------------

    def _load_tokens(self) -> dict:
        raw = db.kv_get(self.conn, TOKENS_KEY)
        if raw is None:
            raise TraktAuthError()
        return json.loads(raw)

    def _save_tokens(self, tokens: dict) -> None:
        tokens.setdefault("created_at", int(time.time()))
        db.kv_set(self.conn, TOKENS_KEY, json.dumps(tokens))

    def _refresh(self, tokens: dict) -> dict:
        resp = self.session.post(f"{API}/oauth/token", json={
            "refresh_token": tokens["refresh_token"],
            "client_id": self.config.trakt_client_id,
            "client_secret": self.config.trakt_client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "refresh_token",
        }, timeout=TIMEOUT)
        if resp.status_code != 200:
            raise TraktAuthError("Trakt login expired")
        new_tokens = resp.json()
        self._save_tokens(new_tokens)
        return new_tokens

    def _fresh_tokens(self) -> dict:
        tokens = self._load_tokens()
        expires_at = tokens["created_at"] + tokens["expires_in"]
        if expires_at - time.time() < REFRESH_MARGIN_SECONDS:
            tokens = self._refresh(tokens)
        return tokens

    # --- requests -----------------------------------------------------------

    def _get(self, path: str) -> list | dict:
        tokens = self._fresh_tokens()
        resp = self._authed_get(path, tokens)
        if resp.status_code == 401:
            resp = self._authed_get(path, self._refresh(tokens))
            if resp.status_code == 401:
                raise TraktAuthError("Trakt rejected the login")
        resp.raise_for_status()
        return resp.json()

    def _authed_get(self, path: str, tokens: dict) -> requests.Response:
        return self.session.get(
            f"{API}{path}", headers={"Authorization": f"Bearer {tokens['access_token']}"}, timeout=TIMEOUT
        )

    def fetch_watched(self) -> list[WatchedItem]:
        movies = self._get("/sync/watched/movies")
        shows = self._get("/sync/watched/shows?extended=noseasons")
        return [_to_item(e, "movie") for e in movies] + [_to_item(e, "show") for e in shows]

    # --- login --------------------------------------------------------------

    def device_auth(self, print_fn: Callable[[str], None] = print) -> None:
        resp = self.session.post(
            f"{API}/oauth/device/code", json={"client_id": self.config.trakt_client_id}, timeout=TIMEOUT
        )
        resp.raise_for_status()
        code = resp.json()
        print_fn(f"Go to {code['verification_url']} and enter the code: {code['user_code']}")

        interval = code["interval"]
        deadline = time.time() + code["expires_in"]
        while time.time() < deadline:
            time.sleep(interval)
            resp = self.session.post(f"{API}/oauth/device/token", json={
                "code": code["device_code"],
                "client_id": self.config.trakt_client_id,
                "client_secret": self.config.trakt_client_secret,
            }, timeout=TIMEOUT)
            if resp.status_code == 200:
                self._save_tokens(resp.json())
                print_fn("Logged in to Trakt.")
                return
            if resp.status_code == 400:  # user has not approved yet
                continue
            if resp.status_code == 429:  # polling too fast
                interval += 1
                continue
            raise TraktAuthError(f"Trakt login failed (HTTP {resp.status_code})")
        raise TraktAuthError("Trakt login code expired")


def _to_item(entry: dict, type: str) -> WatchedItem:
    media = entry[type]
    ids = media["ids"]
    return WatchedItem(
        type=type,
        trakt_id=ids["trakt"],
        imdb_id=ids.get("imdb") or None,
        tmdb_id=ids.get("tmdb") or None,
        title=media["title"],
        year=media.get("year"),
        last_watched_at=datetime.fromisoformat(entry["last_watched_at"].replace("Z", "+00:00")),
    )
