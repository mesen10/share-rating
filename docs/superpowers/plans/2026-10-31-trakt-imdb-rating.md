# Trakt → IMDb Rating Helper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local Flask page that shows 10 Trakt-watched titles not yet rated on IMDb, opens IMDb on click, and hides titles permanently on ✕.

**Architecture:** One Python package `share_rating`. Thin HTTP clients (Trakt, TMDB) and an IMDb CSV parser return plain dataclasses; `db.py` owns all SQLite access; `sync.py` orchestrates clients into the DB; `selection.py` is a pure function that picks cards; `web.py` is a server-rendered Flask app with a little JS for ✕. A CLI exposes `auth` (Trakt device flow) and `serve`.

**Tech Stack:** Python 3.15 (existing `.venv`), Flask, requests, SQLite (`sqlite3` stdlib), python-dotenv for `.env`, pytest, responses (HTTP mocking).

**Spec:** `docs/superpowers/specs/2026-10-31-trakt-imdb-rating-design.md`

## Global Constraints

- All code, comments, and documentation in English.
- Python + SQLite, runs locally; server binds `127.0.0.1` only, default port `8765`.
- The repo is **public** (`origin` = GitHub). Nothing personal is ever committed: no secrets, no Trakt/IMDb/TMDB ids or tokens, no real watch history or ratings, no usernames.
- Secrets and personal settings live in `.env` (git-ignored); only `.env.example` with empty values is committed. Trakt tokens live in the DB `kv` table, never in code or `.env`.
- Committed fixtures are synthetic; never commit the user's real CSV export or Trakt data.
- Before every commit, run `git status` and `git diff --cached` and confirm no personal data is staged. Never run `git push`; the user pushes.
- Trakt sync uses `/sync/watched/movies` and `/sync/watched/shows` only — never `/sync/history`.
- No automated requests to IMDb of any kind. IMDb input = uploaded CSV, parsed in memory, never written to disk. A bad CSV must never overwrite the stored ratings.
- "Rated" confirmations (`self_rated`) are permanent; CSV import never touches them.
- The `hidden` table is never modified by sync.
- Titles without an IMDb ID are never shown.
- Page copy: buttons `Sync` and `New 10`; IMDb link `https://www.imdb.com/title/<tt>/`, `target="_blank"`.
- Selection: 10 cards, 8 from last-watched within the last 5 years (`timedelta(days=1826)`), 2 older, random within each group, shortfall filled from the other group.

## Review Focus

1. Wrong file uploaded (Trakt export, an IMDb list export, PNG, BOM, odd header case): rejected with a message, stored ratings stay; a real export with a BOM still works. Pinned in Task 4 and Task 7.
2. Trakt access token expired: the client refreshes once and retries; if refresh fails, the page says to run `python -m share_rating auth`. Pinned in Task 3.
3. Trakt item with no IMDb ID or no TMDB ID, or TMDB down: no IMDb ID → never shown; no poster → placeholder, page still renders. Pinned in Task 2 and Task 5.
4. Backlog nearly empty (fewer than 10 candidates, or zero): page shows what exists; zero shows "All caught up". Pinned in Task 5 and Task 7.
5. A hidden or "Rated"-confirmed title that disappears from Trakt and returns, or is missing from a later CSV: never resurfaces. Pinned in Task 2 and Task 4.

---

## File Structure

```
share_rating/
  __init__.py
  __main__.py      CLI: `auth`, `serve`
  config.py        load .env / environment -> Config
  models.py        WatchedItem, Card dataclasses
  db.py            schema + all queries
  trakt.py         Trakt client: device auth, refresh, fetch watched
  imdb_csv.py      IMDb ratings CSV import
  tmdb.py          poster lookup
  selection.py     pick_cards (pure)
  sync.py          run_sync orchestration
  web.py           Flask app factory + routes
  templates/index.html
  static/app.js
  static/style.css
tests/
  conftest.py      tmp DB fixture
  fixtures/        synthetic IMDb CSV and Trakt JSON
  test_*.py        one per module
.env.example
pyproject.toml
README.md
.gitignore
```

