import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import miniai.llm as llm_module
from miniai.commands import try_builtin


class _FakeMiniLLM:
    def __init__(self, model_path="/fake/model.gguf"):
        self.model_path = model_path
        self.switched_to = None

    def switch_model(self, model=None, tag=None, path=None):
        new_path = path or f"/fake/{model or 'qwen2.5-coder'}-{tag}.gguf"
        self.switched_to = (model, tag)
        self.model_path = new_path
        return new_path


def _fake_manifests(monkeypatch, tmp_path, entries):
    """entries: list of (name, tag). Creates a fake Ollama manifest tree
    under tmp_path and points _KNOWN_OLLAMA_DIRS at it."""
    library = tmp_path / "manifests" / "registry.ollama.ai" / "library"
    for name, tag in entries:
        d = library / name
        d.mkdir(parents=True, exist_ok=True)
        (d / tag).write_text("{}")
    monkeypatch.setattr(llm_module, "_KNOWN_OLLAMA_DIRS", [str(tmp_path)])


def test_try_builtin_returns_none_for_normal_request():
    assert try_builtin("trie par taille", _FakeMiniLLM()) is None


def test_models_lists_local_models(monkeypatch, tmp_path):
    _fake_manifests(monkeypatch, tmp_path, [("qwen2.5-coder", "1.5b-base"), ("qwen2.5-coder", "3b")])
    out = try_builtin("models", _FakeMiniLLM())
    assert "qwen2.5-coder:1.5b-base" in out
    assert "qwen2.5-coder:3b" in out


def test_models_marks_the_active_one(monkeypatch, tmp_path):
    _fake_manifests(monkeypatch, tmp_path, [("qwen2.5-coder", "1.5b-base"), ("qwen2.5-coder", "3b")])
    active_blob = str(tmp_path / "blobs" / "sha256-doesnotmatter")

    def fake_read_manifest_blob(models_dir, model, tag):
        if (model, tag) == ("qwen2.5-coder", "3b"):
            return active_blob
        return None

    monkeypatch.setattr(llm_module, "_read_manifest_blob", fake_read_manifest_blob)

    out = try_builtin("models", _FakeMiniLLM(model_path=active_blob))
    lines = {line.strip() for line in out.splitlines()}
    assert "- qwen2.5-coder:3b (actif)" in lines
    assert "- qwen2.5-coder:1.5b-base" in lines


def test_model_command_switches_and_reports_it():
    mini = _FakeMiniLLM()
    out = try_builtin("model 3b", mini)
    assert mini.switched_to == (None, "3b")
    assert "3b" in out


def test_model_command_accepts_name_colon_tag():
    mini = _FakeMiniLLM()
    try_builtin("model deepseek-coder:1.3b", mini)
    assert mini.switched_to == ("deepseek-coder", "1.3b")


def test_model_command_reports_missing_model_without_raising():
    class _FailingMiniLLM(_FakeMiniLLM):
        def switch_model(self, model=None, tag=None, path=None):
            raise FileNotFoundError("GGUF introuvable pour x:y")

    out = try_builtin("model does-not-exist", _FailingMiniLLM())
    assert "introuvable" in out


def test_history_command(monkeypatch, tmp_path):
    from miniai.history import log_event

    monkeypatch.setenv("MINIAI_HISTORY_PATH", str(tmp_path / "history.jsonl"))
    log_event("trie par taille", "ls ", "", "-S", "inline")

    out = try_builtin("history", _FakeMiniLLM())
    assert "trie par taille" in out
    assert "-S" in out


def test_history_command_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("MINIAI_HISTORY_PATH", str(tmp_path / "does-not-exist.jsonl"))
    out = try_builtin("history", _FakeMiniLLM())
    assert "vide" in out.lower()


def test_help_command():
    out = try_builtin("help", _FakeMiniLLM())
    assert "models" in out
    assert "model <tag>" in out
