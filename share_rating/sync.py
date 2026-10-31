import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

import requests

from share_rating import db
from share_rating.trakt import TraktAuthError, TraktClient


@dataclass
class SyncResult:
    ok: bool
    message: str


def run_sync(conn: sqlite3.Connection, trakt: TraktClient) -> SyncResult:
    try:
        items = trakt.fetch_watched()
    except TraktAuthError:
        return SyncResult(False, "Trakt login expired. Run: python -m share_rating auth")
    except requests.RequestException as e:
        return SyncResult(False, f"Trakt sync failed: {e}")

    db.replace_watched(conn, items)
    db.kv_set(conn, "last_trakt_sync", datetime.now(UTC).isoformat())
    return SyncResult(True, f"Synced {len(items)} watched titles from Trakt")
