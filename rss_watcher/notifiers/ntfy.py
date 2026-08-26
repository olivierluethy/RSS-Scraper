# -*- coding: utf-8 -*-
"""ntfy notification backend."""

from __future__ import annotations

from typing import Any

import requests

from .base import Notifier


class NtfyNotifier(Notifier):
    name = "ntfy"

    def __init__(self, server: str, topic: str, default_priority: str = "default",
                 timeout: float = 10.0):
        if not topic:
            raise ValueError(
                "ntfy notifier requires a 'topic' (set it via config or the "
                "NTFY_TOPIC environment variable)"
            )
        self._server = server.rstrip("/")
        self._topic = topic
        self._default_priority = default_priority
        self._timeout = timeout

    @classmethod
    def from_config(cls, spec: dict[str, Any]) -> "NtfyNotifier":
        return cls(
            server=spec.get("server", "https://ntfy.sh"),
            topic=spec.get("topic", ""),
            default_priority=spec.get("default_priority", "default"),
            timeout=float(spec.get("timeout", 10.0)),
        )

    def send(self, title: str, body: str, priority: str = "default") -> None:
        headers = {
            "Title": title,
            "Priority": priority or self._default_priority,
        }
        resp = requests.post(
            f"{self._server}/{self._topic}",
            data=body.encode("utf-8"),
            headers=headers,
            timeout=self._timeout,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"HTTP {resp.status_code} – {resp.text}")
