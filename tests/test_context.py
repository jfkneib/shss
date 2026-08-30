import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from miniai.context import build_context


def test_build_context_empty_when_no_files_mentioned(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert build_context("affiche la date du jour") == ""


def test_build_context_ignores_unrelated_files_in_cwd(tmp_path, monkeypatch):
    # Un fichier présent mais non mentionné dans la demande ne doit pas
    # apparaître dans le contexte : seule une mention explicite compte.
    (tmp_path / "a.txt").write_text("x")
    monkeypatch.chdir(tmp_path)
    assert build_context("affiche la date du jour") == ""


def test_build_context_previews_mentioned_file(tmp_path, monkeypatch):
    target = tmp_path / "dede.txt"
    target.write_text("un;deux;trois\nquatre;cinq\n")
    monkeypatch.chdir(tmp_path)

    context = build_context(f"formate {target} en json")

    assert f"Aperçu de {target} :" in context
    assert "un;deux;trois" in context
    assert "quatre;cinq" in context


def test_build_context_ignores_nonexistent_file_mentions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    context = build_context("formate /tmp/ne-existe-pas-du-tout.txt en json")
    assert "Aperçu" not in context
