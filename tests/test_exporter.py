from pathlib import Path

from openloop.exporter import export_csv, export_json


def test_export_json_and_csv(tmp_path: Path):
    rows = [{"id": "1", "text": "Send deck", "owner": "Alex", "status": "open", "priority": "p0"}]
    js = export_json(rows, tmp_path / "out.json")
    assert "Send deck" in js.read_text()
    csv_path = export_csv(rows, tmp_path / "out.csv")
    body = csv_path.read_text()
    assert "text" in body and "Send deck" in body
