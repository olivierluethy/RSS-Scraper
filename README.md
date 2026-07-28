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
- 🔎 **Case-insensitive keyword matching** on article titles.
- 🔔 **Instant push notifications** through ntfy (phone, desktop, or self-hosted server).
- 🧠 **De-duplication** — each article link is only reported once per run.
- ⏱️ **Configurable polling interval** (default: every 4 minutes).
- 🪶 **Minimal dependencies** — pure Python, three small libraries.
- 🖥️ **Two deployment modes** — run locally as a script, or keep it alive on a server.

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

1. Fetches every feed in `FEEDS` and reads the newest 15 entries.
2. Lower-cases each headline and checks it against the keywords in `SUCHWOERTER`.
3. On a new match (a link not seen before this run), sends a high-priority ntfy
   notification containing the headline, link, and timestamp.
4. Sleeps for `INTERVAL` seconds and repeats.

---

## Repository structure

| Path | Description |
|------|-------------|
| `server-version` | Full watcher with the complete ~50-feed list. Silent unless a match is found — ideal for long-running server deployments. |
| `standalone-version` | Slimmer variant with a 5-feed starter list. Also sends a low-priority **"no hits" status ping** every cycle, so you always know it's alive. |
| `20min-scrapper/` | Snapshot of the live server deployment (Passenger/cPanel), including `main.py` (identical to `server-version`), the `passenger_wsgi.py` wrapper, and runtime folders. |

---

## Requirements

- Python **3.8+**
- Dependencies:
  ```bash
  pip install feedparser requests
  ```

---

## Configuration

All settings live at the top of the script (`server-version` / `standalone-version` /
`20min-scrapper/main.py`):

| Setting | Meaning | Default |
|---------|---------|---------|
| `NTFY_SERVER` | ntfy base URL | `https://ntfy.sh` |
| `NTFY_TOPIC`  | Your **private** ntfy topic (treat like a secret) | *(set your own)* |
| `INTERVAL`    | Seconds between polling cycles | `240` (4 min) |
| `SUCHWOERTER` | List of keywords to match (case-insensitive) | `["helvetus", "stralium"]` |
| `FEEDS`       | List of RSS feed URLs to watch | ~50 Swiss feeds |

> ⚠️ **Security note:** the ntfy topic acts as a shared secret — anyone who knows it
> can read your alerts or post to it. Pick a long, random topic name and avoid
> committing real values (see the [roadmap](#roadmap) for moving config to
> environment variables).

---

## Usage

### 1. Get a notification channel

Install the **ntfy** app on your phone (iOS/Android) or use the web app, then
subscribe to the same topic string you set in `NTFY_TOPIC`.

### 2. Run locally (standalone)

```bash
pip install feedparser requests
python standalone-version
```

### 3. Run on a server (keep-alive)

```bash
# start in the background, surviving logout
nohup python server-version > watcher.log 2>&1 &
```

Check it's running with `ps aux | grep server-version`, and stop it with `kill <pid>`.
For a more robust setup, run it under **systemd**, **supervisor**, or **tmux/screen**
(see the [roadmap](#roadmap)).

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

Planned improvements are tracked as [GitHub Issues](../../issues) and grouped into
**features**, **bugs**, and **performance**. Highlights:

- Move configuration & secrets to environment variables / a config file.
- Persist the "seen articles" set across restarts.
- Fetch feeds concurrently and use conditional GETs (ETag / Last-Modified).
- Ship a proper service definition (systemd / Docker) instead of `nohup`.

Contributions and issue reports are welcome.

---

## License

No license file is currently included. Until one is added, all rights are reserved
by the repository owner. If you intend to reuse this code, please open an issue to
request clarification.
