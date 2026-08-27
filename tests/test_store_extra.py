from datetime import date
from pathlib import Path

from openloop.extractor import extract_rules
from openloop.store import LoopStore


def test_search_priority_and_history(tmp_path: Path):
    store = LoopStore(tmp_path / "e.db")
    result = extract_rules(
        "I'll write the RFC tomorrow.",
        source_id="s",
        reference_date=date(2026, 8, 25),
        default_owner="Bhargav",
    )
    store.save_ingest("notes", result, source_id="s")
    rows = store.search("RFC")
    assert rows
    lid = rows[0]["id"]
    assert store.update(lid, priority="p0")
    assert store.get(lid)["priority"] == "p0"
    assert store.update(lid, status="done")
    hist = store.history(lid)
    assert any(h["kind"] == "status" for h in hist)


def test_dedupe(tmp_path: Path):
    store = LoopStore(tmp_path / "d.db")
    r1 = extract_rules("I'll write the RFC tomorrow.", source_id="a", reference_date=date(2026, 8, 25), default_owner="me")
    store.save_ingest("n1", r1, source_id="a")
    r2 = extract_rules("I'll write the RFC tomorrow.", source_id="b", reference_date=date(2026, 8, 25), default_owner="me")
    _sid, n = store.save_ingest("n2", r2, source_id="b")
    assert n == 0
    assert r2.skipped_dupes >= 1
