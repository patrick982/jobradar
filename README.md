# jobradar

A small, self-hosted job radar. It scans several Austrian job boards, scores
every posting against a configurable profile, keeps track of which ads are
still live, and shows everything in a local web dashboard.

Built as a personal tool — and as a way to keep the whole stack (HTTP, HMAC
signing, SQLite, a small stdlib HTTP server, tests) in one honest, working
project.

> **How this was built.** This is an **AI-assisted** project. It was developed
> together with an AI coding assistant (opencode): I defined the requirements
> and direction, tested everything and use it day to day; most of the code was
> written by the assistant. I publish it as a real, working tool I use — with
> that stated openly, and not as a claim of hand-written code.

## Features

- **Multi-source scanning** — [karriere.at](https://www.karriere.at),
  [willhaben](https://www.willhaben.at), [jobs.at](https://www.jobs.at) and the
  AMS *alle jobs* API.
- **Configurable ranking** — keyword weights, mandatory "core" terms, penalties
  (e.g. `senior`, `leitung`) and boosts (`teilzeit`, `homeoffice`).
- **Liveness checks** — re-visits ads and marks them `live`, `expired` or
  `unknown`, so the list never shows dead postings.
- **Local dashboard** — plain HTML/JS front end served by a minimal HTTP API.
- **Status tracking** — mark jobs as `gemerkt`, `beworben`, `absage`, …
- **Tests** — `unittest` suite covering parsing, scoring, signing and the DB.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp config.example.json config.json   # adjust location / keywords / weights
export AMS_KEY="..."                 # optional, only for the AMS source

python3 radar.py scan                # query all sources, store + rank
python3 radar.py list --teilzeit     # print the best part-time matches
python3 radar.py serve               # http://127.0.0.1:8765
```

## CLI

| Command | What it does |
| --- | --- |
| `radar.py scan [--sources …] [--keywords …] [--check]` | Query sources, upsert into SQLite, re-rank |
| `radar.py rank` | Recompute scores for everything in the DB |
| `radar.py list [--teilzeit] [--show-expired] [--limit N]` | Print ranked jobs |
| `radar.py check [--min-score S] [--only-missing]` | Re-check ad liveness |
| `radar.py serve [--host H] [--port P]` | Start the dashboard |

## Configuration

`config.json` (see `config.example.json`) holds the search profile:

- `location` / `radius_km` — search area.
- `keywords` — one scan per keyword per source.
- `rank.core` + `core_penalty` — terms that must appear, or a penalty applies.
- `rank.weights` — per-term score deltas (positive and negative).
- `rank.boost`, `rank.employment`, `rank.location`, `rank.homeoffice` — bonus
  rules.

Secrets never live in the repo: the AMS API key is read from the `AMS_KEY`
environment variable (see `.env.example`).

## How the sources work

Each source is a small adapter in `jobradar/sources/` that turns a site's
response into a uniform `Job` (see `jobradar/models.py`):

| Source | Mechanism |
| --- | --- |
| karriere.at | Parses the embedded `window.VUE_INITIAL_STATE` JSON |
| willhaben | Public `publicapi.willhaben.at/jobs/v2/adverts` JSON API |
| jobs.at | JSON API (needs an `X-Requested-With` header) |
| AMS | `jobs.ams.at` search API with an **HMAC-SHA512** signed header |

The AMS request signature is the interesting part: the browser sends a random
nonce, a timestamp and an HMAC over `METHOD + path + sorted query + nonce/timestamp`
keyed with a secret embedded (obfuscated) in the site's JS. `jobradar` rebuilds
that request in `jobradar/sources/ams.py`.

## Project layout

```
radar.py                 # entry point
jobradar/
  cli.py                 # argparse subcommands
  config.py              # config loading + env overrides
  db.py                  # SQLite storage (schema + upsert + status)
  models.py              # the Job dataclass + helpers
  rank.py                # scoring
  liveness.py            # live/expired detection
  server.py              # dashboard HTTP API
  sources/               # one module per job board
  web/index.html         # dashboard UI
tests/                   # unittest suite
```

## Tests

```bash
python3 -m unittest discover -s tests
```

## Notes & limits

- Job boards change their markup; parsers are intentionally small and easy to
  fix.
- The AMS key rotates, so that source can temporarily return `401`.
- `jobs.at` keeps expired ads listed, so its liveness is reported as `unknown`.

## Stack

Python 3 (stdlib + `requests`) · SQLite · vanilla HTML/JS. No framework.
The dashboard is served by a small `http.server`-based API, not a web framework.
