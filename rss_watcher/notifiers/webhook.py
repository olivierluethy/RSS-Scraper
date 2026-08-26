# -*- coding: utf-8 -*-
"""Slack / Discord incoming-webhook notification backends."""

from __future__ import annotations

from typing import Any

import requests

from .base import Notifier


class SlackNotifier(Notifier):
    name = "slack"

    def __init__(self, webhook_url: str, timeout: float = 10.0):
        if not webhook_url:
            raise ValueError("slack notifier requires 'webhook_url'")
        self._webhook_url = webhook_url
        self._timeout = timeout

    @classmethod
    def from_config(cls, spec: dict[str, Any]) -> "SlackNotifier":
        return cls(
            webhook_url=spec.get("webhook_url", ""),
            timeout=float(spec.get("timeout", 10.0)),
        )

    def send(self, title: str, body: str, priority: str = "default") -> None:
        resp = requests.post(
            self._webhook_url,
            json={"text": f"*{title}*\n{body}"},
            timeout=self._timeout,
        )
        if resp.status_code not in (200, 204):
            raise RuntimeError(f"HTTP {resp.status_code} – {resp.text}")


class DiscordNotifier(Notifier):
    name = "discord"

    def __init__(self, webhook_url: str, timeout: float = 10.0):
        if not webhook_url:
            raise ValueError("discord notifier requires 'webhook_url'")
        self._webhook_url = webhook_url
        self._timeout = timeout

    @classmethod
    def from_config(cls, spec: dict[str, Any]) -> "DiscordNotifier":
        return cls(
            webhook_url=spec.get("webhook_url", ""),
            timeout=float(spec.get("timeout", 10.0)),
        )

    def send(self, title: str, body: str, priority: str = "default") -> None:
        resp = requests.post(
            self._webhook_url,
            json={"content": f"**{title}**\n{body}"},
            timeout=self._timeout,
        )
        if resp.status_code not in (200, 204):
            raise RuntimeError(f"HTTP {resp.status_code} – {resp.text}")
