# -*- coding: utf-8 -*-
"""Keyword matching against RSS entries.

Supports matching on multiple entry fields (title / summary / category),
substring, whole-word and regex modes, case sensitivity, and per-keyword
priority. Missing fields are handled gracefully so a title-less or otherwise
malformed entry can never abort a feed.

Resolves GitHub issues #5 (crash on title-less entries) and #9 (match on
summary/body, regex, whole words, per-keyword priority).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .config import MatchingConfig


@dataclass
class Match:
    keyword: str
    priority: str
    field: str


def _extract_field(entry: Any, name: str) -> str:
    """Return a searchable string for ``name`` from a feedparser entry.

    Uses ``.get`` semantics so absent fields yield an empty string instead of
    raising ``AttributeError`` (issue #5). ``category`` is special-cased to also
    include the list of ``tags``.
    """
    if name == "category":
        parts: list[str] = []
        cat = entry.get("category") if hasattr(entry, "get") else None
        if cat:
            parts.append(str(cat))
        for tag in entry.get("tags", []) if hasattr(entry, "get") else []:
            term = tag.get("term") if isinstance(tag, dict) else getattr(tag, "term", None)
            if term:
                parts.append(str(term))
        return " ".join(parts)

    value = entry.get(name, "") if hasattr(entry, "get") else getattr(entry, name, "")
    return str(value) if value else ""


class Matcher:
    """Compiles keyword specs from config into fast, reusable matchers."""

    def __init__(self, config: MatchingConfig):
        self._case_sensitive = config.case_sensitive
        self._default_fields = config.fields or ["title"]
        self._compiled: list[tuple[str, str, list[str], "re.Pattern[str]"]] = []

        flags = 0 if config.case_sensitive else re.IGNORECASE
        for spec in config.keywords:
            text = str(spec["text"])
            mode = spec.get("mode") or config.mode
            priority = spec.get("priority") or "default"
            fields = spec.get("fields") or self._default_fields
            pattern = self._compile(text, mode, flags)
            self._compiled.append((text, priority, list(fields), pattern))

    @staticmethod
    def _compile(text: str, mode: str, flags: int) -> "re.Pattern[str]":
        if mode == "regex":
            return re.compile(text, flags)
        if mode == "word":
            # \b works for ASCII word boundaries; keeps `helvetus` from matching
            # inside a larger token (issue #9).
            return re.compile(r"\b" + re.escape(text) + r"\b", flags)
        # default: substring
        return re.compile(re.escape(text), flags)

    def match(self, entry: Any) -> Match | None:
        """Return the first :class:`Match` for ``entry``, or ``None``.

        A missing title is fine — the entry is simply searched on whatever
        fields *are* present.
        """
        # Cache extracted field values across keywords for this entry.
        field_cache: dict[str, str] = {}
        for text, priority, fields, pattern in self._compiled:
            for field_name in fields:
                if field_name not in field_cache:
                    field_cache[field_name] = _extract_field(entry, field_name)
                haystack = field_cache[field_name]
                if haystack and pattern.search(haystack):
                    return Match(keyword=text, priority=priority, field=field_name)
        return None
