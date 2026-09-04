import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import shss.cases as cases_module
import shss.cases_cli as cli_module
import shss.cases_gui as gui_module


def _setup_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("SHSS_CASES_PATH", str(tmp_path / "cases.json"))
    monkeypatch.setenv("SHSS_CASES_CACHE_PATH", str(tmp_path / "cases.embeddings.json"))


def test_build_parser_edit_accepts_partial_fields():
    args = cli_module.build_parser().parse_args(["edit", "energie", "--note", "nouvelle note"])
    assert args.id == "energie"
    assert args.note == "nouvelle note"
    assert args.request is None
    assert args.script_file is None
    assert args.script_stdin is False


def test_build_parser_gui_has_no_extra_args():
    args = cli_module.build_parser().parse_args(["gui"])
    assert args.func is cli_module._cmd_gui


def test_cmd_edit_updates_only_given_field(monkeypatch, tmp_path, capsys):
    _setup_paths(monkeypatch, tmp_path)
    cases_module.save_cases(
        [{"id": "energie", "requests": ["x"], "script": "echo x", "note": "ancienne"}]
    )

    args = cli_module.build_parser().parse_args(["edit", "energie", "--note", "nouvelle"])
    code = cli_module._cmd_edit(args)

    assert code == 0
    updated = cases_module.load_cases()[0]
    assert updated["note"] == "nouvelle"
    assert updated["requests"] == ["x"]  # inchange
    assert updated["script"] == "echo x"  # inchange


def test_cmd_edit_missing_case_returns_1(monkeypatch, tmp_path, capsys):
    _setup_paths(monkeypatch, tmp_path)

    args = cli_module.build_parser().parse_args(["edit", "absent", "--note", "x"])
    code = cli_module._cmd_edit(args)

    assert code == 1
    assert "absent" in capsys.readouterr().err


def test_cmd_add_stdin_flag_sets_input_mode(monkeypatch, tmp_path):
    _setup_paths(monkeypatch, tmp_path)
    args = cli_module.build_parser().parse_args(
        ["add", "fix-select", "--request", 'corrige : "x"', "--stdin"]
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO("#!/usr/bin/env bash\n"))

    code = cli_module._cmd_add(args)

    assert code == 0
    assert cases_module.load_cases()[0]["input"] == "stdin"


def test_cmd_edit_no_stdin_clears_input_mode(monkeypatch, tmp_path):
    _setup_paths(monkeypatch, tmp_path)
    cases_module.save_cases(
        [{"id": "fix", "requests": ["x"], "script": "echo x", "input": "stdin"}]
    )

    args = cli_module.build_parser().parse_args(["edit", "fix", "--no-stdin"])
    code = cli_module._cmd_edit(args)

    assert code == 0
    assert "input" not in cases_module.load_cases()[0]


def test_cmd_add_threshold_flag_sets_field(monkeypatch, tmp_path):
    _setup_paths(monkeypatch, tmp_path)
    args = cli_module.build_parser().parse_args(
        ["add", "fix", "--request", "x", "--threshold", "0.85"]
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO("#!/usr/bin/env bash\n"))

    assert cli_module._cmd_add(args) == 0
    assert cases_module.load_cases()[0]["threshold"] == 0.85


def test_cmd_edit_clear_threshold_removes_field(monkeypatch, tmp_path):
    _setup_paths(monkeypatch, tmp_path)
    cases_module.save_cases([{"id": "fix", "requests": ["x"], "script": "echo x", "threshold": 0.9}])

    args = cli_module.build_parser().parse_args(["edit", "fix", "--clear-threshold"])
    assert cli_module._cmd_edit(args) == 0
    assert "threshold" not in cases_module.load_cases()[0]


def test_cmd_reindex_missing_embedding_model_gives_friendly_error(monkeypatch, tmp_path, capsys):
    _setup_paths(monkeypatch, tmp_path)
    cases_module.save_cases([{"id": "x", "requests": ["une demande"], "script": "echo x"}])

    def _boom(*a, **kw):
        raise FileNotFoundError("GGUF introuvable pour le modele d'embeddings")

    monkeypatch.setattr(cases_module, "reindex", _boom)

    args = cli_module.build_parser().parse_args(["reindex"])
    code = cli_module._cmd_reindex(args)

    assert code == 1
    err = capsys.readouterr().err
    assert "GGUF introuvable" in err
    assert "Traceback" not in err


