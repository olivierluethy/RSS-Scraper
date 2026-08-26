# -*- coding: utf-8 -*-
"""Configuration loading and normalisation.

Configuration comes from a YAML file (see ``config.example.yaml``) with
``${ENV_VAR}`` / ``${ENV_VAR:-default}`` placeholders resolved from the
environment, so secrets (e.g. the ntfy topic) never have to live in source.

A handful of environment variables also act as direct overrides for the most
common settings, which makes container/systemd deployments a one-liner:

    NTFY_TOPIC, NTFY_SERVER, INTERVAL, SUCHWOERTER (comma-separated), RSS_FEEDS

Resolves GitHub issues #3 (secret out of source), #4 (feed de-duplication) and
#6 (single, externalised configuration).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

try:  # PyYAML is the only "heavy" optional dependency
    import yaml
except ImportError:  # pragma: no cover - surfaced as a clear error below
    yaml = None


# ────────────────────────────────────────────────
#          Environment-variable substitution
# ────────────────────────────────────────────────

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _substitute_env(value: Any) -> Any:
    """Recursively replace ``${VAR}`` / ``${VAR:-default}`` in strings."""
    if isinstance(value, str):
        def repl(match: "re.Match[str]") -> str:
            name, default = match.group(1), match.group(2)
            return os.environ.get(name, default if default is not None else "")

        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, list):
        return [_substitute_env(v) for v in value]
    if isinstance(value, dict):
        return {k: _substitute_env(v) for k, v in value.items()}
    return value


# ────────────────────────────────────────────────
#                 Config dataclasses
# ────────────────────────────────────────────────


@dataclass
class FetchConfig:
    connect_timeout: float = 5.0
    read_timeout: float = 10.0
    concurrency: int = 10
    conditional_get: bool = True


@dataclass
class MatchingConfig:
    # Normalised keyword specs: {"text", "mode", "priority", "fields"}
    keywords: list[dict[str, Any]] = field(default_factory=list)
    fields: list[str] = field(default_factory=lambda: ["title"])
    mode: str = "substring"  # substring | word | regex
    case_sensitive: bool = False


@dataclass
class StorageConfig:
    path: str = "seen.sqlite3"
    ttl_days: int = 30


@dataclass
class Config:
    interval: int = 240
    max_entries: int = 15
    status_ping: bool = False
    fetch: FetchConfig = field(default_factory=FetchConfig)
    matching: MatchingConfig = field(default_factory=MatchingConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    notifiers: list[dict[str, Any]] = field(default_factory=list)
    feeds: list[str] = field(default_factory=list)


# ────────────────────────────────────────────────
#                    Normalisation
# ────────────────────────────────────────────────


def _normalise_keywords(raw: Any, default_mode: str, default_priority: str) -> list[dict[str, Any]]:
    """Accept either ["helvetus", ...] or [{"text": ..., "priority": ...}, ...]."""
    keywords: list[dict[str, Any]] = []
    for item in raw or []:
        if isinstance(item, str):
            spec = {"text": item}
        elif isinstance(item, dict) and item.get("text"):
            spec = dict(item)
        else:
            continue
        spec.setdefault("mode", default_mode)
        spec.setdefault("priority", default_priority)
        spec.setdefault("fields", None)  # None => use global matching.fields
        keywords.append(spec)
    return keywords


def _dedupe_feeds(feeds: list[str]) -> list[str]:
    """De-duplicate feed URLs while preserving order (issue #4)."""
    cleaned = [f.strip() for f in feeds if isinstance(f, str) and f.strip()]
    return list(dict.fromkeys(cleaned))


def _default_notifier_priority(notifiers: list[dict[str, Any]]) -> str:
    for n in notifiers:
        if n.get("default_priority"):
            return str(n["default_priority"])
    return "default"


def from_dict(data: dict[str, Any]) -> Config:
    """Build a validated :class:`Config` from a raw mapping."""
    data = _substitute_env(data or {})

    fetch = FetchConfig(**{k: v for k, v in (data.get("fetch") or {}).items()
                           if k in FetchConfig.__dataclass_fields__})
    storage = StorageConfig(**{k: v for k, v in (data.get("storage") or {}).items()
                               if k in StorageConfig.__dataclass_fields__})

    notifiers = list(data.get("notifiers") or [])

    raw_matching = data.get("matching") or {}
    default_mode = raw_matching.get("mode", "substring")
    default_priority = _default_notifier_priority(notifiers)
    matching = MatchingConfig(
        keywords=_normalise_keywords(raw_matching.get("keywords"), default_mode, default_priority),
        fields=list(raw_matching.get("fields") or ["title"]),
        mode=default_mode,
        case_sensitive=bool(raw_matching.get("case_sensitive", False)),
    )

    cfg = Config(
        interval=int(data.get("interval", 240)),
        max_entries=int(data.get("max_entries", 15)),
        status_ping=bool(data.get("status_ping", False)),
        fetch=fetch,
        matching=matching,
        storage=storage,
        notifiers=notifiers,
        feeds=_dedupe_feeds(list(data.get("feeds") or [])),
    )
    _apply_env_overrides(cfg)
    return cfg


def _apply_env_overrides(cfg: Config) -> None:
    """Convenience overrides for the most common settings."""
    if os.environ.get("INTERVAL"):
        cfg.interval = int(os.environ["INTERVAL"])

    suchwoerter = os.environ.get("SUCHWOERTER")
    if suchwoerter:
        words = [w.strip() for w in suchwoerter.split(",") if w.strip()]
        priority = _default_notifier_priority(cfg.notifiers)
        cfg.matching.keywords = _normalise_keywords(words, cfg.matching.mode, priority)

    feeds = os.environ.get("RSS_FEEDS")
    if feeds:
        cfg.feeds = _dedupe_feeds([f.strip() for f in feeds.split(",")])

    # ntfy overrides are applied per-notifier so `NTFY_TOPIC` alone works even
    # when the topic isn't spelled out in the config file.
    for notifier in cfg.notifiers:
        if notifier.get("type") == "ntfy":
            if os.environ.get("NTFY_SERVER"):
                notifier["server"] = os.environ["NTFY_SERVER"]
            if os.environ.get("NTFY_TOPIC"):
                notifier["topic"] = os.environ["NTFY_TOPIC"]

    # If no notifier is configured at all but an ntfy topic is present in the
    # environment, wire up a sensible default so a bare deployment still works.
    if not cfg.notifiers and os.environ.get("NTFY_TOPIC"):
        cfg.notifiers = [{
            "type": "ntfy",
            "server": os.environ.get("NTFY_SERVER", "https://ntfy.sh"),
            "topic": os.environ["NTFY_TOPIC"],
            "default_priority": "high",
        }]


def load(path: str | None = None) -> Config:
    """Load configuration from ``path`` (falling back to env-only config)."""
    data: dict[str, Any] = {}
    if path:
        if yaml is None:
            raise RuntimeError(
                "PyYAML is required to read a config file. Install it with "
                "`pip install PyYAML` or configure via environment variables."
            )
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    return from_dict(data)
