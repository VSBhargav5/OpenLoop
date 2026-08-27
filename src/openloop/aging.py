"""How 'stale' an open loop feels — days untouched + overdue weight."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional


def _parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", ""))
    except ValueError:
        return None


def age_days(row: dict, *, as_of: Optional[date] = None) -> int:
    today = as_of or date.today()
    updated = _parse_dt(row.get("updated_at"))
    created = _parse_dt(row.get("created_at"))
    stamp = (updated or created)
    if not stamp:
        return 0
    return max((today - stamp.date()).days, 0)


def is_stale(row: dict, *, days: int = 14, as_of: Optional[date] = None) -> bool:
    if row.get("status") not in {"open", "snoozed", "blocked"}:
        return False
    return age_days(row, as_of=as_of) >= days


def aging_score(row: dict, *, as_of: Optional[date] = None) -> int:
    """Higher = more urgent to nudge. 0–100."""
    today = as_of or date.today()
    score = min(age_days(row, as_of=today) * 3, 40)
    due = _parse_date(row.get("due_date"))
    if due:
        delta = (today - due).days
        if delta > 0:
            score += min(30 + delta * 2, 50)
        elif delta == 0:
            score += 20
        elif delta >= -2:
            score += 10
    if not row.get("owner"):
        score += 10
    if (row.get("priority") or "p2") == "p0":
        score += 15
    elif row.get("priority") == "p1":
        score += 8
    if row.get("status") == "blocked":
        score += 5
    return min(score, 100)
