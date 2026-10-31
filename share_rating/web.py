"""Local web page: 10 unrated titles at a time, CSV import, Trakt sync."""

import random
import re
import secrets
from datetime import UTC, datetime

from flask import Flask, abort, flash, g, redirect, render_template, request, url_for

from share_rating import db
from share_rating.config import Config
from share_rating.imdb_csv import CsvImportError, import_ratings_csv
from share_rating.selection import pick_cards
from share_rating.sync import run_sync
from share_rating.tmdb import ensure_posters, poster_url
from share_rating.trakt import TraktClient

IMDB_ID = re.compile(r"^tt\d+$")


def create_app(
    config: Config,
    *,
    trakt_factory=TraktClient,
    rng: random.Random | None = None,
    now_fn=lambda: datetime.now(UTC),
) -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = secrets.token_hex(16)  # only signs flash messages
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
    rng = rng or random.Random()

    def get_conn():
        if "conn" not in g:
            g.conn = db.connect(config.db_path)
            db.init_db(g.conn)
        return g.conn

    @app.teardown_appcontext
    def close_conn(_exc):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.close()

    @app.template_filter("poster_url")
    def _poster_url(path):
        return poster_url(path)

    @app.get("/")
    def index():
        conn = get_conn()
        candidates = db.unrated_candidates(conn)
        cards = pick_cards(candidates, now_fn(), rng)
        cards = ensure_posters(conn, cards, config.tmdb_api_key)
        never_imported = (
            db.kv_get(conn, "last_csv_import") is None
            and conn.execute("SELECT 1 FROM imdb_ratings LIMIT 1").fetchone() is None
        )
        return render_template("index.html", cards=cards, unrated=len(candidates), never_imported=never_imported)

    def _imdb_id_or_400(imdb_id: str) -> str:
        if not IMDB_ID.match(imdb_id):
            abort(400)
        return imdb_id

    @app.post("/hide/<imdb_id>")
    def hide(imdb_id):
        db.hide(get_conn(), _imdb_id_or_400(imdb_id))
        return "", 204

    @app.post("/rated/<imdb_id>")
    def rated(imdb_id):
        db.mark_rated(get_conn(), _imdb_id_or_400(imdb_id))
        return "", 204

    @app.post("/sync")
    def sync():
        conn = get_conn()
        flash(run_sync(conn, trakt_factory(config, conn)).message)
        return redirect(url_for("index"))

    @app.post("/import")
    def import_csv():
        upload = request.files.get("csv")
        if upload is None or not upload.filename:
            flash("Choose a CSV file first")
            return redirect(url_for("index"))
        conn = get_conn()
        try:
            count = import_ratings_csv(conn, upload.read())
        except CsvImportError as e:
            flash(f"CSV import failed, kept previous ratings: {e}")
        else:
            db.kv_set(conn, "last_csv_import", datetime.now(UTC).isoformat())
            flash(f"Imported {count} IMDb ratings")
        return redirect(url_for("index"))

    return app
