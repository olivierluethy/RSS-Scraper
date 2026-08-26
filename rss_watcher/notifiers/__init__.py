# -*- coding: utf-8 -*-
"""Pluggable notification backends.

Every backend implements the small :class:`Notifier` interface
(``send(title, body, priority)``) and is selected via configuration, so alerts
can be routed to ntfy, e-mail, Telegram, Slack/Discord — or several at once.

Resolves GitHub issue #10 (additional notification backends).
"""

from __future__ import annotations

from typing import Any

from .base import Notifier
from .ntfy import NtfyNotifier
from .email import EmailNotifier
from .telegram import TelegramNotifier
from .webhook import SlackNotifier, DiscordNotifier

_REGISTRY: dict[str, type[Notifier]] = {
    "ntfy": NtfyNotifier,
    "email": EmailNotifier,
    "telegram": TelegramNotifier,
    "slack": SlackNotifier,
    "discord": DiscordNotifier,
}


def build_notifiers(specs: list[dict[str, Any]]) -> list[Notifier]:
    """Instantiate notifier backends from a list of config dicts."""
    notifiers: list[Notifier] = []
    for spec in specs:
        spec = dict(spec)
        kind = spec.pop("type", None)
        if not kind:
            raise ValueError("Each notifier needs a 'type' field")
        if kind not in _REGISTRY:
            raise ValueError(
                f"Unknown notifier type '{kind}'. "
                f"Available: {', '.join(sorted(_REGISTRY))}"
            )
        notifiers.append(_REGISTRY[kind].from_config(spec))
    return notifiers


class NotifierGroup:
    """Fan a single alert out to every configured backend.

    A failure in one backend is logged but never blocks the others.
    """

    def __init__(self, notifiers: list[Notifier]):
        self._notifiers = notifiers

    def __bool__(self) -> bool:
        return bool(self._notifiers)

    @property
    def names(self) -> list[str]:
        return [n.name for n in self._notifiers]

    def send(self, title: str, body: str, priority: str = "default") -> None:
        for notifier in self._notifiers:
            try:
                notifier.send(title, body, priority)
            except Exception as exc:  # noqa: BLE001 - isolate backends
                print(f"[notifier:{notifier.name}] send failed: {exc}")


__all__ = [
    "Notifier",
    "NotifierGroup",
    "build_notifiers",
    "NtfyNotifier",
    "EmailNotifier",
    "TelegramNotifier",
    "SlackNotifier",
    "DiscordNotifier",
]
