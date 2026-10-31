"""Import ratings from IMDb's "Your Ratings" CSV export. The upload is parsed in memory only."""

import csv
import io
import re
import sqlite3

from share_rating import db

IMDB_ID = re.compile(r"^tt\d+$")
REQUIRED_COLUMNS = ("Const", "Your Rating")


class CsvImportError(Exception):
    pass


def parse_ratings_csv(data: bytes) -> dict[str, int]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CsvImportError("file is not a UTF-8 CSV") from None
    if "\x00" in text:
        raise CsvImportError("file is not a CSV")

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise CsvImportError("file is empty") from None
    except csv.Error as e:
        raise CsvImportError(f"cannot read CSV: {e}") from None

    columns = {name.strip().lower(): i for i, name in enumerate(header)}
    if "position" in columns:  # list and watchlist exports have it; the ratings export does not
        raise CsvImportError("this is an IMDb list or watchlist export, not 'Your Ratings'")
    missing = [c for c in REQUIRED_COLUMNS if c.lower() not in columns]
    if missing:
        raise CsvImportError(
            f"missing column(s) {', '.join(missing)}; is this the IMDb 'Your Ratings' export?"
        )
    id_col, rating_col = columns["const"], columns["your rating"]

    ratings = {}
    try:
        for row in reader:
            if len(row) <= max(id_col, rating_col):
                continue
            imdb_id, rating = row[id_col].strip(), row[rating_col].strip()
            if IMDB_ID.match(imdb_id) and rating.isdigit() and 1 <= int(rating) <= 10:
                ratings[imdb_id] = int(rating)
    except csv.Error as e:
        raise CsvImportError(f"cannot read CSV: {e}") from None

    if not ratings:
        raise CsvImportError("no ratings found in file")
    return ratings


def import_ratings_csv(conn: sqlite3.Connection, data: bytes) -> int:
    ratings = parse_ratings_csv(data)
    db.replace_imdb_ratings(conn, ratings)
    return len(ratings)
