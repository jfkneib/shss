import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import miniai.llm as llm_module
from miniai.llm import discover_gguf_path


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
