from openloop.utc import now_iso


def test_now_iso_looks_like_timestamp():
    value = now_iso()
    assert "T" in value
    assert len(value) >= 19