---

### Task 1: Project scaffold, config, models

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `share_rating/__init__.py`, `share_rating/config.py`, `share_rating/models.py`, `tests/conftest.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `Config` (frozen dataclass): `trakt_client_id: str`, `trakt_client_secret: str`, `imdb_user_id: str`, `tmdb_api_key: str | None`, `db_path: Path` (default `share_rating.db` in the project root), `port: int` (default `8765`).
  - `load_config(env_path: Path = Path(".env")) -> Config` — reads `env_path` with python-dotenv (real environment variables win), keys `TRAKT_CLIENT_ID`, `TRAKT_CLIENT_SECRET`, `IMDB_USER_ID`, `TMDB_API_KEY`, `DB_PATH`, `PORT`. Empty string counts as missing. Raises `ConfigError` naming the missing key.
  - `WatchedItem` (frozen dataclass): `type: Literal["movie","show"]`, `trakt_id: int`, `imdb_id: str | None`, `tmdb_id: int | None`, `title: str`, `year: int | None`, `last_watched_at: datetime` (UTC-aware).
  - `Card` (frozen dataclass): `type`, `imdb_id: str`, `tmdb_id: int | None`, `title`, `year`, `last_watched_at: datetime`, `poster_path: str | None`.
  - `tests/conftest.py` fixture `conn` → a `sqlite3.Connection` on `tmp_path / "test.db"` with `db.init_db` applied (wire it up in Task 2; leave the fixture stub here).

- [ ] **Step 1:** The repo already exists (user ran `git init`; do not re-init). `.gitignore` with `.venv/`, `.idea/`, `.superpowers/`, `.env`, `*.db`, `*.db-*`, `tests/fixtures/private/`, `__pycache__/`, `.pytest_cache/`. `pyproject.toml`: package `share_rating`, deps `flask`, `requests`, `python-dotenv`; dev deps `pytest`, `responses`. Install: `.venv/bin/pip install -e '.[dev]'`.
- [ ] **Step 2: Write failing tests** in `tests/test_config.py` (use `monkeypatch.delenv` so the developer's real environment cannot leak in):
  - `test_load_config_reads_all_keys` — write a temp `.env` with all keys (fake values), assert each field.
  - `test_load_config_defaults` — omit `TMDB_API_KEY`, `DB_PATH`, `PORT`: assert `None`, `share_rating.db`, `8765`.
  - `test_load_config_missing_key_raises` — omit `IMDB_USER_ID`: `pytest.raises(ConfigError, match="IMDB_USER_ID")`.
  - `test_environment_overrides_env_file` — `monkeypatch.setenv("PORT", "9000")` beats `.env`.
- [ ] **Step 3:** Run `.venv/bin/pytest tests/test_config.py -v` — expect FAIL (import error).
- [ ] **Step 4:** Implement `config.py` and `models.py`. `.env.example` lists every key with an **empty** value and a comment on where to get it (Trakt app at `https://trakt.tv/oauth/applications`, redirect URI `urn:ietf:wg:oauth:2.0:oob`; TMDB key at `https://www.themoviedb.org/settings/api`; IMDb user id `ur...` from the profile URL, ratings list must be public).
- [ ] **Step 5:** Run tests — expect PASS.
- [ ] **Step 6: Commit** (include the spec and this plan). Stage files by name, not `git add .`; check `git status` shows no `.env`, `.idea/`, `.superpowers/`, or `*.db`. `git commit -m "chore: scaffold project, config and models"`

---

### Task 2: Database layer

