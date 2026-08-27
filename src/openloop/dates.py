"""Normalize relative deadline phrases into concrete dates."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional, Tuple

from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta, FR, MO, SA, SU, TH, TU, WE

WEEKDAY_MAP = {
    "monday": MO, "mon": MO, "tuesday": TU, "tue": TU,
    "wednesday": WE, "wed": WE, "thursday": TH, "thu": TH,
    "friday": FR, "fri": FR, "saturday": SA, "sat": SA,
    "sunday": SU, "sun": SU,
}


def normalize_deadline(
    due_text: Optional[str],
    reference: Optional[date] = None,
) -> Tuple[Optional[date], Optional[str]]:
    if not due_text or not due_text.strip():
        return None, None

    text = due_text.strip().lower()
    for prefix in ("by ", "before ", "due ", "deadline ", "until ", "on "):
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()

    text = text.rstrip(".,;")
    ref = reference or date.today()
    original = due_text.strip()

    if text in {"today", "eod", "end of day", "tonight"}:
        return ref, original
    if text in {"tomorrow", "tmr", "tmrw", "eod tomorrow"}:
        return ref + timedelta(days=1), original
    if text in {"yesterday"}:
        return ref - timedelta(days=1), original
    if "next week" in text:
        return ref + timedelta(days=7), original
    if "next month" in text:
        return ref + relativedelta(months=1), original
    if "end of week" in text or text == "eow":
        days_ahead = 4 - ref.weekday()
        if days_ahead < 0:
            days_ahead += 7
        return ref + timedelta(days=days_ahead), original
    if "end of month" in text or text == "eom":
        next_month = ref.replace(day=1) + relativedelta(months=1)
        return next_month - timedelta(days=1), original
    if text in {"asap", "soon"}:
        return ref + timedelta(days=2), original

    for name, weekday in WEEKDAY_MAP.items():
        if f"next {name}" in text:
            return ref + relativedelta(weekday=weekday(+1)), original
        if f"this {name}" in text or text == name:
            return ref + relativedelta(weekday=weekday(+1)), original

    if text.startswith("in "):
        parts = text.split()
        if len(parts) >= 3 and parts[1].isdigit():
            n = int(parts[1])
            unit = parts[2]
            if unit.startswith("day"):
                return ref + timedelta(days=n), original
            if unit.startswith("week"):
                return ref + timedelta(weeks=n), original
            if unit.startswith("month"):
                return ref + relativedelta(months=n), original

    try:
        parsed = date_parser.parse(
            due_text, default=datetime.combine(ref, datetime.min.time())
        )
        return parsed.date(), original
    except (ValueError, OverflowError, TypeError):
        return None, original
