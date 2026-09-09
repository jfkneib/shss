import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import shss.cli as cli_module
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


class _FakeShell:
    """Remplace PersistentShell (un vrai sous-processus bash) -- pas
    besoin d'un vrai shell pour verifier CE que run_once()/repl() font
    de la sortie/du code de retour, juste que le bon appel est fait."""

    def __init__(self, output="", code=0):
        self.output = output
        self.code = code
        self.ran = []

    def cwd(self):
        return "/fake"

    def run(self, line):
        self.ran.append(line)
        return self.output, self.code

    def close(self):
        pass


class _FakeLLMForCli:
    """Mimique MiniLLM.generate_bash (voir test_inline.py) -- toujours
    `result` tel quel, confirm() reçoit `result` aussi (pas teste ici)."""

    def __init__(self, result):
        self.result = result

    def generate_bash(self, request, prefix="", suffix="", confirm=None):
        if confirm is not None:
            confirm(self.result)
        return self.result


def test_run_once_logs_execution_when_a_tag_was_resolved(monkeypatch, tmp_path):
    from shss.resolutions import read_events

    monkeypatch.setenv("SHSS_RESOLUTIONS_PATH", str(tmp_path / "resolutions.jsonl"))
    fake_shell = _FakeShell(output="a.txt\nb.txt\n", code=0)
    monkeypatch.setattr(cli_module, "PersistentShell", lambda: fake_shell)

    code = cli_module.run_once(_FakeLLMForCli("-S"), "ls #@ trie par taille @#")

    assert code == 0
    assert fake_shell.ran == ["ls -S"]
    events = read_events(limit=1)
    assert events[0]["kind"] == "execution"
    assert events[0]["line"] == "ls #@ trie par taille @#"
    assert events[0]["expanded"] == "ls -S"
    assert events[0]["exit_code"] == 0
    assert events[0]["output"] == "a.txt\nb.txt\n"


def test_run_once_does_not_log_execution_for_a_plain_bash_line(monkeypatch, tmp_path):
    from shss.resolutions import read_events

    monkeypatch.setenv("SHSS_RESOLUTIONS_PATH", str(tmp_path / "resolutions.jsonl"))
    fake_shell = _FakeShell(output="", code=0)
    monkeypatch.setattr(cli_module, "PersistentShell", lambda: fake_shell)

    cli_module.run_once(_FakeLLMForCli("unused"), "ls -la")

    assert read_events() == []


def test_run_once_logs_execution_with_a_nonzero_exit_code(monkeypatch, tmp_path):
    from shss.resolutions import read_events

    monkeypatch.setenv("SHSS_RESOLUTIONS_PATH", str(tmp_path / "resolutions.jsonl"))
    fake_shell = _FakeShell(output="ls: cannot access\n", code=2)
    monkeypatch.setattr(cli_module, "PersistentShell", lambda: fake_shell)

    code = cli_module.run_once(_FakeLLMForCli("-Z"), "ls #@ option bidon @#")

    assert code == 2
    assert read_events(limit=1)[0]["exit_code"] == 2
