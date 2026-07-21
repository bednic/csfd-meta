# CSFD Kodi Metadata Scraper — Design

**Date:** 2026-07-20
**Status:** Approved design, ready for implementation planning

## Summary

A self-contained Kodi **Omega (21)** metadata scraper addon that pulls movie and
TV-series metadata from [CSFD.cz](https://www.csfd.cz). It is a native Python
scraper (extension points `xbmc.metadata.scraper.movies` and
`xbmc.metadata.scraper.tvshows`) driven by Kodi's library scanner.

CSFD.cz has **no public API**, so the addon scrapes and parses server-rendered
HTML. The design's central discipline is a **strict separation** between a pure,
Kodi-agnostic CSFD parsing core and a thin Kodi glue layer — so parsing is fully
unit-testable offline and a hosted backend can be swapped in later without
touching the Kodi layer.

> **Anti-bot wall (discovered during implementation, 2026-07-20):** csfd.cz is
> fronted by **Anubis** (techaro.lol, v1.24.0), a JavaScript proof-of-work bot
> wall. Plain HTTP fetches (and header-rotation approaches like node-csfd-api)
> receive a trap page — "Ujišťujeme se, že nejste robot!" — not real HTML.
> Login cookies do not help; the wall sits in front of the login page too.
> The client defeats it by **solving the proof-of-work in pure Python** (no
> browser, no account): parse the `anubis_challenge` JSON, brute-force a nonce
> where `sha256(randomData + nonce)` has `difficulty` leading zero hex digits
> (difficulty is currently 1 — a few hashes), call the `pass-challenge`
> endpoint to obtain the `techaro.lol-anubis-auth` cookie, cache it, and retry.
> This lives entirely inside `client.py`; the parser layer is unaffected.

## Goals & Scope

### In scope (v1)

- **Content:** Movies and TV series.
- **Metadata:** all four groups —
  - Core text: title, original title, year, plot/outline, runtime, country,
    genres, tagline.
  - Ratings: CSFD % mapped to Kodi's 0–10 scale, plus vote count.
  - Cast & crew: actors (with roles), directors, writers.
  - Artwork: poster(s) and fanart from CSFD's gallery.
- **TV depth:** rich **show-level** data + **episode titles / S-E numbers** so
  every episode file matches. Per-episode plot/art kept minimal (only what CSFD
  readily exposes).
- **Title language:** display title defaults to the Czech title (original goes to
  `originaltitle`); an addon **setting** lets the user prefer the original title
  as display.
- **Distribution:** installable zip.

### Out of scope (v1, deferred)

- Full per-episode metadata (plots, stills, per-episode cast).
- Trailers (setting stub present, disabled).
- Hosted backend service (architecture keeps the door open; not built).
- Personal/official Kodi repo submission.

## Architecture

Core principle: **CSFD domain logic knows nothing about Kodi; Kodi glue knows
nothing about HTML.** The `csfd/` package is the clean seam a future backend
would sit behind — swap `client.py`'s fetch-and-parse for an HTTP call to a
server and the Kodi layer is unchanged.

```
csfd-meta/
├── addon.xml                     # Kodi manifest (2 scraper extension points)
├── addon.py                      # thin entry point → router
├── resources/
│   ├── settings.xml              # Omega-format settings
│   ├── language/                 # Czech + English strings
│   └── lib/
│       ├── kodi/                 # Kodi-facing layer ("glue")
│       │   ├── router.py         #   parse action= params, dispatch
│       │   ├── movie_scraper.py  #   find / getdetails for movies
│       │   ├── tv_scraper.py     #   find / getdetails / episodes for shows
│       │   └── mapping.py        #   CsfdItem → Kodi InfoTagVideo (ONLY Kodi-API file)
│       └── csfd/                 # Pure domain layer (NO Kodi imports)
│           ├── client.py         #   HTTP fetch (requests) + caching + rate-limit
│           ├── search.py         #   parse /hledat/ → [SearchResult]
│           ├── film.py           #   parse film/series page → CsfdFilm
│           ├── episodes.py       #   parse series episode list → [CsfdEpisode]
│           └── models.py         #   dataclasses: SearchResult, CsfdFilm, CsfdEpisode, Person…
└── tests/
    ├── fixtures/                 # saved real CSFD HTML snapshots
    └── test_*.py                 # offline parser tests
```

Both scraper extension points share the same `csfd/` core.

**Parsing library:** BeautifulSoup4 (`script.module.beautifulsoup4`) with CSS
selectors — forgiving of malformed HTML and readable/easy to update when CSFD
changes layout. Speed is irrelevant at this request volume; resilience wins over
lxml/XPath.

## Kodi scraper flow

`addon.py → router.py` parses the `action=` parameter and dispatches. All data
crosses from `csfd/` to `kodi/` as plain dataclasses; `mapping.py` is the only
place that touches Kodi APIs.

### Movies

| Action | Kodi sends | We do | We return |
|---|---|---|---|
| `NfoUrl` | contents of a local `.nfo` | scan for a `csfd.cz/film/...` URL | that URL (skips search) |
| `find` | `title`, `year` | `csfd.search()` | list of ListItems, each with CSFD URL + uniqueid `csfd`, label, year, thumb |
| `getdetails` | chosen CSFD `url` | `csfd.film()` → `mapping.py` | one ListItem with full `VideoInfoTag`; end via `xbmcplugin.setResolvedUrl(handle, True, li)` |

### TV shows

Same `NfoUrl` / `find` / `getdetails` for the show, plus:

| Action | Kodi sends | We do | We return |
|---|---|---|---|
| `getepisodelist` | show `url` | `csfd.episodes()` | one ListItem per episode with `title`, `season`, `episode`, per-episode `url` |
| `getepisodedetails` | an episode `url` | minimal parse (title, aired if present) | ListItem with the episode's `VideoInfoTag` |

`getepisodelist` is the workhorse (every episode file matches by S/E);
`getepisodedetails` is deliberately thin per the chosen TV scope.

### Mapping details (`mapping.py`, Omega `InfoTagVideo` setters — not deprecated `setInfo`)

- `setUniqueIDs({'csfd': id}, 'csfd')` — stable identity across re-scrapes/refresh.
- `setRatings({'csfd': (value_0_to_10, votes)}, defaultrating='csfd')` — CSFD % ÷ 10.
- `setCast([xbmc.Actor(name, role, order, thumb), …])`, `setDirectors`, `setWriters`.
- `setTitle` / `setOriginalTitle` driven by the title-language setting.
- `li.setArt({'poster':…, 'fanart':…})` + `addAvailableArtwork` for extras.

## CSFD client, resilience & testing

### `client.py`

- **HTTP:** `requests` with a full, coherent modern-browser header set
  (`User-Agent`, `Sec-Ch-Ua`, `Sec-Fetch-*`, `Accept`, `Accept-Language: cs-CZ`)
  for consistent Czech markup. ~10s timeout, 2–3 retries with backoff for
  transient failures.
- **Anubis proof-of-work wall:** csfd.cz is fronted by Anubis. On any response
  that is the trap page, the client parses the `anubis_challenge` JSON, solves
  the PoW (`sha256(randomData + nonce)` with `difficulty` leading zero hex
  digits), GETs `/.within.website/x/cmd/anubis/api/pass-challenge` with a cookie
  jar to obtain `techaro.lol-anubis-auth`, caches that cookie, and retries the
  original request. Pure `hashlib` — no browser, no account. Re-solves when the
  cached auth cookie expires.
- **Caching:** parsed results cached to
  `special://profile/addon_data/...` keyed by URL, with TTL (default ~7 days,
  configurable). Search results: short TTL; film pages: long TTL.
- **Rate limiting:** enforced small delay between requests so a large library
  scan doesn't hammer CSFD or get blocked.

### Defensive parsing

- Every field extracted **independently and wrapped** — a missing/renamed block
  degrades that one field to `None`/empty and logs a warning; it never aborts the
  scrape. Partial results beat nothing.
- CSFD URL/ID normalization in one place: `/film/12345-nazev/` → id `12345`,
  canonical URL; handles film vs series vs episode sub-pages.
- Toward Kodi: any hard failure returns **empty results cleanly** so the scanner
  moves on rather than hanging.

### Testing strategy (core defense against layout drift)

- **Fixture-based unit tests:** real CSFD HTML snapshots under `tests/fixtures/`
  (film, series, search page, episode list). Parser tests run **fully offline**
  and assert exact dataclass output. The regression net — no Kodi, no network.
- **Live canary test:** separate, network-marked, run manually or scheduled in
  CI. Fetches a couple of known-stable titles live and checks key fields still
  populate — the early-warning system for CSFD layout changes, before users hit
  broken scrapes.
- **Maintenance loop:** canary fails → re-save fixture from live page → update
  selector → fixture test locks in the fix.

The zero-Kodi-dependency parser layer is what makes `pytest` run the whole domain
suite anywhere.

## Settings (`resources/settings.xml`, Omega format)

- **Title language** — display title = Czech (default) or Original.
- **Fetch trailers?** — off by default (stub, out of v1 scope).
- **Cache TTL (days)** — default 7.
- **Max artwork per type** — cap posters/fanart from gallery (default 5).
- **Enable debug logging** — verbose parser logging for chasing layout breaks.

## Dependencies (`addon.xml` `<requires>`)

- `xbmc.python` `3.0.1` (Omega).
- `script.module.requests`
- `script.module.beautifulsoup4`
- `script.module.certifi`

All are official Kodi-repo modules — installed automatically, nothing vendored.

## Distribution

- **v1:** distributable zip ("Install from zip file").
- **Later (optional):** personal Kodi repo for auto-updates; eventual official
  Kodi repo submission.

## Build order (backbone of the implementation plan)

Each step is independently testable. Steps 1–4 are pure Python (no Kodi); real
Kodi testing begins at step 5.

1. **Domain models + client** — dataclasses, HTTP fetch, consent cookie, caching.
2. **Search parser** + fixtures/tests.
3. **Film parser** + fixtures/tests (all four metadata groups).
4. **Episode parser** + fixtures/tests.
5. **Kodi skeleton** — `addon.xml`, `addon.py`, `router.py`, settings, language
   files; installs cleanly in Kodi.
6. **Movie scraper glue + mapping** — wire find/getdetails; scrape a real movie.
7. **TV scraper glue** — show find/getdetails + getepisodelist/getepisodedetails.
8. **Canary test + polish** — live early-warning test, logging, README.

## Key risks

- **HTML layout drift** (primary) — mitigated by fixture tests + live canary +
  defensive per-field parsing.
- **Anubis anti-bot wall** — mitigated by the pure-Python PoW solver. Works at
  any SHA difficulty (currently 1); would break only if CSFD switches to a
  JS-only or "slow" challenge mode, which the live canary would flag.
- **Sparse CSFD episode data** — mitigated by scoping TV to show-level + episode
  titles in v1.
