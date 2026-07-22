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
