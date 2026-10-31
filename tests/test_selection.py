import random
from datetime import UTC, datetime, timedelta

from share_rating.models import Card
from share_rating.selection import pick_cards

NOW = datetime(2026, 10, 31, tzinfo=UTC)
CUTOFF = NOW - timedelta(days=1826)


def cards(prefix, n, watched):
    return [Card("movie", f"tt{prefix}{i:05d}", None, f"T{i}", 2000, watched, None) for i in range(n)]


def recent(n):
    return cards("1", n, NOW - timedelta(days=30))


def older(n):
    return cards("2", n, NOW - timedelta(days=4000))


def split(result):
    r = [c for c in result if c.imdb_id.startswith("tt1")]
    o = [c for c in result if c.imdb_id.startswith("tt2")]
    return len(r), len(o)


def test_pick_8_recent_2_older():
    result = pick_cards(recent(20) + older(20), NOW, random.Random(0))
    assert split(result) == (8, 2)
    assert len({c.imdb_id for c in result}) == 10


def test_pick_orders_recent_first():
    result = pick_cards(older(20) + recent(20), NOW, random.Random(0))
    assert all(c.imdb_id.startswith("tt1") for c in result[:8])


def test_pick_fills_from_older_when_recent_short():
    assert split(pick_cards(recent(3) + older(20), NOW, random.Random(0))) == (3, 7)


def test_pick_fills_from_recent_when_older_short():
    assert split(pick_cards(recent(20), NOW, random.Random(0))) == (10, 0)


def test_pick_fewer_than_total():
    assert len(pick_cards(recent(2) + older(2), NOW, random.Random(0))) == 4


def test_pick_empty():
    assert pick_cards([], NOW, random.Random(0)) == []


def test_window_boundary():
    edge = cards("1", 1, CUTOFF) + older(20)
    assert split(pick_cards(edge, NOW, random.Random(0))) == (1, 9)


def test_pick_varies_with_rng():
    pool = recent(40) + older(40)
    a = {c.imdb_id for c in pick_cards(pool, NOW, random.Random(1))}
    b = {c.imdb_id for c in pick_cards(pool, NOW, random.Random(2))}
    assert a != b
