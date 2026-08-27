from pathlib import Path

from openloop.config import load_config, save_config


def test_roundtrip(tmp_path: Path):
    p = tmp_path / "cfg.json"
    save_config({"me": "Bhargav", "stale_days": 10}, path=p)
    cfg = load_config(p)
    assert cfg["me"] == "Bhargav"
    assert cfg["stale_days"] == 10
    assert isinstance(cfg["aliases"], dict)


def test_missing_file_defaults(tmp_path: Path):
    cfg = load_config(tmp_path / "nope.json")
    assert cfg["stale_days"] == 14
