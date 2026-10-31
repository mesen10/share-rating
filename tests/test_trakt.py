import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
import requests
import responses

from share_rating import db
from share_rating.config import Config
from share_rating.trakt import TraktAuthError, TraktClient

API = "https://api.trakt.tv"
FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = Config(trakt_client_id="fake-id", trakt_client_secret="fake-secret")


def store_tokens(conn, created_at=None, expires_in=86400, access="old-access"):
    tokens = {
        "access_token": access,
        "refresh_token": "fake-refresh",
        "expires_in": expires_in,
        "created_at": int(time.time()) if created_at is None else created_at,
    }
    db.kv_set(conn, "trakt_tokens", json.dumps(tokens))


def mock_watched(rsps, status=200):
    rsps.get(f"{API}/sync/watched/movies", json=json.loads((FIXTURES / "trakt_watched_movies.json").read_text()), status=status)
    rsps.get(f"{API}/sync/watched/shows", json=json.loads((FIXTURES / "trakt_watched_shows.json").read_text()), status=status)


def token_response(access="new-access"):
    return {"access_token": access, "refresh_token": "new-refresh", "expires_in": 86400,
            "created_at": int(time.time()), "token_type": "bearer", "scope": "public"}


@responses.activate
def test_fetch_watched_parses_movies_and_shows(conn):
    store_tokens(conn)
    mock_watched(responses)
    items = TraktClient(CONFIG, conn).fetch_watched()

    assert [(i.type, i.trakt_id) for i in items] == [("movie", 1001), ("movie", 1002), ("show", 2001), ("show", 2002)]
    dune = items[0]
    assert dune.imdb_id == "tt15239678"
    assert dune.tmdb_id == 693134
    assert dune.title == "Dune: Part Two"
    assert dune.year == 2024
    assert dune.last_watched_at == datetime(2024, 3, 12, 20, 15, tzinfo=UTC)
    assert items[1].imdb_id is None
    assert items[3].tmdb_id is None


@responses.activate
def test_fetch_watched_shows_skip_seasons(conn):
    store_tokens(conn)
    mock_watched(responses)
    TraktClient(CONFIG, conn).fetch_watched()
    assert "extended=noseasons" in responses.calls[1].request.url


@responses.activate
def test_fetch_watched_sends_required_headers(conn):
    store_tokens(conn)
    mock_watched(responses)
    TraktClient(CONFIG, conn).fetch_watched()
    headers = responses.calls[0].request.headers
    assert headers["trakt-api-key"] == "fake-id"
    assert headers["trakt-api-version"] == "2"
    assert headers["Authorization"] == "Bearer old-access"


@responses.activate
def test_expired_token_refreshes_then_retries(conn):
    store_tokens(conn, created_at=1_000_000)
    responses.post(f"{API}/oauth/token", json=token_response())
    mock_watched(responses)

    TraktClient(CONFIG, conn).fetch_watched()

    refresh_body = json.loads(responses.calls[0].request.body)
    assert refresh_body["grant_type"] == "refresh_token"
    assert refresh_body["refresh_token"] == "fake-refresh"
    assert refresh_body["redirect_uri"] == "urn:ietf:wg:oauth:2.0:oob"
    assert json.loads(db.kv_get(conn, "trakt_tokens"))["access_token"] == "new-access"
    assert responses.calls[1].request.headers["Authorization"] == "Bearer new-access"


@responses.activate
def test_401_triggers_single_refresh(conn):
    store_tokens(conn)
    responses.get(f"{API}/sync/watched/movies", status=401)
    responses.post(f"{API}/oauth/token", json=token_response())
    mock_watched(responses)

    items = TraktClient(CONFIG, conn).fetch_watched()

    assert len(items) == 4
    assert sum(1 for c in responses.calls if c.request.url.endswith("/oauth/token")) == 1


@responses.activate
def test_refresh_failure_raises_auth_error(conn):
    store_tokens(conn, created_at=1_000_000)
    responses.post(f"{API}/oauth/token", status=401)
    with pytest.raises(TraktAuthError, match="python -m share_rating auth"):
        TraktClient(CONFIG, conn).fetch_watched()


def test_no_tokens_raises_auth_error(conn):
    with pytest.raises(TraktAuthError, match="python -m share_rating auth"):
        TraktClient(CONFIG, conn).fetch_watched()


@responses.activate
def test_server_error_raises(conn):
    store_tokens(conn)
    responses.get(f"{API}/sync/watched/movies", status=503)
    with pytest.raises(requests.HTTPError):
        TraktClient(CONFIG, conn).fetch_watched()


@responses.activate
def test_device_auth_polls_until_token(conn):
    responses.post(f"{API}/oauth/device/code", json={
        "device_code": "dev-code", "user_code": "ABCD1234",
        "verification_url": "https://trakt.tv/activate", "expires_in": 600, "interval": 0,
    })
    responses.post(f"{API}/oauth/device/token", status=400)
    responses.post(f"{API}/oauth/device/token", json=token_response("device-access"))
    printed = []

    TraktClient(CONFIG, conn).device_auth(print_fn=printed.append)

    assert any("ABCD1234" in line and "https://trakt.tv/activate" in line for line in printed)
    assert json.loads(responses.calls[1].request.body) == {
        "code": "dev-code", "client_id": "fake-id", "client_secret": "fake-secret"}
    assert json.loads(db.kv_get(conn, "trakt_tokens"))["access_token"] == "device-access"


@responses.activate
def test_device_auth_denied_raises(conn):
    responses.post(f"{API}/oauth/device/code", json={
        "device_code": "dev-code", "user_code": "ABCD1234",
        "verification_url": "https://trakt.tv/activate", "expires_in": 600, "interval": 0,
    })
    responses.post(f"{API}/oauth/device/token", status=418)
    with pytest.raises(TraktAuthError):
        TraktClient(CONFIG, conn).device_auth(print_fn=lambda _: None)
