import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from shss.history import log_event, read_events


def test_log_event_creates_file_and_parent_dir(tmp_path, monkeypatch):
    history_path = tmp_path / "sub" / "history.jsonl"
    monkeypatch.setenv("SHSS_HISTORY_PATH", str(history_path))

    log_event("liste les pdf", "", "", "find . -iname '*.pdf'", "inline")

    assert history_path.is_file()


def test_read_events_round_trip(tmp_path, monkeypatch):
    history_path = tmp_path / "history.jsonl"
    monkeypatch.setenv("SHSS_HISTORY_PATH", str(history_path))

    log_event("un", "", "", "UN", "inline")
    log_event("deux", "", "", "DEUX", "script")

    events = read_events(limit=20)
    assert [e["request"] for e in events] == ["un", "deux"]
    assert [e["kind"] for e in events] == ["inline", "script"]
    assert events[1]["result"] == "DEUX"


def test_read_events_respects_limit(tmp_path, monkeypatch):
    history_path = tmp_path / "history.jsonl"
    monkeypatch.setenv("SHSS_HISTORY_PATH", str(history_path))

    for i in range(5):
        log_event(f"demande {i}", "", "", f"resultat {i}", "inline")

    events = read_events(limit=2)
    assert [e["request"] for e in events] == ["demande 3", "demande 4"]


def test_read_events_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SHSS_HISTORY_PATH", str(tmp_path / "does-not-exist.jsonl"))
    assert read_events() == []
