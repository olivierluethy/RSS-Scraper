# -*- coding: utf-8 -*-
"""Feed fetching: concurrent, timeout-bounded, and conditional.

Each feed is fetched with ``requests`` using an explicit ``(connect, read)``
timeout so a hanging host can't stall the cycle, and with conditional-GET
headers (``If-None-Match`` / ``If-Modified-Since``) so unchanged feeds are
skipped without re-parsing. Fetches run in a thread pool, turning cycle time
from the sum of feed latencies into roughly the slowest single feed.

Resolves GitHub issues #11 (concurrency), #12 (conditional GETs) and #13
(per-feed timeouts).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

import feedparser
import requests

from .config import FetchConfig

_USER_AGENT = "rss-watcher/1.0 (+https://github.com/olivierluethy/RSS-Scraper)"


@dataclass
class FeedResult:
    url: str
    entries: list[Any]
    etag: str | None = None
    modified: str | None = None
    not_modified: bool = False
    error: str | None = None


class FeedCache:
    """Remembers each feed's ETag / Last-Modified between cycles."""

    def __init__(self) -> None:
        self._etags: dict[str, str] = {}
        self._modified: dict[str, str] = {}

    def headers_for(self, url: str) -> dict[str, str]:
        headers: dict[str, str] = {}
        if url in self._etags:
            headers["If-None-Match"] = self._etags[url]
        if url in self._modified:
            headers["If-Modified-Since"] = self._modified[url]
        return headers

    def update(self, url: str, etag: str | None, modified: str | None) -> None:
        if etag:
            self._etags[url] = etag
        if modified:
            self._modified[url] = modified


def fetch_one(url: str, config: FetchConfig, cache: FeedCache) -> FeedResult:
    """Fetch and parse a single feed, honouring timeouts and conditional GETs."""
    headers = {"User-Agent": _USER_AGENT}
    if config.conditional_get:
        headers.update(cache.headers_for(url))

    try:
        resp = requests.get(
            url,
            headers=headers,
            timeout=(config.connect_timeout, config.read_timeout),
        )
    except requests.RequestException as exc:
        return FeedResult(url=url, entries=[], error=str(exc))

    if config.conditional_get and resp.status_code == 304:
        return FeedResult(url=url, entries=[], not_modified=True)

    if resp.status_code >= 400:
        return FeedResult(url=url, entries=[], error=f"HTTP {resp.status_code}")

    parsed = feedparser.parse(resp.content)
    etag = resp.headers.get("ETag")
    modified = resp.headers.get("Last-Modified")
    cache.update(url, etag, modified)
    return FeedResult(
        url=url,
        entries=list(parsed.entries),
        etag=etag,
        modified=modified,
    )


def fetch_all(feeds: list[str], config: FetchConfig, cache: FeedCache) -> list[FeedResult]:
    """Fetch every feed concurrently and return results as they complete."""
    if not feeds:
        return []
    workers = max(1, min(config.concurrency, len(feeds)))
    results: list[FeedResult] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_one, url, config, cache): url for url in feeds}
        for future in as_completed(futures):
            url = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:  # defensive: fetch_one already guards
                results.append(FeedResult(url=url, entries=[], error=str(exc)))
    return results
