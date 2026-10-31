import random
from datetime import datetime, timedelta

from share_rating.models import Card


def pick_cards(
    candidates: list[Card],
    now: datetime,
    rng: random.Random,
    total: int = 10,
    recent: int = 8,
    window: timedelta = timedelta(days=1826),
) -> list[Card]:
    """Pick `total` cards, `recent` of them watched within `window`; each group tops up the other."""
    cutoff = now - window
    recent_pool = [c for c in candidates if c.last_watched_at >= cutoff]
    older_pool = [c for c in candidates if c.last_watched_at < cutoff]

    n_recent = min(recent, len(recent_pool))
    n_older = min(total - n_recent, len(older_pool))
    n_recent = min(total - n_older, len(recent_pool))

    return rng.sample(recent_pool, n_recent) + rng.sample(older_pool, n_older)
