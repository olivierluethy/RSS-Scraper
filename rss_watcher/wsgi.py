# -*- coding: utf-8 -*-
"""A real WSGI application for Passenger / gunicorn deployments.

The polling loop can't itself be a WSGI callable (it's an infinite loop, not a
request handler). This module runs the :class:`~rss_watcher.watcher.Watcher` in
a background thread and exposes ``application`` — a genuine WSGI app serving a
JSON health/status endpoint.

Resolves GitHub issue #1 (invalid Passenger entrypoint).
"""

from __future__ import annotations

import json
import os
import threading

from . import config as config_module
from .watcher import Watcher

_watcher: Watcher | None = None
_thread: threading.Thread | None = None
_lock = threading.Lock()
_started_error: str | None = None


def _ensure_started() -> None:
    global _watcher, _thread, _started_error
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        try:
            cfg_path = os.environ.get("RSS_WATCHER_CONFIG")
            if cfg_path and not os.path.exists(cfg_path):
                cfg_path = None  # fall back to environment-only configuration
            cfg = config_module.load(cfg_path)
            _watcher = Watcher(cfg)
            _thread = threading.Thread(target=_watcher.run_forever, daemon=True)
            _thread.start()
            _started_error = None
        except Exception as exc:  # surface config errors via the health endpoint
            _started_error = str(exc)


def application(environ, start_response):
    """WSGI entrypoint — returns a JSON health/status document."""
    _ensure_started()

    alive = _thread is not None and _thread.is_alive()
    healthy = alive and _started_error is None
    status = {
        "status": "ok" if healthy else "error",
        "running": alive,
        "feeds": len(_watcher.cfg.feeds) if _watcher else 0,
        "seen": _watcher.store.count() if _watcher else 0,
        "error": _started_error,
    }

    body = json.dumps(status).encode("utf-8")
    http_status = "200 OK" if healthy else "503 Service Unavailable"
    start_response(http_status, [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(body))),
    ])
    return [body]
