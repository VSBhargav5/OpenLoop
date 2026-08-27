"""Stable fingerprint so similar commitments don't duplicate."""

from __future__ import annotations

import hashlib
import re
from typing import Optional

_STOP = {
    "the", "a", "an", "to", "for", "of", "and", "please", "pls", "just", "can", "you", "will", "i",
}


def normalize_text(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    kept = [w for w in words if w not in _STOP]
    return " ".join(kept) if kept else " ".join(words)


def fingerprint(text: str, owner: Optional[str] = None) -> str:
    body = normalize_text(text)
    who = (owner or "").strip().lower()
    raw = f"{who}|{body}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def similar(a: str, b: str) -> bool:
    return normalize_text(a) == normalize_text(b)
