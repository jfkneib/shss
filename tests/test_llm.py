import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from miniai.llm import discover_gguf_path


def test_discover_gguf_path_env_override(monkeypatch):
    monkeypatch.setenv("MINIAI_MODEL_PATH", "/some/where/model.gguf")
    assert discover_gguf_path() == "/some/where/model.gguf"
