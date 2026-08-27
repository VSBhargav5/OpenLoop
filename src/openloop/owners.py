"""Normalize owner names so Alex / @alex / alex.k map to one person."""

from __future__ import annotations

import re
from typing import Mapping, Optional

_SELF = {"i", "i'll", "ill", "me", "myself", "we"}


def normalize_owner(
    raw: Optional[str],
    *,
    aliases: Optional[Mapping[str, str]] = None,
    default_self: Optional[str] = None,
) -> Optional[str]:
    if raw is None:
        return None
    name = raw.strip().lstrip("@")
    if not name:
        return None
    key = re.sub(r"[._]+", " ", name).strip().lower()
    if key in _SELF:
        return default_self or "me"
    if aliases:
        lowered = {k.lower(): v for k, v in aliases.items()}
        if key in lowered:
            return lowered[key]
        compact = key.replace(" ", "")
        for alias, canonical in lowered.items():
            if alias.replace(" ", "") == compact:
                return canonical
    return " ".join(p.capitalize() for p in key.split())
