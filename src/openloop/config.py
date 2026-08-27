"""Optional ~/.openloop/config.json — me, aliases, stale window."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_DIR = Path.home() / ".openloop"
DEFAULT_PATH = DEFAULT_DIR / "config.json"

DEFAULTS: dict[str, Any] = {
    "me": None,
    "aliases": {},
    "stale_days": 14,
    "min_confidence": 0.35,
    "digest_days": 7,
}


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    p = path or DEFAULT_PATH
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update({k: v for k, v in data.items() if k in DEFAULTS or k == "aliases"})
        except (OSError, json.JSONDecodeError):
            pass
    if not isinstance(cfg.get("aliases"), dict):
        cfg["aliases"] = {}
    return cfg


def save_config(cfg: dict[str, Any], path: Path | None = None) -> Path:
    p = path or DEFAULT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    merged = {**DEFAULTS, **cfg}
    p.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return p
