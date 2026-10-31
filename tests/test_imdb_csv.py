from datetime import UTC, datetime
from pathlib import Path

import pytest

from share_rating import db
from share_rating.imdb_csv import CsvImportError, import_ratings_csv, parse_ratings_csv
from share_rating.models import WatchedItem

SAMPLE = (Path(__file__).parent / "fixtures" / "imdb_ratings_sample.csv").read_bytes()


def test_parse_sample_csv():
    assert parse_ratings_csv(SAMPLE) == {"tt0111161": 9, "tt0068646": 8, "tt0903747": 10}


def test_parse_handles_bom_and_header_case():
    assert parse_ratings_csv(b"\xef\xbb\xbfconst , YOUR RATING\ntt0000001,7\n") == {"tt0000001": 7}


def test_parse_skips_invalid_rows():
    data = b"Const,Your Rating\ntt0000001,7\nnm0000001,8\ntt0000002,11\ntt0000003,abc\n"
    assert parse_ratings_csv(data) == {"tt0000001": 7}


def test_parse_missing_column_raises():
    trakt_like = b"imdb_id,title,watched_at\ntt0000001,X,2024-01-01\n"
    with pytest.raises(CsvImportError, match="Your Rating"):
        parse_ratings_csv(trakt_like)


def test_parse_no_valid_rows_raises():
    with pytest.raises(CsvImportError):
        parse_ratings_csv(b"Const,Your Rating\n")


def test_parse_empty_file_raises():
    with pytest.raises(CsvImportError):
        parse_ratings_csv(b"")


def test_parse_binary_garbage_raises():
    with pytest.raises(CsvImportError):
        parse_ratings_csv(b"\x89PNG\x00\xff\xfe")


def seed(conn):
    db.replace_watched(conn, [
        WatchedItem("movie", 1, "tt0111161", None, "A", 1994, datetime(2024, 1, 1, tzinfo=UTC)),
        WatchedItem("movie", 2, "tt9999999", None, "B", 2000, datetime(2024, 1, 1, tzinfo=UTC)),
    ])


def candidate_ids(conn):
    return sorted(c.imdb_id for c in db.unrated_candidates(conn))


def test_import_replaces_ratings(conn):
    seed(conn)
    db.replace_imdb_ratings(conn, {"tt9999999": 5})
    assert import_ratings_csv(conn, SAMPLE) == 3
    assert candidate_ids(conn) == ["tt9999999"]


def test_failed_import_keeps_previous(conn):
    seed(conn)
    db.replace_imdb_ratings(conn, {"tt0111161": 8})
    with pytest.raises(CsvImportError):
        import_ratings_csv(conn, b"not,a,ratings,file\n1,2,3,4\n")
    assert candidate_ids(conn) == ["tt9999999"]
