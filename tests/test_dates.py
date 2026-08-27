from datetime import date

from openloop.dates import normalize_deadline


def test_tomorrow_and_eod():
    ref = date(2026, 8, 25)
    d, _ = normalize_deadline("tomorrow", reference=ref)
    assert d == date(2026, 8, 26)
    d, _ = normalize_deadline("EOD", reference=ref)
    assert d == ref


def test_next_week_and_asap():
    ref = date(2026, 8, 25)
    d, _ = normalize_deadline("next week", reference=ref)
    assert d == date(2026, 9, 1)
    d, _ = normalize_deadline("asap", reference=ref)
    assert d == date(2026, 8, 27)


def test_in_n_days():
    ref = date(2026, 8, 25)
    d, _ = normalize_deadline("in 3 days", reference=ref)
    assert d == date(2026, 8, 28)
