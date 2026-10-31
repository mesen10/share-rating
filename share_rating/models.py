from dataclasses import dataclass
from datetime import datetime
from typing import Literal

TitleType = Literal["movie", "show"]


@dataclass(frozen=True)
class WatchedItem:
    type: TitleType
    trakt_id: int
    imdb_id: str | None
    tmdb_id: int | None
    title: str
    year: int | None
    last_watched_at: datetime  # UTC-aware


@dataclass(frozen=True)
class Card:
    type: TitleType
    imdb_id: str
    tmdb_id: int | None
    title: str
    year: int | None
    last_watched_at: datetime  # UTC-aware
    poster_path: str | None  # None = not looked up yet, "" = no poster