**Files:**
- Create: `share_rating/db.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: `WatchedItem`, `Card` from Task 1.
- Produces:
  - `connect(path: Path) -> sqlite3.Connection` (row_factory = `sqlite3.Row`, foreign keys on) and `init_db(conn) -> None` (idempotent `CREATE TABLE IF NOT EXISTS`).
  - `replace_watched(conn, items: list[WatchedItem]) -> None` — one transaction: upsert every item keyed by `(type, trakt_id)`, **keep existing `poster_path`**, delete rows not in `items`.
  - `replace_imdb_ratings(conn, ratings: dict[str, int]) -> None` — one transaction: delete all, insert all.
  - `hide(conn, imdb_id: str) -> None` (idempotent).
  - `unrated_candidates(conn) -> list[Card]` — watched rows with non-null `imdb_id`, not in `imdb_ratings`, not in `hidden`.
  - `set_poster_path(conn, type: str, tmdb_id: int, poster_path: str) -> None` — `""` means "looked up, none".
  - `kv_get(conn, key: str) -> str | None`, `kv_set(conn, key: str, value: str) -> None`.

Schema:
```sql
CREATE TABLE IF NOT EXISTS watched (
  type TEXT NOT NULL CHECK (type IN ('movie','show')),
  trakt_id INTEGER NOT NULL,
  imdb_id TEXT, tmdb_id INTEGER,
  title TEXT NOT NULL, year INTEGER,
  last_watched_at TEXT NOT NULL,          -- ISO 8601 UTC
  poster_path TEXT,                       -- NULL = not looked up, '' = none
  PRIMARY KEY (type, trakt_id));
