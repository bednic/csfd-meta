# CSFD Kodi Metadata Scraper (metadata.csfd)

Scrapes movie and TV-series metadata from [CSFD.cz](https://www.csfd.cz) for
Kodi **Omega (21)**.

## Features
- Movies and TV series (show-level metadata + episode titles/numbering)
- Core text, CSFD rating (as 0–10), cast & crew, poster/fanart artwork
- Configurable display-title language (Czech default, original optional)
- Disk caching + polite rate limiting

## Entry points
Kodi's metadata-scraper extension point does not pass a content-type
parameter, so the addon ships two separate entry scripts registered against
the two scraper extension points in `addon.xml`:
- `addon_movie.py` — `xbmc.metadata.scraper.movies`
- `addon_tv.py` — `xbmc.metadata.scraper.tvshows`

Both dispatch into the shared, Kodi-free library under `resources/lib/`.

## Install
Build the zip and install it in Kodi via *Add-ons → Install from zip file*:

    make zip

Then set CSFD as the information provider for your Movies / TV Shows sources.

## Library layout for TV series

Kodi matches your files to scraped metadata by **folder/file names**, not by
the CSFD ids. If the layout below isn't followed, the show is found but its
episodes stay unmatched (no titles/plots, or attached to the wrong episode).

### Folder structure

Use one folder per show, a `Season NN` subfolder per season, and one file per
episode:

```
TV Shows/                         <- source, scanned with content = "TV shows"
└─ Tom a Jerry (1940)/            <- one folder per show; include the year
   ├─ tvshow.nfo                  <- optional; pins the exact CSFD match
   ├─ Season 01/
   │  ├─ Tom a Jerry S01E01.mkv
   │  └─ Tom a Jerry S01E02.mkv
   └─ Season 02/
      └─ Tom a Jerry S02E01.mkv
```

- **Set the source content type to *TV shows*** and pick CSFD as the scraper.
  Point the scraper at the show folder, not at loose files.
- **Put the year in the show folder name** — `Show Name (YYYY)`. Many CSFD
  titles are identical and differ only by year (e.g. *Tom a Jerry* is a 2021
  film *and* a 1940 series); the year lets the automatic match land on the
  right entry, and it's what the manual "choose" dialog shows in the list.
- **One `Season NN` subfolder per season.** Use `Specials` (or `Season 00`)
  for specials.

### Episode numbering must match CSFD

Episode files **must carry an `SxxExx` tag** (`S01E03`, `s1e3`, `1x03`, …) and
those numbers **must match CSFD's numbering**, because that is the only key
Kodi uses to line a file up with a scraped episode:

- Multi-season shows are numbered `SxxExx` exactly as CSFD lists them on the
  show's *Epizody* tab.
- Single-season shows are numbered `Exx` on CSFD and map to **season 1**, so
  name those files `S01Exx`.

CSFD's ordering can differ from TVDB/TMDB. If an episode comes back wrong,
check the show's *Epizody* tab on csfd.cz and rename the file to the season/
episode number shown there.

### Pinning the exact show (optional)

To skip title search and bind a folder to one specific CSFD entry, drop a
`tvshow.nfo` in the show folder containing just the CSFD URL:

```
https://www.csfd.cz/film/69266-tom-a-jerry/
```

Kodi's *NfoUrl* action hands that URL straight to the scraper, so the match is
exact regardless of how many same-named shows exist. A per-episode `.nfo`
next to an episode file works the same way with that episode's CSFD URL.

## Anti-bot wall
CSFD.cz sits behind an [Anubis](https://anubis.techaro.lan/) proof-of-work
wall. `CsfdClient` solves the PoW challenge in pure Python before returning
real HTML, so no extra configuration is needed — but it does mean requests
are slower than a plain HTTP GET, and the wall can occasionally block
requests from datacenter/CI IP ranges. The live canary tests need a real
(non-datacenter) network path to succeed.

## Development
    python -m pip install -r requirements-dev.txt
    pytest                 # offline unit tests (fixtures)
    pytest -m network      # live canary tests (hit CSFD, needs real network)

When CSFD changes layout, a canary test fails: re-capture the relevant
fixture under `tests/fixtures/` and update the selectors until green.

## Anubis relay (required)

csfd.cz is behind the Anubis bot wall, which blocks the Android TV / Kodi TLS
fingerprint. The addon therefore fetches pages through a small relay that runs
on a normal-fingerprint, always-on host (e.g. a NAS) and solves Anubis there.

### Run the relay (on the NAS)

```bash
# uses the published image bednic/anubis-relay
cd relay
docker compose up -d
curl -s http://localhost:9753/health   # -> ok
```

### Point the addon at it

In the addon settings, set **Anubis relay URL** to `http://<nas-host>:9753`
(default `http://nas:9753`). Without a reachable relay the addon cannot scrape.

### Build/push the image (maintainer)

```bash
cd relay
docker build -t bednic/anubis-relay:latest -t bednic/anubis-relay:0.2.0 .
docker push bednic/anubis-relay:latest
docker push bednic/anubis-relay:0.2.0
```
