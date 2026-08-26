# -*- coding: utf-8 -*-
"""The notifier interface all backends implement."""

from __future__ import annotations

from typing import Any


class Notifier:
    """Minimal delivery interface: ``send(title, body, priority)``."""

    name = "notifier"

    @classmethod
    def from_config(cls, spec: dict[str, Any]) -> "Notifier":
        raise NotImplementedError

    def send(self, title: str, body: str, priority: str = "default") -> None:
        raise NotImplementedError
