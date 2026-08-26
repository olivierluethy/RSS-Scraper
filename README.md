# RSS-Scraper

A lightweight **RSS keyword watcher for Swiss news outlets**. It continuously polls a
curated list of Swiss news feeds, scans the latest headlines for one or more
keywords, and delivers an instant **push notification** via
[ntfy](https://ntfy.sh) the moment a matching article appears.

Originally built to track when specific terms surface across *20 Minuten, Blick,
Luzerner Zeitung, NZZ,* and *Tages-Anzeiger* — but the feed list and keywords are
fully configurable for any topic.

---

## Features

- 📰 **Multi-source polling** — watches ~50 RSS feeds across 5 major Swiss publishers.
- 🔎 **Flexible keyword matching** — substring, whole-word, or regex, over the
  title, summary, and/or category fields, with per-keyword priority.
- 🔔 **Pluggable notifications** — ntfy, e-mail (SMTP), Telegram, Slack, Discord;
  route to one backend or several at once.
- 🧠 **Persistent de-duplication** — reported links are stored in SQLite and
  survive restarts, so no duplicate alerts after a crash or deploy.
- ⚡ **Fast, polite fetching** — feeds are fetched concurrently with per-feed
  timeouts and conditional GETs (ETag / Last-Modified) to skip unchanged feeds.
- 🔐 **Externalised config** — one YAML file (plus env-var overrides); secrets
  like the ntfy topic stay out of source.
- 🖥️ **First-class deployment** — CLI, systemd unit, Docker/Compose, or Passenger WSGI.

---

## How it works

```
┌─────────────┐     poll every N sec     ┌──────────────────┐
│  RSS feeds  │ ───────────────────────▶ │   RSS-Scraper    │
│ (20min, NZZ │                          │  parse headlines │
│  Blick, …)  │                          │  match keywords  │
└─────────────┘                          └────────┬─────────┘
                                                  │ match found
                                                  ▼
                                         ┌──────────────────┐
                                         │   ntfy.sh topic  │──▶ 📱 push
                                         └──────────────────┘
```

On each cycle the scraper:

1. Fetches every feed concurrently (with timeouts and conditional GETs) and reads
   the newest `max_entries` entries of each.
2. Matches the configured keywords against the chosen fields (title/summary/category).
3. On a new match — a link not already in the persistent seen-store — sends a
   notification (to every configured backend) with the headline, link, and timestamp.
4. Records the link so it's never re-sent, then sleeps for `interval` seconds and repeats.

---

## Repository structure

The watcher now lives in a single package (`rss_watcher/`) — the one source of
truth. The scripts at the repo root are thin launchers that select a config profile.

| Path | Description |
|------|-------------|
| `rss_watcher/` | The watcher package: config, fetching, matching, storage, notifier backends, and the WSGI health app. Run with `python -m rss_watcher --config config.yaml`. |
| `config.example.yaml` | Full configuration reference (~50-feed list). Copy to `config.yaml` and edit. |
| `config.standalone.example.yaml` | Slim 5-feed profile that also sends a low-priority **"no hits" status ping** each cycle. |
| `server-version` | Thin launcher defaulting to `config.yaml`. |
| `standalone-version` | Thin launcher defaulting to `config.standalone.yaml`. |
| `20min-scrapper/` | Passenger/cPanel deployment: `main.py` (worker launcher) and `passenger_wsgi.py` (a real WSGI health endpoint that runs the poller in a background thread). |
| `deploy/rss-watcher.service` | systemd unit (`Restart=always`, journald logging). |
| `Dockerfile`, `docker-compose.yml` | Container deployment. |

---

## Requirements

- Python **3.9+**
- Dependencies:
  ```bash
  pip install -r requirements.txt   # feedparser, requests, PyYAML
  ```

---

## Configuration

All settings live in a YAML file. Copy the example and edit it — the real file is
git-ignored so secrets never get committed:

```bash
cp config.example.yaml config.yaml
```

Any value may reference an environment variable with `${VAR}` or `${VAR:-default}`.
A few settings can also be overridden directly via env vars: `NTFY_TOPIC`,
`NTFY_SERVER`, `INTERVAL`, `SUCHWOERTER` (comma-separated), `RSS_FEEDS`.

Key sections (see `config.example.yaml` for the full reference):

| Section | Meaning |
|---------|---------|
| `interval` / `max_entries` | Seconds between cycles; newest entries scanned per feed. |
| `fetch` | Connect/read timeouts, concurrency, conditional-GET toggle. |
| `matching` | `fields` (title/summary/category), `mode` (substring/word/regex), `case_sensitive`, and `keywords` (plain strings or per-keyword `{text, mode, priority, fields}`). |
| `storage` | SQLite `path` and `ttl_days` for the persistent seen-store. |
| `notifiers` | One or more backends: `ntfy`, `email`, `telegram`, `slack`, `discord`. |
| `feeds` | List of RSS feed URLs (auto de-duplicated). |

> ⚠️ **Security note:** the ntfy topic acts as a shared secret. Keep it in
> `config.yaml` / an env var (never in git), and **rotate** any topic that was
> previously committed to history.

---

## Usage

### 1. Get a notification channel

Install the **ntfy** app on your phone (iOS/Android) or use the web app, then
subscribe to the same topic string you set as `NTFY_TOPIC`.

### 2. Run locally

```bash
pip install -r requirements.txt
cp config.standalone.example.yaml config.standalone.yaml   # edit keywords/feeds
NTFY_TOPIC=your-private-topic python -m rss_watcher --config config.standalone.yaml
```

Add `--once` to run a single cycle and exit (handy for testing or cron).

### 3. Run on a server

**systemd (recommended):**

```bash
sudo cp deploy/rss-watcher.service /etc/systemd/system/
sudo mkdir -p /opt/rss-watcher
sudo cp -r rss_watcher config.yaml /opt/rss-watcher/
sudo systemctl daemon-reload && sudo systemctl enable --now rss-watcher
journalctl -u rss-watcher -f
```

**Docker / Compose:**

```bash
cp config.example.yaml config.yaml            # edit it
export NTFY_TOPIC=your-private-topic
docker compose up -d --build
```

**Passenger / cPanel:** point the app at `20min-scrapper/passenger_wsgi.py`; it
runs the poller in a background thread and serves a JSON health endpoint.

---

## Example notification

```
20min Alert: Helvetus / Stralium
─────────────────────────────────
NEUER ARTIKEL auf 20min!

Helvetus AG kündigt Expansion an

https://www.20min.ch/story/…

(2026-07-28 08:41:12)
```

---

## Roadmap

The initial roadmap — externalised config, persistent de-dup, concurrent +
conditional fetching, and proper service definitions — has now landed. Further
improvements and issue reports are welcome via [GitHub Issues](../../issues).

---

## License

No license file is currently included. Until one is added, all rights are reserved
by the repository owner. If you intend to reuse this code, please open an issue to
request clarification.
