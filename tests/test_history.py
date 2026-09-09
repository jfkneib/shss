import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from shss.history import format_line, log_line, read_lines


def test_log_line_creates_file_and_parent_dir(tmp_path, monkeypatch):
    history_path = tmp_path / "sub" / "history.jsonl"
    monkeypatch.setenv("SHSS_HISTORY_PATH", str(history_path))

    log_line("#@ trie par taille @#")

    assert history_path.is_file()


def test_log_line_records_the_raw_text_unmodified(tmp_path, monkeypatch):
    history_path = tmp_path / "history.jsonl"
    monkeypatch.setenv("SHSS_HISTORY_PATH", str(history_path))

    raw = '#@pc-stats@ energie consomee par le pc @#'
    log_line(raw)

    event = read_lines(limit=1)[0]
    assert event["line"] == raw
    assert "timestamp" in event
    # rien d'autre : pas de demande depouillee, pas de profil separe --
    # tel quel, delimiteurs et prefixe de profil compris.
    assert set(event) == {"timestamp", "line"}


def test_read_lines_round_trip_and_order(tmp_path, monkeypatch):
    history_path = tmp_path / "history.jsonl"
    monkeypatch.setenv("SHSS_HISTORY_PATH", str(history_path))

    log_line("#@ un @#")
    log_line("#@ deux @#")

    events = read_lines(limit=20)
    assert [e["line"] for e in events] == ["#@ un @#", "#@ deux @#"]


def test_read_lines_respects_limit(tmp_path, monkeypatch):
    history_path = tmp_path / "history.jsonl"
    monkeypatch.setenv("SHSS_HISTORY_PATH", str(history_path))

    for i in range(5):
        log_line(f"#@ demande {i} @#")

    events = read_lines(limit=2)
    assert [e["line"] for e in events] == ["#@ demande 3 @#", "#@ demande 4 @#"]


def test_read_lines_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SHSS_HISTORY_PATH", str(tmp_path / "does-not-exist.jsonl"))
    assert read_lines() == []


def test_format_line_shows_timestamp_and_raw_text():
    text = format_line({"timestamp": "2026-09-06T10:00:00", "line": "#@pc-stats@ x @#"})
    assert "2026-09-06T10:00:00" in text
    assert "#@pc-stats@ x @#" in text
