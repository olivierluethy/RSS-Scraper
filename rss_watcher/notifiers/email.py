# -*- coding: utf-8 -*-
"""E-mail (SMTP) notification backend."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Any

from .base import Notifier


class EmailNotifier(Notifier):
    name = "email"

    def __init__(self, host: str, port: int, sender: str, recipients: list[str],
                 username: str | None = None, password: str | None = None,
                 use_tls: bool = True, timeout: float = 10.0):
        if not host or not sender or not recipients:
            raise ValueError("email notifier requires 'host', 'from' and 'to'")
        self._host = host
        self._port = port
        self._sender = sender
        self._recipients = recipients
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._timeout = timeout

    @classmethod
    def from_config(cls, spec: dict[str, Any]) -> "EmailNotifier":
        to = spec.get("to", [])
        if isinstance(to, str):
            to = [addr.strip() for addr in to.split(",") if addr.strip()]
        return cls(
            host=spec.get("smtp_host", ""),
            port=int(spec.get("smtp_port", 587)),
            sender=spec.get("from", ""),
            recipients=list(to),
            username=spec.get("username"),
            password=spec.get("password"),
            use_tls=bool(spec.get("use_tls", True)),
            timeout=float(spec.get("timeout", 10.0)),
        )

    def send(self, title: str, body: str, priority: str = "default") -> None:
        msg = EmailMessage()
        msg["Subject"] = title
        msg["From"] = self._sender
        msg["To"] = ", ".join(self._recipients)
        if priority in ("high", "urgent", "max"):
            msg["X-Priority"] = "1"
        msg.set_content(body)

        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password or "")
            smtp.send_message(msg)