CREATE TABLE IF NOT EXISTS imdb_ratings (imdb_id TEXT PRIMARY KEY, rating INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS hidden (imdb_id TEXT PRIMARY KEY, hidden_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
```

- [ ] **Step 1:** Make the `conn` fixture call `connect` + `init_db`.
- [ ] **Step 2: Write failing tests** in `tests/test_db.py`:
  - `test_replace_watched_adds_updates_and_deletes` — insert A, B; replace with B' (new `last_watched_at`), C → rows are B', C.
  - `test_replace_watched_keeps_poster_path` — set poster on A, replace with A (new date) → `poster_path` unchanged.
  - `test_candidates_exclude_rated_hidden_and_no_imdb` — 4 items: rated, hidden, `imdb_id=None`, plain → only plain returned.
  - `test_hidden_survives_watched_reconcile` — hide X, `replace_watched([])`, `replace_watched([X])` → X not a candidate.
  - `test_replace_imdb_ratings_replaces_all` — `{"tt1":8}` then `{"tt2":7}` → only `tt2` stored.
  - `test_kv_roundtrip` — set/get; missing key → `None`.
- [ ] **Step 3:** Run `.venv/bin/pytest tests/test_db.py -v` — expect FAIL.
- [ ] **Step 4:** Implement `db.py`.
- [ ] **Step 5:** Run tests — expect PASS.
- [ ] **Step 6: Commit:** `git commit -am "feat: add SQLite storage layer"` (add new files first).

---

### Task 3: Trakt client

**Files:**
- Create: `share_rating/trakt.py`, `tests/fixtures/trakt_watched_movies.json`, `tests/fixtures/trakt_watched_shows.json`
- Test: `tests/test_trakt.py`

**Interfaces:**
- Consumes: `Config`, `WatchedItem`, `kv_get`/`kv_set`.
- Produces:
  - `class TraktAuthError(Exception)` — message tells the user to run `python -m share_rating auth`.
  - `class TraktClient(config: Config, conn: sqlite3.Connection, session: requests.Session | None = None)`
    - `device_auth(print_fn=print) -> None` — `POST /oauth/device/code`, print `user_code` + `verification_url`, poll `POST /oauth/device/token` every `interval` seconds until 200 (400 = pending; 404/409/410/418 = stop with `TraktAuthError`), store tokens.
    - `fetch_watched() -> list[WatchedItem]` — movies then shows.
  - Token storage: `kv` key `trakt_tokens`, JSON of the token response plus `created_at`.

Details the implementer needs:
- Base URL `https://api.trakt.tv`; headers `Content-Type: application/json`, `trakt-api-version: 2`, `trakt-api-key: <client_id>`, `Authorization: Bearer <access_token>`, plus a `User-Agent` such as `share-rating/0.1`.
- Endpoints: `GET /sync/watched/movies`, `GET /sync/watched/shows?extended=noseasons`.
- Movie entry: `{"last_watched_at": "...Z", "movie": {"title", "year", "ids": {"trakt", "imdb", "tmdb"}}}`; show entry: same with `"show"`. `ids.imdb`/`ids.tmdb` may be `null`.
- Refresh: if `created_at + expires_in` is less than 60 s away, or a request returns 401, `POST /oauth/token` with `grant_type=refresh_token`, `redirect_uri=urn:ietf:wg:oauth:2.0:oob`; retry the request once. Refresh failure or no stored tokens → `TraktAuthError`.
- Non-2xx other than 401 → `raise_for_status()` (sync must not reconcile on a failed fetch).

- [ ] **Step 1:** Create the two fixtures by hand with well-known public titles and made-up Trakt ids — never from the user's real account (2 movies — one with `"imdb": null`; 2 shows — one with `"tmdb": null`). Tests use fake client id/secret/tokens.
- [ ] **Step 2: Write failing tests** (use `responses`):
  - `test_fetch_watched_parses_movies_and_shows` — 4 `WatchedItem`s; types, ids, UTC-aware `last_watched_at`; the null ids come through as `None`.
  - `test_fetch_watched_sends_required_headers` — assert `trakt-api-key`, `trakt-api-version: 2`, `Authorization`.
  - `test_expired_token_refreshes_then_retries` — stored token with `created_at` long past; mock `/oauth/token` then `/sync/watched/*` → new token stored in `kv`, fetch succeeds.
  - `test_401_triggers_single_refresh` — first call 401, refresh 200, second call 200 → success; refresh called once.
  - `test_refresh_failure_raises_auth_error` — refresh returns 401 → `TraktAuthError`.
  - `test_no_tokens_raises_auth_error`.
  - `test_server_error_raises` — 503 → `requests.HTTPError`.
  - `test_device_auth_polls_until_token` — device code response with `interval: 0`; token endpoint 400 then 200 → tokens stored.
- [ ] **Step 3:** Run `.venv/bin/pytest tests/test_trakt.py -v` — expect FAIL.
- [ ] **Step 4:** Implement `trakt.py`.
- [ ] **Step 5:** Run tests — expect PASS.
- [ ] **Step 6: Commit:** `git commit -m "feat: add Trakt client with device auth and watched sync"`

---

### Task 4: IMDb CSV import and "Rated" confirmations

> Revised 2026-10-31: IMDb blocks automated requests (AWS WAF), so the scraper is replaced by CSV upload + in-app confirmations. See spec.

**Files:**
- Create: `share_rating/imdb_csv.py`, `tests/fixtures/imdb_ratings_sample.csv`
- Modify: `share_rating/config.py`, `.env.example`, `tests/test_config.py` (drop `IMDB_USER_ID`); `share_rating/db.py`, `tests/test_db.py` (add `self_rated`)
- Test: `tests/test_imdb_csv.py`

**Interfaces:**
- Consumes: `replace_imdb_ratings` (Task 2).
- Produces:
  - `Config` without `imdb_user_id`; `REQUIRED_KEYS = ("TRAKT_CLIENT_ID", "TRAKT_CLIENT_SECRET")`.
  - `class CsvImportError(Exception)`.
  - `parse_ratings_csv(data: bytes) -> dict[str, int]` — decode `utf-8-sig`; header match is case-insensitive and whitespace-trimmed; needs `Const` and `Your Rating` (else `CsvImportError` naming the missing column); keeps rows where `Const` matches `^tt\d+$` and rating is an int 1–10, skips others; zero kept rows → `CsvImportError`; undecodable / not CSV → `CsvImportError`.
  - `import_ratings_csv(conn, data: bytes) -> int` — parse, then `replace_imdb_ratings`; returns the count. On error nothing is written.
  - DB: table `self_rated (imdb_id TEXT PRIMARY KEY, rated_at TEXT NOT NULL)`; `mark_rated(conn, imdb_id: str) -> None` (idempotent); `unrated_candidates` also excludes `self_rated`.

- [ ] **Step 1:** Synthetic fixture `tests/fixtures/imdb_ratings_sample.csv` with the real export header `Const,Your Rating,Date Rated,Title,Original Title,URL,Title Type,IMDb Rating,Runtime (mins),Year,Genres,Num Votes,Release Date,Directors`, 3 well-known titles with made-up ratings, plus one row with an empty rating. Never use the user's real export.
- [ ] **Step 2: Write failing tests:**
  - `test_parse_sample_csv` — fixture → 3 entries, exact `{tt: rating}`; empty-rating row skipped.
  - `test_parse_handles_bom_and_header_case` — `b"\xef\xbb\xbfconst , YOUR RATING\ntt0000001,7\n"` → `{"tt0000001": 7}`.
  - `test_parse_missing_column_raises` — a Trakt-like CSV without `Your Rating` → `CsvImportError` matching `Your Rating`.
  - `test_parse_no_valid_rows_raises` — header only → `CsvImportError`.
  - `test_parse_binary_garbage_raises` — `b"\x89PNG\x00\xff"` → `CsvImportError`.
  - `test_import_replaces_ratings` and `test_failed_import_keeps_previous` (seed `{"tt1": 8}`, bad bytes → still a non-candidate).
  - In `tests/test_db.py`: `test_mark_rated_excludes_and_survives_csv_import` — `mark_rated`, then `replace_imdb_ratings({})` → still excluded; `mark_rated` twice is fine.
  - In `tests/test_config.py`: remove `IMDB_USER_ID` from fixtures; missing-key test uses `TRAKT_CLIENT_SECRET`.
- [ ] **Step 3:** Run `.venv/bin/pytest tests/test_imdb_csv.py tests/test_db.py tests/test_config.py -q` — expect FAIL.
- [ ] **Step 4:** Implement; remove `IMDB_USER_ID` from `.env.example` and add a comment on where to export ratings (IMDb → Your Ratings → Export).
- [ ] **Step 5:** Run the full suite — expect PASS.
- [ ] **Step 6: Commit:** `git commit -m "feat: import IMDb ratings from CSV and record in-app confirmations"`

---

### Task 5: Selection and posters

**Files:**
- Create: `share_rating/selection.py`, `share_rating/tmdb.py`
- Test: `tests/test_selection.py`, `tests/test_tmdb.py`

**Interfaces:**
- Consumes: `Card`, `set_poster_path`, `Config.tmdb_api_key`.
- Produces:
  - `pick_cards(candidates: list[Card], now: datetime, rng: random.Random, total: int = 10, recent: int = 8, window: timedelta = timedelta(days=1826)) -> list[Card]` — recent group = `last_watched_at >= now - window`; take `min(recent, len(recent_group))` from recent and fill to `total` from older, then top up from recent if older ran short; `rng.sample` within groups; result order: recent first, then older.
  - `poster_url(poster_path: str | None) -> str | None` — `https://image.tmdb.org/t/p/w342{poster_path}` or `None` for `None`/`""`.
  - `ensure_posters(conn, cards: list[Card], api_key: str | None, session=None) -> list[Card]` — for cards with `poster_path is None` and a `tmdb_id`: `GET https://api.themoviedb.org/3/{movie|tv}/{tmdb_id}?api_key=…`, store `poster_path` (`""` if null or 404). On network error / 5xx: leave unchanged, do not raise. No key → return cards unchanged. Returns cards with `poster_path` filled.

- [ ] **Step 1: Write failing tests** (`rng = random.Random(0)`, fixed `now`):
  - `test_pick_8_recent_2_older` — 20 recent + 20 older → 8 recent, 2 older, no duplicates.
  - `test_pick_fills_from_older_when_recent_short` — 3 recent + 20 older → 3 + 7.
  - `test_pick_fills_from_recent_when_older_short` — 20 recent + 0 older → 10 recent.
  - `test_pick_fewer_than_total` — 4 candidates → all 4.
  - `test_pick_empty` → `[]`.
  - `test_window_boundary` — card exactly at `now - 1826 days` counts as recent.
  - `test_pick_varies_with_rng` — two different seeds give different sets.
  - `test_ensure_posters_fetches_and_caches` (responses) — second call makes no HTTP request.
  - `test_ensure_posters_tv_uses_tv_endpoint`.
  - `test_ensure_posters_404_stores_empty` and `test_ensure_posters_500_leaves_null`.
  - `test_ensure_posters_without_key_or_tmdb_id_skips`.
- [ ] **Step 2:** Run `.venv/bin/pytest tests/test_selection.py tests/test_tmdb.py -v` — expect FAIL.
- [ ] **Step 3:** Implement both modules.
- [ ] **Step 4:** Run tests — expect PASS.
- [ ] **Step 5: Commit:** `git commit -m "feat: add card selection and TMDB posters"`

---

### Task 6: Sync orchestration

> Revised 2026-10-31: Trakt only; IMDb input is the CSV import (Task 4).

**Files:**
- Create: `share_rating/sync.py`
- Test: `tests/test_sync.py`

**Interfaces:**
- Consumes: `TraktClient.fetch_watched`, `TraktAuthError`, `replace_watched`, `kv_set`.
- Produces:
  - `SyncResult` (dataclass): `ok: bool`, `message: str`.
  - `run_sync(conn, trakt: TraktClient) -> SyncResult` — on success store `kv` `last_trakt_sync` (ISO UTC); message `"Synced <N> watched titles from Trakt"`. Errors never reconcile. Exact copy:
    - `TraktAuthError` → `"Trakt login expired. Run: python -m share_rating auth"`
    - `requests.RequestException` → `"Trakt sync failed: <error>"`

- [ ] **Step 1: Write failing tests** (fake Trakt client):
  - `test_sync_success_updates_watched` — rows stored, `ok`, message has the count, `kv` timestamp set.
  - `test_trakt_auth_error_message` — exact copy above.
  - `test_trakt_failure_does_not_wipe_watched` — fetch raises `HTTPError` → watched table unchanged, message starts `"Trakt sync failed"`.
- [ ] **Step 2:** Run `.venv/bin/pytest tests/test_sync.py -q` — expect FAIL.
- [ ] **Step 3:** Implement `sync.py`.
- [ ] **Step 4:** Run tests — expect PASS.
- [ ] **Step 5: Commit:** `git commit -m "feat: add Trakt sync orchestration"`

---

### Task 7: Web page

> Revised 2026-10-31: adds CSV upload and the "Rated ✓ / Not yet" confirmation.

**Files:**
- Create: `share_rating/web.py`, `share_rating/templates/index.html`, `share_rating/static/app.js`, `share_rating/static/style.css`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `unrated_candidates`, `pick_cards`, `ensure_posters`, `poster_url`, `hide`, `mark_rated`, `import_ratings_csv`, `CsvImportError`, `run_sync`, `TraktClient`.
- Produces: `create_app(config: Config, *, trakt_factory=TraktClient, rng: random.Random | None = None, now_fn=lambda: datetime.now(UTC)) -> Flask`. One DB connection per request (`flask.g`). `MAX_CONTENT_LENGTH = 20 MB`. `SECRET_KEY` random per process (flash only).

Routes:
- `GET /` — candidates → `pick_cards` → `ensure_posters` → render. Top bar: `"<N> unrated"`, `Sync` (form `POST /sync`), `New 10` (link to `/`), `Import IMDb CSV` (form `POST /import`, `multipart/form-data`, file field `csv`, `accept=".csv"`, submits on file choose). Grid 2 rows × 5 cards (CSS grid, 5 columns). Card: poster (`poster_url` or a grey placeholder with the title), title, year, `Movie`/`Show`, `Watched <Mon YYYY>`, ✕ button. Poster/title is `<a href="https://www.imdb.com/title/<tt>/" target="_blank" rel="noopener">`. Zero candidates → `"All caught up — nothing left to rate."`. When no IMDb ratings were ever imported (`imdb_ratings` empty and `kv` `last_csv_import` unset) show a hint: `"Import your IMDb ratings CSV once so already-rated titles are skipped."`. Flash messages above the grid.
- `POST /hide/<imdb_id>` and `POST /rated/<imdb_id>` — validate `^tt\d+$` (else 400), call `hide` / `mark_rated`, return 204.
- `POST /sync` — `run_sync(conn, trakt_factory(config, conn))`, flash its message, redirect `/`.
- `POST /import` — no file → flash `"Choose a CSV file first"`; `import_ratings_csv` → flash `"Imported <N> IMDb ratings"` and set `kv` `last_csv_import`; `CsvImportError` → flash `"CSV import failed, kept previous ratings: <error>"`. Redirect `/`. The upload is never written to disk.

`app.js`:
- Link click: let the browser open the tab (no `preventDefault`), then add class `asking` to the card, which shows an overlay with `Rated ✓` and `Not yet`.
- `Rated ✓` → `fetch` POST `/rated/<tt>` → remove card. `Not yet` → remove `asking`.
- ✕ → `fetch` POST `/hide/<tt>` → remove card; ✕ never triggers the link.
- On fetch failure keep the card and show an inline error.

- [ ] **Step 1: Write failing tests** (Flask test client, temp DB, seeded rows, `rng=Random(0)`):
  - `test_index_shows_10_cards_with_imdb_links` — 30 candidates → exactly 10 `href="https://www.imdb.com/title/tt` with `target="_blank"`; shows `30 unrated`.
  - `test_index_excludes_rated_confirmed_and_hidden`.
  - `test_index_empty_state` — `"All caught up"`.
  - `test_index_shows_import_hint_until_first_import`.
  - `test_index_renders_without_tmdb_key` — placeholder, 200.
  - `test_hide_and_rated_endpoints` — 204 each, titles gone from `/`; `POST /rated/notanid` → 400.
  - `test_import_csv_success` — upload the fixture → redirect; `/` shows `"Imported 3 IMDb ratings"`; those titles gone.
  - `test_import_csv_bad_file_keeps_ratings` — upload garbage → `"CSV import failed, kept previous ratings"`; earlier ratings still applied.
  - `test_import_without_file`.
  - `test_sync_flashes_message` — fake Trakt raising `TraktAuthError` → `/` shows `"Trakt login expired"`.
- [ ] **Step 2:** Run `.venv/bin/pytest tests/test_web.py -q` — expect FAIL.
- [ ] **Step 3:** Implement routes, template, JS, CSS.
- [ ] **Step 4:** Run the full suite — expect PASS.
- [ ] **Step 5: Commit:** `git commit -m "feat: add poster grid web page"`

---

### Task 8: CLI, README, end-to-end check

**Files:**
- Create: `share_rating/__main__.py`, `README.md`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `load_config`, `connect`, `init_db`, `TraktClient.device_auth`, `create_app`.
- Produces: `main(argv: list[str] | None = None) -> int` with subcommands `auth` and `serve [--no-browser]`. `serve` binds `127.0.0.1:<config.port>` and opens the browser via `webbrowser.open` unless `--no-browser`. `ConfigError` → print it, return 2.

- [ ] **Step 1: Write failing tests:**
  - `test_missing_config_returns_2` — no `.env` and empty environment → exit code 2, message names the missing key and says to copy `.env.example` to `.env`.
  - `test_serve_binds_localhost` — patch `Flask.run`, assert `host="127.0.0.1"`, `port=8765`.
- [ ] **Step 2:** Run `.venv/bin/pytest tests/test_cli.py -v` — expect FAIL.
- [ ] **Step 3:** Implement `__main__.py`. Write `README.md`: setup (copy `.env.example` to `.env`, create Trakt app, TMDB key, make IMDb ratings public), `python -m share_rating auth`, `python -m share_rating serve`, the rating workflow. Use placeholders only (`urXXXXXXXX`, `your-client-id`); no real ids or usernames.
- [ ] **Step 4:** Run the full suite `.venv/bin/pytest -v` — expect all PASS.
- [ ] **Step 5: Manual end-to-end with the user** (needs their real `.env`): run `auth`, `serve`, press `Sync`, confirm the unrated count looks plausible, click a card (IMDb opens), ✕ a card, rate one title on IMDb, `Sync` again → that title is gone. Report results faithfully.
- [ ] **Step 6: Commit:** `git commit -m "feat: add CLI and README"`
