"""UTC timestamps without depending on datetime.utcnow."""

from __future__ import annotations

from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