def test_cmd_test_missing_embedding_model_gives_friendly_error(monkeypatch, tmp_path, capsys):
    _setup_paths(monkeypatch, tmp_path)
    cases_module.save_cases([{"id": "x", "requests": ["une demande"], "script": "echo x"}])

    def _boom(*a, **kw):
        raise FileNotFoundError("GGUF introuvable pour le modele d'embeddings")

    monkeypatch.setattr(cases_module, "find_matches", _boom)

    args = cli_module.build_parser().parse_args(["test", "une demande"])
    code = cli_module._cmd_test(args)

    assert code == 1
    err = capsys.readouterr().err
    assert "GGUF introuvable" in err
    assert "Traceback" not in err


def test_main_profile_flag_sets_env_var_before_dispatch(monkeypatch, tmp_path):
    monkeypatch.delenv("SHSS_CASES_PATH", raising=False)
    monkeypatch.delenv("SHSS_CASES_PROFILE", raising=False)
    monkeypatch.setattr(cases_module.Path, "home", staticmethod(lambda: tmp_path))

    # main() ecrit dans os.environ directement (pas via monkeypatch,
    # c'est le code teste qui le fait) -- nettoyage manuel pour ne pas
    # laisser fuiter la variable vers les tests suivants.
    try:
        code = cli_module.main(["--profile", "pc-stats", "list"])
        assert code == 0
        assert os.environ["SHSS_CASES_PROFILE"] == "pc-stats"
        assert cases_module._cases_path() == tmp_path / ".shss" / "profiles" / "pc-stats" / "cases.json"
    finally:
        os.environ.pop("SHSS_CASES_PROFILE", None)


def test_main_without_profile_flag_leaves_env_var_untouched(monkeypatch, tmp_path):
    _setup_paths(monkeypatch, tmp_path)
    monkeypatch.delenv("SHSS_CASES_PROFILE", raising=False)

    cli_module.main(["list"])

    assert "SHSS_CASES_PROFILE" not in os.environ


def test_cmd_gui_returns_0_when_it_opens(monkeypatch):
    monkeypatch.setattr(gui_module, "try_run", lambda: True)
    args = cli_module.build_parser().parse_args(["gui"])
    assert cli_module._cmd_gui(args) == 0


def test_cmd_gui_returns_1_with_message_when_unavailable(monkeypatch, capsys):
    monkeypatch.setattr(gui_module, "try_run", lambda: False)
    args = cli_module.build_parser().parse_args(["gui"])

    code = cli_module._cmd_gui(args)

    assert code == 1
    assert "tkinter" in capsys.readouterr().err.lower()


def test_main_bare_invocation_opens_gui_when_possible(monkeypatch):
    monkeypatch.setattr(gui_module, "try_run", lambda: True)
    assert cli_module.main([]) == 0


def test_main_bare_invocation_falls_back_to_help_when_gui_unavailable(monkeypatch, capsys):
    monkeypatch.setattr(gui_module, "try_run", lambda: False)

    code = cli_module.main([])

    assert code == 0
    out_err = capsys.readouterr()
    assert "usage: shss-cases" in out_err.out


def test_try_run_returns_false_when_tk_cannot_open(monkeypatch):
    # Simule "pas d'affichage utilisable" (ex: SSH sans X) sans jamais
    # toucher un vrai Tk -- tk.Tk() leve TclError dans ce cas reel.
    import tkinter

    def _boom():
        raise tkinter.TclError("no display name and no $DISPLAY environment variable")

    monkeypatch.setattr(tkinter, "Tk", _boom)
    assert gui_module.try_run() is False


def test_try_run_opens_app_and_runs_mainloop_when_tk_available(monkeypatch):
    # Ne construit jamais la vraie fenetre (_App reste bouchonne) --
    # sinon ce test bloquerait sur un vrai root.mainloop() dans tout
    # environnement qui a effectivement un affichage (ce poste, par
    # exemple : DISPLAY est bien defini ici).
    import tkinter

    calls = {}

    class _FakeRoot:
        def mainloop(self):
            calls["ran"] = True

    monkeypatch.setattr(tkinter, "Tk", lambda: _FakeRoot())
    monkeypatch.setattr(gui_module, "_App", lambda root: calls.setdefault("app_root", root))

    assert gui_module.try_run() is True
    assert calls.get("ran") is True
    assert isinstance(calls.get("app_root"), _FakeRoot)
