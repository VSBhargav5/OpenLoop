from datetime import date, datetime

from openloop.aging import age_days, aging_score, is_stale


def test_stale_open_item():
    row = {
        "status": "open",
        "updated_at": datetime(2026, 8, 1).isoformat(),
        "created_at": datetime(2026, 8, 1).isoformat(),
        "due_date": None,
        "owner": "Alex",
        "priority": "p2",
    }
    assert is_stale(row, days=14, as_of=date(2026, 8, 25))
    assert age_days(row, as_of=date(2026, 8, 25)) == 24
    assert aging_score(row, as_of=date(2026, 8, 25)) >= 40


def test_fresh_not_stale():
    row = {
        "status": "open",
        "updated_at": datetime(2026, 8, 24).isoformat(),
        "created_at": datetime(2026, 8, 24).isoformat(),
        "priority": "p2",
    }
    assert not is_stale(row, days=14, as_of=date(2026, 8, 25))
