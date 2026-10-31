from pathlib import Path

import pytest

from share_rating.config import ConfigError, load_config

KEYS = ["TRAKT_CLIENT_ID", "TRAKT_CLIENT_SECRET", "IMDB_USER_ID", "TMDB_API_KEY", "DB_PATH", "PORT"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)


def write_env(tmp_path, **values):
    path = tmp_path / ".env"
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
    return path


REQUIRED = {
    "TRAKT_CLIENT_ID": "fake-id",
    "TRAKT_CLIENT_SECRET": "fake-secret",
}


def test_load_config_reads_all_keys(tmp_path):
    path = write_env(tmp_path, **REQUIRED, TMDB_API_KEY="fake-tmdb", DB_PATH="data/x.db", PORT="9100")
    config = load_config(path)
    assert config.trakt_client_id == "fake-id"
    assert config.trakt_client_secret == "fake-secret"
    assert not hasattr(config, "imdb_user_id")
    assert config.tmdb_api_key == "fake-tmdb"
    assert config.db_path == Path("data/x.db")
    assert config.port == 9100


def test_load_config_defaults(tmp_path):
    config = load_config(write_env(tmp_path, **REQUIRED))
    assert config.tmdb_api_key is None
    assert config.db_path == Path("share_rating.db")
    assert config.port == 8510


def test_load_config_missing_key_raises(tmp_path):
    values = {k: v for k, v in REQUIRED.items() if k != "TRAKT_CLIENT_ID"}
    with pytest.raises(ConfigError, match="TRAKT_CLIENT_ID"):
        load_config(write_env(tmp_path, **values))


def test_client_secret_is_optional(tmp_path):
    # Trakt apps created since 2026-10 use PKCE and get no client secret.
    config = load_config(write_env(tmp_path, TRAKT_CLIENT_ID="fake-id"))
    assert config.trakt_client_secret is None


def test_load_config_empty_value_counts_as_missing(tmp_path):
    with pytest.raises(ConfigError, match="TRAKT_CLIENT_ID"):
        load_config(write_env(tmp_path, **{**REQUIRED, "TRAKT_CLIENT_ID": ""}))


def test_environment_overrides_env_file(tmp_path, monkeypatch):
    path = write_env(tmp_path, **REQUIRED, PORT="9100")
    monkeypatch.setenv("PORT", "9000")
    assert load_config(path).port == 9000
