"""Bulk import loops from a simple CSV."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Optional
from uuid import uuid4

from .dates import normalize_deadline
from .fingerprint import fingerprint
from .models import ExtractResult, Loop, LoopPriority, LoopStatus
from .owners import normalize_owner


def import_csv(
    path: Path,
    *,
    source_id: str,
    reference: Optional[date] = None,
    default_owner: Optional[str] = None,
    aliases: Optional[dict] = None,
) -> ExtractResult:
    ref = reference or date.today()
    loops: list[Loop] = []
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
            text = row.get("text") or row.get("commitment") or row.get("loop") or ""
            if not text:
                continue
            owner = normalize_owner(
                row.get("owner") or None,
                aliases=aliases,
                default_self=default_owner,
            )
            due_text = row.get("due") or row.get("due_text") or row.get("due_date") or None
            due_date, due_text = normalize_deadline(due_text, reference=ref)
            if row.get("due_date") and not due_date:
                try:
                    due_date = date.fromisoformat(row["due_date"][:10])
                except ValueError:
                    pass
            pri_raw = (row.get("priority") or "p2").lower()
            try:
                priority = LoopPriority(pri_raw)
            except ValueError:
                priority = LoopPriority.P2
            status_raw = (row.get("status") or "open").lower()
            try:
                status = LoopStatus(status_raw)
            except ValueError:
                status = LoopStatus.OPEN
            loops.append(
                Loop(
                    id=str(uuid4()),
                    source_id=source_id,
                    text=text,
                    owner=owner,
                    due_date=due_date,
                    due_text=due_text,
                    status=status,
                    priority=priority,
                    tags=row.get("tags") or "",
                    notes=row.get("notes") or None,
                    fingerprint=fingerprint(text, owner),
                    confidence=1.0,
                )
            )
    return ExtractResult(loops=loops)
