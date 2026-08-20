"""utils/formatting.py — small display-formatting helpers, no external deps."""

from __future__ import annotations

from datetime import datetime


def friendly_date(dt: datetime) -> str:
    return dt.strftime("%d %B %Y, %I:%M %p")
