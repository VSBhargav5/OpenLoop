from __future__ import annotations

from typing import Any


def _line(L: dict) -> str:
    owner = (L.get("owner") or "unassigned").strip() or "unassigned"
    due = L.get("due_date") or L.get("due_text") or "no due"
    return f"{owner} — {L.get('text', '').strip()} ({due})"


def format_digest_markdown(digest: dict[str, Any]) -> str:
    days = digest.get("days", 7)
    lines = [
        f"# OpenLoop · still open · {digest.get('as_of')}",
        "",
        (
            f"Open **{digest.get('open', 0)}** · "
            f"Overdue **{len(digest.get('overdue') or [])}** · "
            f"Due in {days}d **{len(digest.get('due_soon') or [])}** · "
            f"Unassigned **{len(digest.get('unassigned') or [])}** · "
            f"No deadline **{len(digest.get('no_due') or [])}**"
        ),
        "",
        "## Overdue",
    ]
    overdue = digest.get("overdue") or []
    if overdue:
        lines.extend(f"- {_line(L)}" for L in overdue)
    else:
        lines.append("- None")

    lines += ["", f"## Due within {days} day(s)"]
    soon = digest.get("due_soon") or []
    if soon:
        lines.extend(f"- {_line(L)}" for L in soon)
    else:
        lines.append("- None")

    lines += ["", "## Unassigned"]
    un = digest.get("unassigned") or []
    if un:
        lines.extend(f"- {_line(L)}" for L in un)
    else:
        lines.append("- None")

    lines += ["", "## Open with no deadline"]
    nd = digest.get("no_due") or []
    if nd:
        lines.extend(f"- {_line(L)}" for L in nd[:20])
        if len(nd) > 20:
            lines.append(f"- …and {len(nd) - 20} more")
    else:
        lines.append("- None")

    by_owner = digest.get("by_owner") or {}
    lines += ["", "## Load by owner"]
    if by_owner:
        lines.extend(f"- {n}: {c}" for n, c in by_owner.items())
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def format_digest_slack(digest: dict[str, Any]) -> str:
    days = digest.get("days", 7)
    blocks = [
        f"*OpenLoop · still open · {digest.get('as_of')}*",
        (
            f"Open {digest.get('open', 0)} · "
            f"Overdue {len(digest.get('overdue') or [])} · "
            f"Due in {days}d {len(digest.get('due_soon') or [])} · "
            f"Unassigned {len(digest.get('unassigned') or [])}"
        ),
        "",
        "*Overdue*",
    ]
    overdue = digest.get("overdue") or []
    blocks.extend(f"• {_line(L)}" for L in overdue) if overdue else blocks.append("• None")
    blocks += ["", f"*Due within {days}d*"]
    soon = digest.get("due_soon") or []
    blocks.extend(f"• {_line(L)}" for L in soon) if soon else blocks.append("• None")
    return "\n".join(blocks).rstrip() + "\n"
