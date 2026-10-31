"""Load settings from a .env file, with real environment variables taking precedence."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

REQUIRED_KEYS = ("TRAKT_CLIENT_ID",)


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    trakt_client_id: str
    trakt_client_secret: str | None = None  # new Trakt apps (PKCE) have none
    tmdb_api_key: str | None = None
    db_path: Path = Path("share_rating.db")
    port: int = 8510


def load_config(env_path: Path = Path(".env")) -> Config:
    values = {k: v for k, v in dotenv_values(env_path).items() if v}
    values.update({k: v for k, v in os.environ.items() if v})

    missing = [key for key in REQUIRED_KEYS if key not in values]
    if missing:
        raise ConfigError(
            f"Missing setting(s): {', '.join(missing)}. Copy .env.example to .env and fill them in."
        )

    try:
        port = int(values.get("PORT", 8510))
    except ValueError:
        raise ConfigError(f"PORT must be a number, got {values['PORT']!r}") from None

    return Config(
        trakt_client_id=values["TRAKT_CLIENT_ID"],
        trakt_client_secret=values.get("TRAKT_CLIENT_SECRET"),
        tmdb_api_key=values.get("TMDB_API_KEY"),
        db_path=Path(values.get("DB_PATH", "share_rating.db")),
        port=port,
    )
