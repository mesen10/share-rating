# Trakt → IMDb Rating Helper — Design

Date: 2026-10-31

## Intent and why

The user wants to rate, with their own IMDb account, every movie and show they have watched on Trakt.tv. It is hard to see which watched titles are still unrated on IMDb. This app compares the Trakt watch history with the user's IMDb ratings. When the user sits down now and then to rate in bulk, the app shows 10 unrated titles at a time. The user clicks a card to rate it on IMDb, or hides the title permanently.

Usage pattern: not regular; occasional sessions of bulk rating.

## Goals

- Keep the list of all watched Trakt movies and shows up to date with a cheap call. Backdated additions and removed entries must also be picked up.
- Fetch the titles the user has rated on IMDb automatically.
- A local web page that lists watched titles not yet rated on IMDb.
- 10 cards at a time: 8 from titles watched in the last 5 years, 2 from older watches.
- Clicking a card opens the IMDb title page in a new tab.
- An ✕ on a card removes that title from the list permanently.

## Non-goals

- Submitting ratings to IMDb from the app. Ratings are given by hand on the IMDb site.
- Per-episode ratings for shows. One rating per show is enough.
- Multiple users, remote hosting, login. Single user, runs locally.
- Writing ratings to Trakt.
- IMDb CSV import (not in the first version; added later if the scraper breaks).

## Anti-goals (failure even if it technically works)

- A hidden title coming back after a sync.
- A title already rated on IMDb appearing on the page (after the latest sync).
- A failed or partial IMDb scrape wiping the previous ratings list and bringing rated titles back onto the page.
- Re-fetching the full Trakt history page by page (`/sync/history`) on every sync.

## Constraints

- Language: Python. Database: SQLite. Runs locally on the user's Mac; the page opens on `localhost`.
- All code, comments, and documentation in English.
- IMDb has no official API for user ratings. The user will make their IMDb ratings list public. The app scrapes `imdb.com/user/<urID>/ratings`. If IMDb changes its page structure, the scraper can break.
- Trakt access: the user creates their own Trakt API app and connects via OAuth (the device code flow fits). Token refresh is stored.
- Poster images need a TMDB API key (Trakt gives no images, only TMDB IDs).
- Secrets (Trakt client id/secret, tokens, TMDB key, IMDb user id) live outside the code, in a local config/env file.

## Decided

### Data and sync

- **Trakt sync:** use `/sync/watched/movies` and `/sync/watched/shows`. These endpoints return all watched titles in one unpaginated response. Call both on every sync. Reconcile the local watched list with the response: add new titles, delete titles no longer on Trakt, update last-watched dates. This picks up backdated additions and removals automatically. (The `/sync/history` + `start_at` delta method is deliberately not used: `start_at` filters on watch date and misses backdated entries.)
- **Stored fields (per title):** Trakt ID, IMDb ID (`tt...`), TMDB ID, title, year, type (movie/show), last watched date (`last_watched_at`).
- **Shows:** one card per show. A show with even one watched episode counts as watched. Last watched date = the `last_watched_at` Trakt returns for the show.
- **IMDb sync:** scrape the full public ratings list every time. Store rated IMDb IDs and ratings. If the scrape fails or comes back partial, keep the previous ratings list; do not overwrite it.
- **Matching:** by IMDb ID. Trakt entries without an IMDb ID are not shown on the page.
- **Hidden titles:** a separate table. Sync never touches it.
- **Sync trigger:** the "Sync" button on the page only (no automatic sync on page load). Runs Trakt watched + full IMDb list, then picks 10 new cards.

### Page

- **Layout:** poster grid, 2 rows × 5 cards. Top bar: total unrated count, "Sync" button, "New 10" button.
- **Card content:** poster, title, year, movie/show label, last watched date, ✕ in the corner.
- **Selection rule:** candidate = watched, has an IMDb ID, not rated on IMDb, not hidden. 8 of the 10 cards come from titles *watched* in the last 5 years (measured by last watched date, not release year); 2 come from older watches. Random within each group. If a group has too few titles to fill its slots, fill the rest from the other group. "New 10" picks a new random set on every press.
- **Card click:** opens `https://www.imdb.com/title/<tt>/` in a new tab. The card stays on the page unchanged; it drops off after the next sync picks up the rating.
- **✕:** the card disappears immediately and the title is hidden permanently. No replacement card is added.
- **Hidden titles page:** not in the first version. There is no way to unhide a title for now.

## Left to the builder

- Web framework (Flask, FastAPI, etc.), templating/JS approach, visual design details.
- Database schema details, config file format.
- IMDb scraping technique (HTML parsing, embedded page JSON, etc.) and how to detect a partial scrape.
- OAuth setup flow and how the app is launched.
- Trakt rate limits and error handling details.
- Testing approach.
