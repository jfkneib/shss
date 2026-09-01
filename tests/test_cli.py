import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import shss.llm as llm_module
from shss.cli import build_parser, print_models


def test_parser_dash_c():
    args = build_parser().parse_args(["-c", "ls -la"])
    assert args.command == "ls -la"


def test_parser_no_args_means_repl():
    args = build_parser().parse_args([])
    assert args.command is None


def test_print_models_includes_downloaded_curated_without_ollama(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(llm_module, "_KNOWN_OLLAMA_DIRS", [])
    monkeypatch.setattr(llm_module, "SYSTEM_MODELS_DIR", tmp_path / "system")
    monkeypatch.setattr(llm_module, "MODELS_DIR", tmp_path / "user")
    (tmp_path / "user").mkdir()
    (tmp_path / "user" / f"{llm_module.CURATED_MODEL_FAMILY}-0.5b.gguf").write_bytes(b"")

    print_models()
    out = capsys.readouterr().out.splitlines()

    assert f"{llm_module.CURATED_MODEL_FAMILY}:0.5b" in out
    # un modèle curaté non téléchargé n'est pas listé (ici 7b)
    assert f"{llm_module.CURATED_MODEL_FAMILY}:7b" not in out
