import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import miniai.inline as inline_module


class _FakeLLM:
    """Mimics MiniLLM.generate_bash: `result` is always what gets spliced
    into the line (single-line, e.g. a script's file path), `display` is
    what confirm() is shown (can be multi-line, e.g. full script source).
    """

    def __init__(self, result, display=None):
        self.result = result
        self.display = display if display is not None else result

    def generate_bash(self, request, prefix="", suffix="", confirm=None):
        if confirm is not None:
            confirm(self.display)
        return self.result


def test_main_prints_line_point_then_display(monkeypatch, capsys):
    monkeypatch.setattr(inline_module, "MiniLLM", lambda: _FakeLLM("-S"))
    line = "ls #@ trie par taille"
    inline_module.main([line, str(len(line))])

    out = capsys.readouterr().out.splitlines()
    assert out[0] == "ls -S"
    assert out[1] == str(len("ls -S"))
    assert out[2] == "-S"


def test_main_no_tag_found_leaves_display_empty(monkeypatch, capsys):
    monkeypatch.setattr(inline_module, "MiniLLM", lambda: _FakeLLM("unused"))
    line = "ls -la"
    inline_module.main([line, str(len(line))])

    out = capsys.readouterr().out.splitlines()
    assert out[0] == line
    assert out[1] == str(len(line))
    assert out[2] == ""


def test_main_multiline_script_display_stays_multiline(monkeypatch, capsys):
    script = "#!/usr/bin/env python3\nprint('hi')"
    monkeypatch.setattr(
        inline_module, "MiniLLM", lambda: _FakeLLM("/tmp/fake.py", display=script)
    )
    line = "#@ un script @#"
    inline_module.main([line, str(len(line))])

    out_lines = capsys.readouterr().out.split("\n")
    assert out_lines[0] == "/tmp/fake.py"
    assert out_lines[1] == str(len("/tmp/fake.py"))
    assert "\n".join(out_lines[2:]).rstrip("\n") == script
