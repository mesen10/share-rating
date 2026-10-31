import pytest
from flask import Flask

from share_rating.__main__ import main

KEYS = ["TRAKT_CLIENT_ID", "TRAKT_CLIENT_SECRET", "TMDB_API_KEY", "DB_PATH", "PORT"]


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)


def test_missing_config_returns_2(capsys):
    assert main(["serve", "--no-browser"]) == 2
    err = capsys.readouterr().err
    assert "TRAKT_CLIENT_ID" in err
    assert ".env.example" in err


def test_serve_binds_localhost(monkeypatch):
    monkeypatch.setenv("TRAKT_CLIENT_ID", "fake-id")
    monkeypatch.setenv("TRAKT_CLIENT_SECRET", "fake-secret")
    calls = {}
    monkeypatch.setattr(Flask, "run", lambda self, **kwargs: calls.update(kwargs))
    opened = []
    monkeypatch.setattr("webbrowser.open", opened.append)

    assert main(["serve", "--no-browser"]) == 0
    assert calls["host"] == "127.0.0.1"
    assert calls["port"] == 8765
    assert opened == []
