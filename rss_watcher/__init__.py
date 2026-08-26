"""RSS keyword watcher — a single, configurable source of truth.

Polls a list of RSS feeds, matches keywords against configurable entry fields,
de-duplicates across restarts, and delivers push notifications through one or
more pluggable backends (ntfy, e-mail, Telegram, Slack, ...).

See ``config.example.yaml`` for the full configuration reference.
"""

__version__ = "1.0.0"
