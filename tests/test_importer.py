from datetime import date
from pathlib import Path

from openloop.importer import import_csv


def test_import_csv(tmp_path: Path):
    p = tmp_path / "loops.csv"
    p.write_text("text,owner,due,priority\nSend deck,Alex,2026-08-28,p0\nReview DPA,Jordan,Friday,p1\n")
    result = import_csv(p, source_id="s", reference=date(2026, 8, 25))
    assert len(result.loops) == 2
    assert result.loops[0].owner == "Alex"
    assert result.loops[0].priority.value == "p0"
    assert result.loops[0].fingerprint
