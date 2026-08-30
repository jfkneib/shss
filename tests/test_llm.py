import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import miniai.llm as llm_module
from miniai.llm import ResolutionCancelled, discover_gguf_path


def test_discover_gguf_path_env_override(monkeypatch):
    monkeypatch.setenv("MINIAI_MODEL_PATH", "/some/where/model.gguf")
    assert discover_gguf_path() == "/some/where/model.gguf"


def test_discover_gguf_path_falls_back_to_system_model_path(monkeypatch, tmp_path):
    monkeypatch.delenv("MINIAI_MODEL_PATH", raising=False)
    monkeypatch.setattr(llm_module, "_KNOWN_OLLAMA_DIRS", [])
    fake_model = tmp_path / "model.gguf"
    fake_model.write_bytes(b"")
    monkeypatch.setattr(llm_module, "SYSTEM_MODEL_PATH", str(fake_model))
    assert discover_gguf_path() == str(fake_model)


class _FakeLlama:
    def __init__(self, text):
        self.text = text
        self.last_prompt = None

    def __call__(self, prompt, **kwargs):
        self.last_prompt = prompt
        return {"choices": [{"text": self.text}]}


def _fake_miniai(monkeypatch, tmp_path, fake_text):
    monkeypatch.setenv("MINIAI_HISTORY_PATH", str(tmp_path / "history.jsonl"))
    monkeypatch.setattr(llm_module, "SCRIPT_DIR", tmp_path / "scripts")

    instance = llm_module.MiniLLM.__new__(llm_module.MiniLLM)
    instance._llm = _FakeLlama(fake_text)
    instance._ensure_loaded = lambda: None
    return instance


def test_generate_bash_inline_takes_only_first_line(monkeypatch, tmp_path):
    llm = _fake_miniai(monkeypatch, tmp_path, "-la\n\nLigne: du bruit en trop")
    assert llm.generate_bash("affiche aussi les fichiers caches", "ls ", "") == "-la"


def test_generate_bash_script_mode_writes_file_and_returns_its_path(monkeypatch, tmp_path):
    script_text = (
        "#!/usr/bin/env python3\n"
        'import json\nwith open("a.txt") as f:\n    pass\n'
    )
    llm = _fake_miniai(monkeypatch, tmp_path, script_text)

    result = llm.generate_bash("formate a.txt en json")

    result_path = Path(result)
    assert result_path.is_file()
    assert result_path.suffix == ".py"
    assert result_path.read_text() == script_text.strip()
    assert oct(result_path.stat().st_mode)[-3:] == "700"


def test_generate_bash_logs_to_history(monkeypatch, tmp_path):
    from miniai.history import read_events

    llm = _fake_miniai(monkeypatch, tmp_path, "-S")
    llm.generate_bash("trie par taille", "ls ", "")

    events = read_events()
    assert len(events) == 1
    assert events[0]["request"] == "trie par taille"
    assert events[0]["result"] == "-S"
    assert events[0]["kind"] == "inline"


def test_generate_bash_confirm_sees_the_final_display_text(monkeypatch, tmp_path):
    llm = _fake_miniai(monkeypatch, tmp_path, "-la\n\nLigne: du bruit en trop")
    seen = {}

    def confirm(text):
        seen["text"] = text
        return True

    result = llm.generate_bash("affiche aussi les fichiers caches", confirm=confirm)
    assert seen["text"] == "-la"
    assert result == "-la"


def test_generate_bash_confirm_false_cancels_without_side_effects(monkeypatch, tmp_path):
    from miniai.history import read_events

    llm = _fake_miniai(monkeypatch, tmp_path, "#!/usr/bin/env python3\nprint('hi')")

    try:
        llm.generate_bash("fait un truc", confirm=lambda text: False)
        assert False, "devrait lever ResolutionCancelled"
    except ResolutionCancelled:
        pass

    assert read_events() == []
    assert not (tmp_path / "scripts").exists()
