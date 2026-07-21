# Design: LAN Anubis relay for the CSFD addon

Date: 2026-07-21
Status: Approved (pending spec review)

## Background

csfd.cz sits behind the Anubis proof-of-work bot wall (v1.24.0). The addon's
pure-Python solver works from a normal desktop/server (standard OpenSSL → a
"trusted" TLS fingerprint, reliable HTTP 302), but on the target device — a
Google TV / Android TV dongle running Kodi — every submission is rejected
`403 "invalid response."` even though the proof is mathematically correct, the
source IP is identical, and the challenge/submit ride the same warmed socket.
Extensive on-device testing (timing sweeps, elapsed-time reporting, TCP
keep-alive, single-connection warm-up) confirmed the block is the **device's
TLS fingerprint**, which stock `requests` in Kodi cannot spoof. On-device
Anubis solving is therefore a dead end.

## Goal

Move Anubis solving off the dongle onto a normal-fingerprint, always-on host
(the user's NAS/home server), and have the addon fetch csfd pages through it.

## Non-goals

- No on-device Anubis solving (removed entirely).
- No parsing/scraping changes — the addon keeps its existing, tested HTML
  parsing and Kodi mapping.
- No authentication on the relay (LAN-only; documented).
- No relay-side disk cache (the long-lived process reuses the auth cookie; the
  addon keeps its own HTML cache).

## Architecture

Thin relay (HTML proxy). Two deploy units in one repo:

- **Addon** (`resources/lib/csfd`, `resources/lib/kodi`): unchanged parsing/
  mapping. `CsfdClient` is rewritten to be **relay-only** — it fetches raw HTML
  from the relay and caches it. It contains no Anubis logic. `anubis.py` is
  removed from the addon.
- **Relay** (`relay/`, self-contained, Dockerised): solves Anubis and returns
  raw csfd HTML over HTTP. Holds a long-lived `requests` session so it solves
  once and reuses the `techaro.lol-anubis-auth` cookie across requests.

The addon cannot scrape without a relay configured — this is intentional.

### Data flow

```
Kodi find/getdetails
  → addon build_client(settings)  → CsfdClient(relay_url=<setting>)
  → GET {relay_url}/fetch?url=<csfd url>        (LAN)
  → relay AnubisFetcher.get(csfd url)
       → GET csfd url; if Anubis trap: solve + pass-challenge; refetch
       → raw HTML
  → relay returns HTML (200)
  → addon parses HTML exactly as today (search/film/episodes → mapping)
```

## Components

### Addon: `resources/lib/csfd/client.py` (rewritten)

`CsfdClient(relay_url, cache_dir=None, ttl_seconds=..., session=None)`:

- `get(url, ttl=None)`: cache lookup (unchanged logic) → on miss, fetch via
  relay → cache HTML → return.
- Relay fetch: `GET {relay_url.rstrip('/')}/fetch?url=<quote(url)>` with a
  ~30 s timeout (Anubis solve may take a moment). Non-200 raises so the caller
  logs a fetch failure (same failure surface as today).
- No throttle (LAN hop is cheap; the relay throttles csfd). No Anubis, no
  keep-alive/socket tuning, no delay sweep, no diagnostics.

`anubis.py` is deleted from `resources/lib/csfd`. Nothing else in the addon
imports it (only the old `client.py` did).

### Addon: settings

`resources/settings.xml` gains a `relay_url` string setting (label `#30005`),
pre-defined with the user's NAS default `http://nas:7878`. Added to both
`strings.po` files. `Settings.relay_url` property returns
`getSettingString("relay_url")`.

`movie_scraper.build_client` passes `relay_url=settings.relay_url` (tv_scraper
already reuses `build_client`).

### Relay: `relay/` (self-contained, zero third-party deps beyond requests)

- `relay/anubis.py`: moved verbatim from the addon (`is_trap`, `parse_challenge`,
  `solve`, `pass_challenge_url`, `error_reason`, `AnubisError`).
- `relay/fetcher.py`: `AnubisFetcher` — a simplified solver (the pre-debugging
  direct-mode logic). Long-lived `requests.Session`; `get(url)`:
  fetch → if `anubis.is_trap`: parse, solve, submit pass-challenge, refetch
  (bounded retries) → return HTML. Polite throttle (`min_interval=1.0`) to
  csfd. `elapsedTime` and connection handling are the simple immediate-submit
  form (works on the host's normal fingerprint).
- `relay/app.py`: stdlib `http.server` (`BaseHTTPRequestHandler`,
  `ThreadingHTTPServer`). One shared `AnubisFetcher`. Binds `0.0.0.0:PORT`
  (`PORT` env, default `7878`).
- `relay/Dockerfile`: `python:3-slim`, `pip install requests` (its `certifi`
  comes as a dependency; no parsing libs — the relay does not parse HTML). Copy
  `relay/`. `CMD ["python", "app.py"]`.
- `relay/docker-compose.yml`: port map `7878:7878`, `restart: unless-stopped`.
  No volume (stateless).
- `relay/tests/`: `test_app.py`, `test_fetcher.py`, and the relocated
  `test_anubis.py`.

### Relay HTTP API

- `GET /fetch?url=<url-encoded csfd url>`
  - 400 if `url` missing or its host is not `www.csfd.cz` / scheme not `https`
    (SSRF guard).
  - 200 `text/html; charset=utf-8` with the raw page on success.
  - 502 if the fetcher fails (Anubis unsolved, network error, csfd non-200).
- `GET /health` → 200 `ok`.
- Any other path/method → 404.

## Error handling

- Relay unreachable / non-200 → addon `CsfdClient.get` raises → the scraper's
  existing `try/except` in `router._dispatch` logs `csfd: action ... failed`
  and returns no results (identical to today's fetch-failure behavior).
- Relay: exceptions in the fetcher are caught per-request and returned as 502
  with a short reason in the body; the process stays up.
- SSRF: only `https://www.csfd.cz/...` URLs are fetched.

## Caching

- Addon keeps its existing profile-dir HTML cache (TTL from `cache_ttl_days`),
  which prevents most relay round-trips.
- Relay is stateless on disk; its long-lived session reuses the Anubis auth
  cookie, so it re-solves only when the cookie expires.

## Security

- LAN-only, no auth (documented in README). Bind to the LAN; do not expose the
  port to the internet.
- SSRF guard restricts fetches to `www.csfd.cz`.

## Testing

- `relay/tests/test_anubis.py`: relocated solver/parse/error_reason tests.
- `relay/tests/test_fetcher.py`: with a fake session — solves a trap then
  returns real HTML; passes raw HTML through; raises on repeated trap.
- `relay/tests/test_app.py`: `/fetch` returns the fetcher's HTML; rejects
  non-csfd URL (400); missing url (400); fetcher error → 502; `/health` 200.
  Uses a fake fetcher injected into the handler.
- Addon `tests/test_client.py`: rewritten for relay mode — `get` issues
  `GET {relay_url}/fetch?url=...` and returns the body; cache hit avoids a
  second relay call; non-200 raises.
- Existing parsing tests (`test_search`, `test_film`, `test_episodes`,
  `test_mapping`, `test_router`, `test_movie_scraper`, `test_tv_mapping`,
  `test_urls`, `test_canary`) unchanged.

## Migration / cleanup

- Delete the on-device scaffolding: delay sweep, `_warm`, single-connection
  keep-alive session, `min_solve_seconds`/`solve_delays`, X-Real-Ip diagnostic
  logging, and the `now`-clock plumbing added for it.
- Move `anubis.py` (and its tests) from the addon to the relay.
- Version bump (addon `0.2.0`: relay is a breaking change to how it fetches).
- README: relay build/run on the NAS (docker compose up -d) and setting the
  addon's Relay URL to `http://nas:7878` (the pre-filled default).

## Out of scope

- Shared auth-cookie approach (rejected: the JWT's `restriction` claim likely
  binds it to the solving fingerprint).
- Relay authentication, HTTPS/TLS on the relay, multi-site support.
