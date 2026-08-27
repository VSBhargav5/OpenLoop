from openloop.digest import format_digest_json, format_digest_markdown, format_digest_slack
from openloop.html_digest import format_digest_html


def _sample():
    return {
        "as_of": "2026-08-25",
        "days": 7,
        "open": 2,
        "blocked": 0,
        "overdue": [{"owner": "Alex", "text": "Ship patch", "due_date": "2026-08-01", "priority": "p0"}],
        "due_soon": [],
        "unassigned": [],
        "no_due": [],
        "stale": [],
        "nudges": [{"owner": "Alex", "text": "Ship patch", "due_date": "2026-08-01", "priority": "p0", "aging_score": 80}],
        "by_owner": {"Alex": 1},
    }


def test_markdown_has_sections():
    md = format_digest_markdown(_sample())
    assert "Overdue" in md and "Nudge first" in md and "Ship patch" in md


def test_html_and_json():
    html = format_digest_html(_sample())
    assert "<table>" in html and "Ship patch" in html
    assert '"as_of"' in format_digest_json(_sample())
    assert "OpenLoop" in format_digest_slack(_sample())
