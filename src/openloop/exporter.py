"""JSON / CSV export of loops."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def export_json(rows: list[dict[str, Any]], path: Path) -> Path:
    path.write_text(json.dumps(rows, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def export_csv(rows: list[dict[str, Any]], path: Path) -> Path:
    fields = [
        "id", "text", "owner", "due_date", "due_text", "status",
        "priority", "tags", "notes", "source_title", "confidence",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) if row.get(k) is not None else "" for k in fields})
    return path
