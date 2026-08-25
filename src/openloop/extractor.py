"""Extract open commitments from messy text.

Rule-based path always works offline. Optional LLM path when OPENAI_API_KEY is set.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Optional
from uuid import uuid4

from .dates import normalize_deadline
from .models import ExtractResult, Loop

# Commitment-ish patterns (intentionally imperfect — high recall, filter later)
_LINE_PATTERNS = [
    # First person promises
    re.compile(
        r"(?P<evidence>(?:I['']ll|I will|I can|I should|Let me|I'?m going to)\s+(?P<body>[^.!?\n]{5,120}))",
        re.I,
    ),
    # Asks / assignments
    re.compile(
        r"(?P<evidence>(?:Can you|Could you|Please|Pls)\s+(?P<body>[^.!?\n]{5,120}))",
        re.I,
    ),
    # Named person + action verb
    re.compile(
        r"(?P<evidence>(?P<owner>[A-Z][a-z]+)\s+(?:will|should|to)\s+(?P<body>[^.!?\n]{5,100}))",
    ),
    # "@name …" style
    re.compile(
        r"(?P<evidence>@(?P<owner>[\w.]+)\s+(?P<body>[^.!?\n]{5,100}))",
        re.I,
    ),
]

_DUE_INLINE = re.compile(
    r"\b(by|before|due|until)\s+(?P<due>[^.!?\n,]{2,40})",
    re.I,
)

_SELF_OWNERS = {"i", "i'll", "ill", "me", "myself"}


def _clean_body(body: str) -> str:
    body = re.sub(r"\s+", " ", body).strip(" -—\t")
    body = re.sub(r"^(to|please|pls)\s+", "", body, flags=re.I)
    return body[:200]


def _guess_due(text: str, reference: date) -> tuple[Optional[date], Optional[str]]:
    m = _DUE_INLINE.search(text)
    if not m:
        return None, None
    return normalize_deadline(m.group("due"), reference=reference)


def extract_rules(
    text: str,
    *,
    source_id: str,
    reference_date: Optional[date] = None,
    default_owner: Optional[str] = None,
) -> ExtractResult:
    """Offline high-recall extractor. Good enough for v0.1 + tests."""
    ref = reference_date or date.today()
    loops: list[Loop] = []
    seen: set[str] = set()

    for line in text.splitlines():
        line = line.strip()
        if len(line) < 8:
            continue
        for pat in _LINE_PATTERNS:
            m = pat.search(line)
            if not m:
                continue
            gd = m.groupdict()
            evidence = (gd.get("evidence") or line).strip()
            body = _clean_body(gd.get("body") or evidence)
            if len(body) < 5:
                continue
            key = body.lower()
            if key in seen:
                continue
            seen.add(key)

            owner = gd.get("owner")
            if owner and owner.lower().lstrip("@") in _SELF_OWNERS:
                owner = default_owner or "me"
            elif owner:
                owner = owner.lstrip("@").strip().title()
            elif re.match(r"^(I['']ll|I will|I can|Let me|I'?m going to)", line, re.I):
                owner = default_owner or "me"
            else:
                owner = None

            due_date, due_text = _guess_due(line, ref)
            loops.append(
                Loop(
                    source_id=source_id,
                    text=body[0].upper() + body[1:] if body else body,
                    owner=owner,
                    due_date=due_date,
                    due_text=due_text,
                    evidence=evidence[:240],
                    confidence=0.55 if owner else 0.4,
                )
            )
            break  # one match per line

    return ExtractResult(loops=loops)


def extract_llm(
    text: str,
    *,
    source_id: str,
    reference_date: Optional[date] = None,
    model: str = "gpt-4o-mini",
    base_url: Optional[str] = None,
    default_owner: Optional[str] = None,
) -> ExtractResult:
    """LLM extraction when an API key is available."""
    from openai import OpenAI

    ref = reference_date or date.today()
    client = OpenAI(base_url=base_url) if base_url else OpenAI()
    system = (
        "You extract OPEN COMMITMENTS from informal text (chat, notes, email).\n"
        "A commitment is something someone said they will do, or was asked to do, "
        "that is not clearly already done.\n"
        "Return JSON only: {\"loops\": [{\"text\": str, \"owner\": str|null, "
        "\"due_text\": str|null, \"evidence\": str, \"confidence\": float}]}\n"
        "Rules: text is a clear action; owner is a person name or null; "
        "due_text is the deadline phrase if any; evidence is a short quote; "
        "skip pure discussion with no obligation."
    )
    user = f"Reference date: {ref.isoformat()}\n\nTEXT:\n{text[:12000]}"
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    raw = resp.choices[0].message.content or "{}"
    data = json.loads(raw)
    loops: list[Loop] = []
    for item in data.get("loops") or []:
        due_text = item.get("due_text")
        due_date, due_text = normalize_deadline(due_text, reference=ref)
        owner = item.get("owner")
        if owner and str(owner).lower() in _SELF_OWNERS:
            owner = default_owner or "me"
        loops.append(
            Loop(
                id=str(uuid4()),
                source_id=source_id,
                text=str(item.get("text") or "").strip(),
                owner=owner,
                due_date=due_date,
                due_text=due_text,
                evidence=(item.get("evidence") or None),
                confidence=float(item.get("confidence") or 0.7),
            )
        )
    return ExtractResult(loops=[L for L in loops if L.text])


def extract(
    text: str,
    *,
    source_id: str,
    reference_date: Optional[date] = None,
    model: str = "gpt-4o-mini",
    base_url: Optional[str] = None,
    default_owner: Optional[str] = None,
    force_rules: bool = False,
) -> ExtractResult:
    """Prefer LLM when key present; else rules. force_rules for tests."""
    if force_rules or not os.getenv("OPENAI_API_KEY"):
        return extract_rules(
            text,
            source_id=source_id,
            reference_date=reference_date,
            default_owner=default_owner,
        )
    try:
        return extract_llm(
            text,
            source_id=source_id,
            reference_date=reference_date,
            model=model,
            base_url=base_url,
            default_owner=default_owner,
        )
    except Exception:
        return extract_rules(
            text,
            source_id=source_id,
            reference_date=reference_date,
            default_owner=default_owner,
        )
