# -*- coding: utf-8 -*-
"""Passenger WSGI entrypoint.

The previous version used the removed ``imp`` module and pointed ``application``
at ``wsgi.main.py`` — which is not a WSGI callable and raised ``AttributeError``
at startup (issue #1). ``main.py`` is an infinite polling loop, so it can never
serve HTTP requests directly.

Instead we expose the real WSGI health app from ``rss_watcher.wsgi``, which runs
the watcher in a background thread and answers a JSON status endpoint.
"""

import os
import sys

# Make the repository root (which contains the ``rss_watcher`` package) importable.
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
for path in (_REPO_ROOT, _HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

# Default the watcher to this deployment's config if the caller didn't set one.
os.environ.setdefault("RSS_WATCHER_CONFIG", os.path.join(_HERE, "config.yaml"))

from rss_watcher.wsgi import application  # noqa: E402  (path setup must run first)

__all__ = ["application"]
