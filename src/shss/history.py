"""Historique brut : la ligne #@ ... @# telle que tapee, sans aucune
transformation -- prefixe de profil compris (ex: '#@pc-stats@ energie
consommee par le pc @#'), rien retire, rien reconstruit.

Seul appelant : tags.py (expand_line()/resolve_pending_tag()), le point
de passage commun au REPL, au mode -c et a l'integration bashrc/Ctrl-G
-- les trois journalisent donc ici de la meme facon, y compris
Ctrl-G/bashrc qui ne peut PAS beneficier du journal riche a cote
(resolutions.py : score, cas retenu, execution, avis) puisque le
process qui resout la balise a deja quitte avant que bash execute la
ligne (voir resolutions.py, docs/getting-started.md section 8).

Distinct de resolutions.py **par construction** : une premiere version
melangeait tout dans un seul fichier ('history.jsonl'), et le champ
cense montrer la demande reelle finissait par etre noye dans un
'result' illisible (plusieurs variables d'env collees bout a bout avec
le chemin du script) -- pas exploitable pour relire ce qui a
effectivement ete tape, encore moins pour le croiser avec un profil
donne. Ce fichier-ci reste volontairement simple : une ligne = un
horodatage + le texte brut, jamais plus."""

import json
import os
import time
from pathlib import Path


def _history_path() -> Path:
    override = os.environ.get("SHSS_HISTORY_PATH")
    if override:
        return Path(override)
    return Path.home() / ".shss" / "history.jsonl"


def log_line(line: str) -> None:
    """Journalise `line` telle quelle -- le texte brut du #@ ... @#
    (delimiteurs et prefixe de profil eventuel compris), jamais la
    demande deja depouillee par tags._split_profile()."""
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "line": line}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_lines(limit: int = 20):
    """Return the last `limit` entries, oldest first."""
    path = _history_path()
    if not path.is_file():
        return []

    events = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if raw:
            events.append(json.loads(raw))
    return events[-limit:]


def format_line(e: dict) -> str:
    """Une ligne lisible pour `shss --history` / #@ history @#
    (commands.py) -- juste l'horodatage et le texte brut, rien a
    interpreter."""
    return f"[{e.get('timestamp', '?')}] {e.get('line', '')}"
