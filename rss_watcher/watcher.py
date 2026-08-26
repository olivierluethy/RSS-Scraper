# -*- coding: utf-8 -*-
"""Watcher orchestration: fetch → match → de-dup → notify.

Ties together configuration, concurrent fetching, matching, the persistent
seen-store and the notifier backends into a single polling loop that every
entrypoint (CLI, systemd, Docker, Passenger WSGI) shares.
"""

from __future__ import annotations

import argparse
import datetime
import threading
import time

from . import config as config_module
from .config import Config
from .fetch import FeedCache, fetch_all
from .matching import Matcher
from .notifiers import NotifierGroup, build_notifiers
from .storage import SeenStore


class Watcher:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.matcher = Matcher(cfg.matching)
        self.store = SeenStore(cfg.storage.path, cfg.storage.ttl_days)
        self.notifiers = NotifierGroup(build_notifiers(cfg.notifiers))
        self.cache = FeedCache()
        self._stop = threading.Event()

    # ────────────────────────────────────────────────
    #                    One cycle
    # ────────────────────────────────────────────────

    def run_cycle(self) -> int:
        """Run a single fetch/match/notify pass. Returns the number of hits."""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        results = fetch_all(self.cfg.feeds, self.cfg.fetch, self.cache)
        hits = 0

        for result in results:
            if result.error:
                print(f"Feed-Fehler bei {result.url}: {result.error}")
                continue
            if result.not_modified:
                continue

            for entry in result.entries[: self.cfg.max_entries]:
                match = self.matcher.match(entry)
                if not match:
                    continue

                link = entry.get("link", "") if hasattr(entry, "get") else ""
                if not link or link in self.store:
                    continue

                title = (entry.get("title", "") if hasattr(entry, "get") else "").strip()
                title = title or "(ohne Titel)"
                message = (
                    f"NEUER ARTIKEL!\n\n"
                    f"{title}\n\n"
                    f"{link}\n\n"
                    f"(Treffer: '{match.keyword}' in {match.field}, {now})"
                )

                print("\n" + "═" * 80)
                print(message)
                print("═" * 80 + "\n")

                self.notifiers.send(
                    f"RSS Alert: {match.keyword}",
                    message,
                    priority=match.priority,
                )
                self.store.add(link)
                hits += 1

        purged = self.store.purge_expired()
        if purged:
            print(f"→ {purged} abgelaufene Einträge entfernt")

        if hits == 0 and self.cfg.status_ping:
            keywords = ", ".join(k["text"] for k in self.cfg.matching.keywords)
            self.notifiers.send(
                "RSS Watcher: keine Treffer",
                f"Status-Check ({now})\n\nKeine neuen Artikel mit:\n{keywords}",
                priority="low",
            )
            print("→ Keine Treffer – Statusmeldung gesendet")

        return hits

    # ────────────────────────────────────────────────
    #                    Main loop
    # ────────────────────────────────────────────────

    def run_forever(self) -> None:
        self._banner()
        while not self._stop.is_set():
            try:
                self.run_cycle()
            except Exception as exc:  # keep the loop alive across cycle failures
                print(f"Zyklus-Fehler: {exc}")
            self._stop.wait(self.cfg.interval)

    def stop(self) -> None:
        self._stop.set()

    def _banner(self) -> None:
        keywords = ", ".join(k["text"] for k in self.cfg.matching.keywords)
        backends = ", ".join(self.notifiers.names) or "(keine)"
        print("RSS Watcher gestartet\n")
        print(f"Suche nach: {keywords}")
        print(f"Felder: {', '.join(self.cfg.matching.fields)}")
        print(f"Feeds: {len(self.cfg.feeds)} | Intervall: {self.cfg.interval}s")
        print(f"Benachrichtigung über: {backends}")
        print(f"Speicher: {self.cfg.storage.path} (bereits gesehen: {self.store.count()})\n")


# ────────────────────────────────────────────────
#                   CLI entrypoint
# ────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RSS keyword watcher")
    parser.add_argument("-c", "--config", help="Path to a YAML config file")
    parser.add_argument("--once", action="store_true",
                        help="Run a single cycle and exit (useful for testing/cron)")
    args = parser.parse_args(argv)

    cfg = config_module.load(args.config)
    if not cfg.feeds:
        print("Keine Feeds konfiguriert – bitte 'feeds' in der Config setzen.")
        return 1

    watcher = Watcher(cfg)
    if args.once:
        watcher._banner()
        hits = watcher.run_cycle()
        print(f"\nFertig. {hits} Treffer.")
        return 0

    try:
        watcher.run_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
