# share-rating

Find the movies and shows you watched on [Trakt](https://trakt.tv) but have not rated on IMDb yet.
A local web page shows 10 unrated titles at a time: 8 watched in the last 5 years, 2 older.
Click a card to open its IMDb page and rate it there, then confirm "Rated ✓" back on the page.
Click ✕ to never see a title again.

Everything runs locally. IMDb is never contacted automatically: your existing IMDb ratings come
from IMDb's own CSV export, which you upload yourself.

## Setup

1. Create a virtualenv and install:

   ```bash
   python -m venv .venv
   .venv/bin/python -m pip install -e '.[dev]'
   ```

2. Copy the settings template. `.env` is git-ignored; never commit it.

   ```bash
   cp .env.example .env
   ```

3. Create a Trakt API app at <https://trakt.tv/oauth/applications> with redirect URI
   `http://localhost:8510/callback` (login uses a device code, so this page is never opened). Put its client id in `.env`
   (`TRAKT_CLIENT_ID=your-client-id`). New Trakt apps show the client secret as "Not issued";
   leave `TRAKT_CLIENT_SECRET` empty then. Older apps that have one can set it.

4. Optional, for posters: get a TMDB API key at <https://www.themoviedb.org/settings/api>
   and set `TMDB_API_KEY` in `.env`. Without it, cards show a plain placeholder.

5. Log in to Trakt (prints a code to enter at trakt.tv/activate):

   ```bash
   .venv/bin/python -m share_rating auth
   ```

## Use

```bash
.venv/bin/python -m share_rating serve
```

The page opens at <http://127.0.0.1:8510/>.

1. **First time:** on IMDb go to *Your Ratings → Export*, download the CSV, and upload it with
   **Import IMDb CSV**. Titles you already rated are skipped from then on. Re-importing later is
   optional; it only tidies up.
2. Press **Sync** to pull your watched movies and shows from Trakt.
3. Click a card to open IMDb in a new tab and rate it. Back on the page, answer
   **Rated ✓** (the title is gone for good) or **Not yet**.
4. **✕** hides a title permanently. **New 10** shows another random set.

Your data (Trakt tokens, watch list, ratings) lives in `share_rating.db`, which is git-ignored.

## Tests

```bash
.venv/bin/pytest
```
