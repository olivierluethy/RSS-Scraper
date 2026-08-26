# -*- coding: utf-8 -*-
"""Tests for the rss_watcher package covering the resolved issues."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rss_watcher import config as config_module
from rss_watcher.matching import Matcher
from rss_watcher.storage import SeenStore
from rss_watcher.watcher import Watcher


# ── Issue #5: title-less entries must not crash ────────────────────────────────

def test_matcher_handles_missing_title():
    cfg = config_module.from_dict({
        "matching": {"keywords": ["helvetus"], "fields": ["title"]},
    })
    matcher = Matcher(cfg.matching)
    # Entry without a title — used to raise AttributeError.
    assert matcher.match({"link": "http://x"}) is None
    assert matcher.match({"title": "Helvetus AG expands"}).keyword == "helvetus"


# ── Issue #9: summary/body, whole-word, regex, priority ────────────────────────

def test_matcher_word_boundary():
    cfg = config_module.from_dict({
        "matching": {"keywords": [{"text": "helvetus", "mode": "word"}]},
    })
    matcher = Matcher(cfg.matching)
    assert matcher.match({"title": "the helvetus deal"}) is not None
    assert matcher.match({"title": "helvetusarium unrelated"}) is None


def test_matcher_summary_and_regex_and_priority():
    cfg = config_module.from_dict({
        "matching": {
            "fields": ["title", "summary"],
            "keywords": [{"text": r"stral\w+", "mode": "regex", "priority": "urgent"}],
        },
    })
    matcher = Matcher(cfg.matching)
    m = matcher.match({"title": "nothing", "summary": "about stralium today"})
    assert m is not None and m.field == "summary" and m.priority == "urgent"


# ── Issue #4: feed de-duplication ──────────────────────────────────────────────

def test_feed_dedup():
    cfg = config_module.from_dict({"feeds": ["http://a", "http://b", "http://a"]})
    assert cfg.feeds == ["http://a", "http://b"]


# ── Issue #3 / #6: env-var substitution keeps secrets out of source ────────────

def test_env_substitution(monkeypatch):
    monkeypatch.setenv("NTFY_TOPIC", "secret-topic")
    cfg = config_module.from_dict({
        "notifiers": [{"type": "ntfy", "topic": "${NTFY_TOPIC}"}],
    })
    assert cfg.notifiers[0]["topic"] == "secret-topic"


# ── Issues #2 / #7: persistent, expiring seen-store ────────────────────────────

def test_seen_store_persists_and_expires(tmp_path):
    db = str(tmp_path / "seen.sqlite3")
    with SeenStore(db, ttl_days=30) as store:
        store.add("http://article/1")
        assert "http://article/1" in store

    # Reopen: the link is still remembered across "restarts".
    with SeenStore(db, ttl_days=30) as store:
        assert "http://article/1" in store
        # An old entry gets purged.
        store.add("http://article/old", when=0.0)
        removed = store.purge_expired()
        assert removed == 1
        assert "http://article/old" not in store
        assert "http://article/1" in store


# ── End-to-end cycle with a stubbed fetcher (no network) ───────────────────────

class _RecordingNotifier:
    name = "recording"

    def __init__(self):
        self.sent = []

    def send(self, title, body, priority="default"):
        self.sent.append((title, body, priority))


def test_run_cycle_dedup_and_notify(tmp_path, monkeypatch):
    from rss_watcher import watcher as watcher_module
    from rss_watcher.fetch import FeedResult

    cfg = config_module.from_dict({
        "feeds": ["http://feed"],
        "matching": {"keywords": ["helvetus"], "fields": ["title"]},
        "storage": {"path": str(tmp_path / "seen.sqlite3"), "ttl_days": 30},
        "notifiers": [],
    })
    w = Watcher(cfg)
    rec = _RecordingNotifier()
    w.notifiers._notifiers = [rec]

    entries = [
        {"title": "Helvetus AG expands", "link": "http://a/1"},
        {"link": "http://a/2"},                      # title-less, must be skipped safely
        {"title": "unrelated", "link": "http://a/3"},
    ]

    def fake_fetch_all(feeds, fetch_cfg, cache):
        return [FeedResult(url="http://feed", entries=list(entries))]

    monkeypatch.setattr(watcher_module, "fetch_all", fake_fetch_all)

    assert w.run_cycle() == 1          # only the Helvetus article
    assert len(rec.sent) == 1
    # Second cycle: already seen → no new notification (issue #2 de-dup).
    assert w.run_cycle() == 0
    assert len(rec.sent) == 1


def test_run_cycle_skips_not_modified(tmp_path, monkeypatch):
    from rss_watcher import watcher as watcher_module
    from rss_watcher.fetch import FeedResult

    cfg = config_module.from_dict({
        "feeds": ["http://feed"],
        "matching": {"keywords": ["helvetus"]},
        "storage": {"path": str(tmp_path / "seen.sqlite3")},
    })
    w = Watcher(cfg)
    w.notifiers._notifiers = [_RecordingNotifier()]

    monkeypatch.setattr(
        watcher_module, "fetch_all",
        lambda *a, **k: [FeedResult(url="http://feed", entries=[], not_modified=True)],
    )
    assert w.run_cycle() == 0
