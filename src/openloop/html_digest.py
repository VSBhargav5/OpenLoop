"""Self-contained HTML still-open digest."""

from __future__ import annotations

from html import escape
from typing import Any


def _row(L: dict) -> str:
    owner = escape((L.get("owner") or "unassigned").strip() or "unassigned")
    text = escape(L.get("text") or "")
    due = escape(str(L.get("due_date") or L.get("due_text") or "no due"))
    pri = escape(str(L.get("priority") or "p2"))
    return (
        f"<tr><td>{owner}</td><td>{text}</td><td>{due}</td>"
        f"<td class='pri {pri}'>{pri}</td></tr>"
    )


def _table(title: str, rows: list[dict]) -> str:
    body = "".join(_row(L) for L in rows) or "<tr><td colspan='4'>None</td></tr>"
    return (
        f"<h2>{escape(title)}</h2>"
        "<table><thead><tr><th>Owner</th><th>Commitment</th>"
        "<th>Due</th><th>P</th></tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def format_digest_html(digest: dict[str, Any]) -> str:
    days = digest.get("days", 7)
    as_of = escape(str(digest.get("as_of") or ""))
    load = digest.get("by_owner") or {}
    load_html = "".join(
        f"<li>{escape(str(n))}: {c}</li>" for n, c in load.items()
    ) or "<li>None</li>"
    return (
        "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">\n"
        f"<title>OpenLoop digest {as_of}</title>\n"
        "<style>body{font:15px/1.45 system-ui,sans-serif;background:#0f1419;color:#e7ecf3;margin:0;padding:24px}"
        "h1{font-size:22px;margin:0 0 8px}.kpi{color:#9aa7b8;margin-bottom:24px}"
        "h2{font-size:15px;color:#7dd3fc;margin:28px 0 8px}"
        "table{border-collapse:collapse;width:100%}"
        "th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #243041}"
        "th{color:#9aa7b8;font-weight:600}.pri.p0{color:#fb7185}.pri.p1{color:#fbbf24}.pri.p2{color:#94a3b8}"
        "</style></head><body>\n"
        f"<h1>OpenLoop · still open · {as_of}</h1>\n"
        f"<p class=\"kpi\">Open <b>{digest.get('open', 0)}</b> · "
        f"Overdue <b>{len(digest.get('overdue') or [])}</b> · "
        f"Due in {days}d <b>{len(digest.get('due_soon') or [])}</b> · "
        f"Unassigned <b>{len(digest.get('unassigned') or [])}</b> · "
        f"Stale <b>{len(digest.get('stale') or [])}</b></p>\n"
        + _table("Overdue", digest.get("overdue") or [])
        + _table(f"Due within {days} day(s)", digest.get("due_soon") or [])
        + _table("Unassigned", digest.get("unassigned") or [])
        + _table("Stale", digest.get("stale") or [])
        + f"<h2>Load by owner</h2><ul>{load_html}</ul>\n</body></html>\n"
    )
