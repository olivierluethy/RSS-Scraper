# -*- coding: utf-8 -*-
"""Telegram bot notification backend."""

from __future__ import annotations

from typing import Any

import requests

from .base import Notifier


class TelegramNotifier(Notifier):
    name = "telegram"

    def __init__(self, bot_token: str, chat_id: str, timeout: float = 10.0):
        if not bot_token or not chat_id:
            raise ValueError("telegram notifier requires 'bot_token' and 'chat_id'")
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._timeout = timeout

    @classmethod
    def from_config(cls, spec: dict[str, Any]) -> "TelegramNotifier":
        return cls(
            bot_token=spec.get("bot_token", ""),
            chat_id=str(spec.get("chat_id", "")),
            timeout=float(spec.get("timeout", 10.0)),
        )

    def send(self, title: str, body: str, priority: str = "default") -> None:
        text = f"*{title}*\n\n{body}"
        resp = requests.post(
            f"https://api.telegram.org/bot{self._bot_token}/sendMessage",
            json={
                "chat_id": self._chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_notification": priority in ("min", "low"),
            },
            timeout=self._timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code} – {resp.text}")
