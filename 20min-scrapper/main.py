# -*- coding: utf-8 -*-
"""Deployment launcher for the Passenger/cPanel snapshot.

Formerly a third hardcoded copy of the watcher; now a thin launcher over the
single-source ``rss_watcher`` package (issue #6). The secret ntfy topic is no
longer embedded here (issue #3) — configure it via ``config.yaml`` or the
``NTFY_TOPIC`` environment variable.

For serving under Passenger, see ``passenger_wsgi.py`` (issue #1); this module
is the plain long-running-worker entrypoint.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
for path in (_REPO_ROOT, _HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

from rss_watcher.watcher import main

if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--config" not in argv and "-c" not in argv:
        default_cfg = os.environ.get("RSS_WATCHER_CONFIG", os.path.join(_HERE, "config.yaml"))
        argv = ["--config", default_cfg] + argv
    raise SystemExit(main(argv))
