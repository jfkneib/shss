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


@pytest.fixture(autouse=True)
def _isolate_home(monkeypatch, tmp_path):
    """Path.home() -> un tmp_path vide par test, jamais le vrai ~ de la
    machine qui fait tourner la suite. Necessaire depuis que
    generate_bash() (llm.py) appelle cases.find_matches_all_profiles()
    meme sur le chemin de generation normale (note de similarite,
    #@ q ... @#) : sans ceci, un test qui ne mocke pas Path.home()
    lui-meme trouvait reellement les profils installes sur la machine
    de dev (pc-stats/grep-search/tmux) et chargeait pour de vrai le
    modele d'embeddings -- lent, non deterministe, et un vrai bug
    trouve en le corrigeant (voir _cache_path() dans cases.py :
    SHSS_CASES_CACHE_PATH s'appliquait a tort meme avec un cases_path
    explicite, masquant le probleme differemment).

    Un test qui a besoin de sa propre isolation plus precise garde la
    main : son propre monkeypatch.setattr(cases_module.Path, "home",
    ...) prend le dessus sans conflit (meme classe Path partout)."""
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
