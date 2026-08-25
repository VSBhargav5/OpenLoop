from datetime import date
from pathlib import Path

from openloop.extractor import extract_rules
from openloop.store import LoopStore


SAMPLE = """
Sarah: Can you send the deck by Friday?
Alex: I'll update the pricing sheet tomorrow.
Priya will review the contract next week.
@jordan please ping legal about the DPA.
Random chatter about lunch plans.
"""


def test_rules_extract_commitments():
    result = extract_rules(SAMPLE, source_id="s1", reference_date=date(2026, 8, 25), default_owner="Bhargav")
    texts = " ".join(L.text.lower() for L in result.loops)
    assert "deck" in texts or "pricing" in texts or "contract" in texts
    assert len(result.loops) >= 2


def test_store_digest_overdue(tmp_path: Path):
    store = LoopStore(tmp_path / "t.db")
    result = extract_rules(
        "I'll ship the patch by 2026-08-01.\nCan you review docs by Friday?",
        source_id="s1",
        reference_date=date(2026, 8, 25),
        default_owner="me",
    )
    store.save_ingest("standup", result, path="x.txt", source_id="s1")
    d = store.digest(days=7, as_of=date(2026, 8, 25))
    assert d["open"] >= 1
    # at least one should be overdue if 2026-08-01 was parsed
    assert "overdue" in d


def test_done_closes_loop(tmp_path: Path):
    store = LoopStore(tmp_path / "t2.db")
    result = extract_rules(
        "I'll write the RFC tomorrow.",
        source_id="s2",
        reference_date=date(2026, 8, 25),
        default_owner="me",
    )
    assert result.loops
    store.save_ingest("notes", result, source_id="s2")
    lid = store.list_loops(status="open")[0]["id"]
    assert store.update(lid, status="done")
    assert store.get(lid)["status"] == "done"
