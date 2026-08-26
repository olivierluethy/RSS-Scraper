# -*- coding: utf-8 -*-
"""Persistent de-duplication store for already-notified article links.

Backed by SQLite so the "seen" set survives crashes, deploys and reboots.
Entries carry a timestamp and are expired after ``ttl_days`` to bound file size.

Resolves GitHub issues #2 (duplicate notifications after restart) and #7
(persist seen articles across restarts, with expiry).
"""

from __future__ import annotations

import sqlite3
import time


class SeenStore:
    def __init__(self, path: str = "seen.sqlite3", ttl_days: int = 30):
        self._path = path
        self._ttl_seconds = ttl_days * 86400 if ttl_days and ttl_days > 0 else 0
        # check_same_thread=False: fetching happens in a thread pool, but writes
        # are funnelled through the single-threaded main loop.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS seen ("
            "  link TEXT PRIMARY KEY,"
            "  ts   REAL NOT NULL"
            ")"
        )
        self._conn.commit()

    def __contains__(self, link: str) -> bool:
        cur = self._conn.execute("SELECT 1 FROM seen WHERE link = ?", (link,))
        return cur.fetchone() is not None

    def add(self, link: str, *, when: float | None = None) -> None:
        ts = time.time() if when is None else when
        self._conn.execute(
            "INSERT OR REPLACE INTO seen (link, ts) VALUES (?, ?)", (link, ts)
        )
        self._conn.commit()

    def purge_expired(self, *, now: float | None = None) -> int:
        """Delete entries older than the TTL. Returns the number removed."""
        if not self._ttl_seconds:
            return 0
        cutoff = (time.time() if now is None else now) - self._ttl_seconds
        cur = self._conn.execute("DELETE FROM seen WHERE ts < ?", (cutoff,))
        self._conn.commit()
        return cur.rowcount

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM seen").fetchone()[0]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SeenStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
