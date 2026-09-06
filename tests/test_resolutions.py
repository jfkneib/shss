import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from shss.resolutions import format_event, log_event, log_execution, log_feedback, read_events


def test_log_event_creates_file_and_parent_dir(tmp_path, monkeypatch):
    resolutions_path = tmp_path / "sub" / "resolutions.jsonl"
    monkeypatch.setenv("SHSS_RESOLUTIONS_PATH", str(resolutions_path))

    log_event("liste les pdf", "", "", "find . -iname '*.pdf'", "inline")

    assert resolutions_path.is_file()


def test_read_events_round_trip(tmp_path, monkeypatch):
    resolutions_path = tmp_path / "resolutions.jsonl"
    monkeypatch.setenv("SHSS_RESOLUTIONS_PATH", str(resolutions_path))

    log_event("un", "", "", "UN", "inline")
    log_event("deux", "", "", "DEUX", "script")

    events = read_events(limit=20)
    assert [e["request"] for e in events] == ["un", "deux"]
    assert [e["kind"] for e in events] == ["inline", "script"]
    assert events[1]["result"] == "DEUX"


def test_read_events_respects_limit(tmp_path, monkeypatch):
    resolutions_path = tmp_path / "resolutions.jsonl"
    monkeypatch.setenv("SHSS_RESOLUTIONS_PATH", str(resolutions_path))

    for i in range(5):
        log_event(f"demande {i}", "", "", f"resultat {i}", "inline")

    events = read_events(limit=2)
    assert [e["request"] for e in events] == ["demande 3", "demande 4"]


def test_read_events_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SHSS_RESOLUTIONS_PATH", str(tmp_path / "does-not-exist.jsonl"))
    assert read_events() == []


def test_log_event_case_kind_records_score_case_id_and_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("SHSS_RESOLUTIONS_PATH", str(tmp_path / "resolutions.jsonl"))

    log_event(
        "energie consommee par le pc", "", "", "/tmp/energie.sh", "case",
        score=0.951, case_id="energie", profile="pc-stats",
    )

    event = read_events(limit=1)[0]
    assert event["score"] == 0.951
    assert event["case_id"] == "energie"
    assert event["profile"] == "pc-stats"


def test_log_event_case_kind_records_default_profile_as_none(tmp_path, monkeypatch):
    monkeypatch.setenv("SHSS_RESOLUTIONS_PATH", str(tmp_path / "resolutions.jsonl"))

    log_event("x", "", "", "y", "case", score=0.9, case_id="fix-select", profile=None)

    event = read_events(limit=1)[0]
    assert "profile" in event  # ecrit explicitement (null), pas omis
    assert event["profile"] is None


def test_log_event_non_case_kind_omits_score_and_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("SHSS_RESOLUTIONS_PATH", str(tmp_path / "resolutions.jsonl"))

    log_event("trie par taille", "ls ", "", "-S", "inline")

    event = read_events(limit=1)[0]
    assert "score" not in event
    assert "case_id" not in event
    assert "profile" not in event


def test_log_execution_records_line_expanded_code_and_output(tmp_path, monkeypatch):
    monkeypatch.setenv("SHSS_RESOLUTIONS_PATH", str(tmp_path / "resolutions.jsonl"))

    log_execution("ls #@ trie par taille @#", "ls -S", "a.txt\nb.txt\n", 0)

    event = read_events(limit=1)[0]
    assert event["kind"] == "execution"
    assert event["line"] == "ls #@ trie par taille @#"
    assert event["expanded"] == "ls -S"
    assert event["exit_code"] == 0
    assert event["output"] == "a.txt\nb.txt\n"
    assert "output_truncated" not in event


def test_log_execution_truncates_long_output(tmp_path, monkeypatch):
    monkeypatch.setenv("SHSS_RESOLUTIONS_PATH", str(tmp_path / "resolutions.jsonl"))
    monkeypatch.setenv("SHSS_RESOLUTIONS_OUTPUT_MAX_CHARS", "10")

    log_execution("cmd", "cmd", "0123456789abcdef", 0)

    event = read_events(limit=1)[0]
    assert event["output"] == "0123456789"
    assert event["output_truncated"] is True


def test_log_feedback_attaches_to_last_resolution_and_returns_it(tmp_path, monkeypatch):
    monkeypatch.setenv("SHSS_RESOLUTIONS_PATH", str(tmp_path / "resolutions.jsonl"))

    log_event("energie consommee par le pc", "", "", "/tmp/x.sh", "case", score=0.9, case_id="energie")
    about = log_feedback("mauvais", "n'a pas mesure le GPU")

    assert about["request"] == "energie consommee par le pc"
    events = read_events(limit=20)
    feedback_entry = events[-1]
    assert feedback_entry["kind"] == "feedback"
    assert feedback_entry["feedback"] == "mauvais"
    assert feedback_entry["comment"] == "n'a pas mesure le GPU"
    assert feedback_entry["about"]["request"] == "energie consommee par le pc"


def test_log_feedback_skips_execution_entries_to_find_the_real_request(tmp_path, monkeypatch):
    monkeypatch.setenv("SHSS_RESOLUTIONS_PATH", str(tmp_path / "resolutions.jsonl"))

    log_event("trie par taille", "ls ", "", "-S", "inline")
    log_execution("ls #@ trie par taille @#", "ls -S", "a.txt\n", 0)

    about = log_feedback("bon")

    assert about["request"] == "trie par taille"


def test_log_feedback_skips_a_previous_feedback_builtin_itself(tmp_path, monkeypatch):
    monkeypatch.setenv("SHSS_RESOLUTIONS_PATH", str(tmp_path / "resolutions.jsonl"))

    log_event("trie par taille", "ls ", "", "-S", "inline")
    log_event("feedback bon", "", "", "shss: avis enregistre", "builtin")

    about = log_feedback("mauvais")

    assert about["request"] == "trie par taille"


def test_log_feedback_returns_none_on_empty_history(tmp_path, monkeypatch):
    monkeypatch.setenv("SHSS_RESOLUTIONS_PATH", str(tmp_path / "resolutions.jsonl"))

    assert log_feedback("bon") is None
    assert read_events() == []  # rien ecrit -- pas d'entree orpheline


def test_format_event_handles_every_kind_without_crashing(tmp_path, monkeypatch):
    monkeypatch.setenv("SHSS_RESOLUTIONS_PATH", str(tmp_path / "resolutions.jsonl"))

    log_event("energie consommee par le pc", "", "", "/tmp/x.sh", "case", score=0.9, case_id="energie", profile="pc-stats")
    log_event("trie par taille", "ls ", "", "-S", "inline")
    log_execution("ls #@ trie par taille @#", "ls -S", "a.txt\n", 1)
    log_feedback("mauvais", "trie dans le mauvais sens")

    for event in read_events(limit=20):
        text = format_event(event)
        assert isinstance(text, str) and text
