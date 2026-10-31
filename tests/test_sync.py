from datetime import UTC, datetime

import requests

from share_rating import db
from share_rating.models import WatchedItem
from share_rating.sync import run_sync
from share_rating.trakt import TraktAuthError


def watched(trakt_id):
    return WatchedItem("movie", trakt_id, f"tt{trakt_id:07d}", None, "T", 2000, datetime(2024, 1, 1, tzinfo=UTC))


class FakeTrakt:
    def __init__(self, items=None, error=None):
        self.items, self.error = items or [], error

    def fetch_watched(self):
        if self.error:
            raise self.error
        return self.items


def test_sync_success_updates_watched(conn):
    result = run_sync(conn, FakeTrakt([watched(1), watched(2)]))
    assert result.ok
    assert result.message == "Synced 2 watched titles from Trakt"
    assert len(db.unrated_candidates(conn)) == 2
    assert db.kv_get(conn, "last_trakt_sync") is not None


def test_trakt_auth_error_message(conn):
    result = run_sync(conn, FakeTrakt(error=TraktAuthError()))
    assert not result.ok
    assert result.message == "Trakt login expired. Run: python -m share_rating auth"


def test_trakt_failure_does_not_wipe_watched(conn):
    db.replace_watched(conn, [watched(1)])
    result = run_sync(conn, FakeTrakt(error=requests.HTTPError("503 Server Error")))
    assert not result.ok
    assert result.message.startswith("Trakt sync failed")
    assert len(db.unrated_candidates(conn)) == 1
    assert db.kv_get(conn, "last_trakt_sync") is None
