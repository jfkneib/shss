import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture(autouse=True)
def _isolate_journal_files(monkeypatch, tmp_path):
    """Aucun test ne doit jamais toucher aux vrais ~/.shss/history.jsonl
    ou resolutions.jsonl de la machine qui fait tourner la suite --
    tags.py journalise desormais la ligne brute a chaque resolution
    (voir history.log_line(), appele par expand_line()/
    resolve_pending_tag()), donc tout test qui passe par la (test_tags,
    test_inline, test_cli...) ecrirait sinon dans le vrai fichier.

    Une valeur par defaut, pas une contrainte : un test qui a besoin de
    relire le contenu ecrit peut toujours faire son propre
    monkeypatch.setenv(...) avec un chemin plus precis, qui prend le
    dessus sans conflit."""
    monkeypatch.setenv("SHSS_HISTORY_PATH", str(tmp_path / "history.jsonl"))
    monkeypatch.setenv("SHSS_RESOLUTIONS_PATH", str(tmp_path / "resolutions.jsonl"))
