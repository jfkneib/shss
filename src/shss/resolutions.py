"""Journal riche des resolutions : ce que shss a propose ou reutilise
(score de similarite, cas retenu, profil d'origine), ce qui s'est
reellement passe a l'execution (code de sortie, sortie), et les avis
explicites (#@ feedback bon|mauvais @#) -- distinct de history.py (la
ligne #@ ... @# brute, telle que tapee, journalisee a part).

Fichier ~/.shss/resolutions.jsonl (SHSS_RESOLUTIONS_PATH) -- separe de
history.jsonl deliberement : le contenu brut doit rester lisible sans
rien reconstruire (voir history.py), celui-ci peut se permettre d'etre
plus riche et plus structure, au prix d'un format qui evolue avec les
besoins (score/case_id/profile ajoutes une fois, kind="execution"/
"feedback" ajoutes ensuite).

Pas de couverture pour l'integration bashrc/Ctrl-G au-dela de la
resolution elle-meme (kind="case"/"script"/"inline"/"builtin", voir
log_event()) : ni log_execution() ni log_feedback() n'y sont
inaccessibles en soi (feedback marche partout, voir commands.py), mais
kind="execution" specifiquement ne peut venir que du REPL/-c (voir
cli.py) -- le process qui resout la balise a deja quitte avant que
bash execute la ligne dans ce mode-la, aucun moyen de recuperer son
resultat depuis ce cote-la."""

import json
import os
import time
from pathlib import Path


def _resolutions_path() -> Path:
    override = os.environ.get("SHSS_RESOLUTIONS_PATH")
    if override:
        return Path(override)
    return Path.home() / ".shss" / "resolutions.jsonl"


def _append(entry: dict) -> None:
    path = _resolutions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_event(
    request: str,
    prefix: str,
    suffix: str,
    result: str,
    kind: str,
    *,
    score: float = None,
    case_id: str = None,
    profile: str = None,
) -> None:
    """Append one resolved #@ ... @# to the resolutions file (JSON
    Lines).

    `score`/`case_id`/`profile` : seulement pour kind="case" (voir
    llm.generate_bash()) -- absents des autres kinds (script/inline/
    builtin), pour lesquels ils n'ont pas de sens. `profile` peut valoir
    None meme pour un cas reutilise (= la base par defaut, pas un
    profil nomme) : ecrit quand meme (`null` en JSON) plutot qu'omis,
    pour rester traçable meme depuis #@all@ (voir cases.py) ou le
    profil retenu peut differer de SHSS_CASES_PROFILE."""
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "request": request,
        "prefix": prefix,
        "suffix": suffix,
        "kind": kind,
        "result": result,
    }
    if score is not None:
        entry["score"] = score
    if case_id is not None:
        entry["case_id"] = case_id
    if kind == "case":
        entry["profile"] = profile
    _append(entry)


def _output_max_chars() -> int:
    raw = os.environ.get("SHSS_RESOLUTIONS_OUTPUT_MAX_CHARS")
    if raw is None or not raw.strip():
        return 4000
    try:
        return int(raw)
    except ValueError:
        return 4000


def log_execution(line: str, expanded: str, output: str, code: int) -> None:
    """Journalise le resultat REEL de l'execution d'une ligne, apres
    resolution -- distinct de log_event() (qui journalise la
    resolution elle-meme, avant execution, dans generate_bash()).
    Seul moyen de savoir si ce qui a ete propose/reutilise a
    effectivement fonctionne (code de sortie), pas seulement ce qui a
    ete affiche -- log_event() ne le sait pas, l'execution a lieu plus
    tard, dans cli.py (repl()/run_once()), une fois la ligne entiere
    (bash autour de la balise inclus) rendue a PersistentShell.run().

    Meme fichier que log_event() (resolutions.jsonl), nouveau
    kind="execution" -- associe a la resolution qui precede par simple
    ordre chronologique (une ligne = une resolution suivie de son
    execution), pas de cle etrangere explicite : suffisant pour une
    lecture humaine ou un script d'analyse qui parcourt le fichier
    dans l'ordre, plus simple qu'un id partage entre les deux entrees.

    `output` tronque a SHSS_RESOLUTIONS_OUTPUT_MAX_CHARS (4000 par
    defaut) -- une commande de recherche par contenu (voir profiles/
    grep-search/) peut renvoyer des pages entieres, inutile de les
    dupliquer integralement dans le journal."""
    max_chars = _output_max_chars()
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kind": "execution",
        "line": line,
        "expanded": expanded,
        "exit_code": code,
        "output": output[:max_chars],
    }
    if len(output) > max_chars:
        entry["output_truncated"] = True
    _append(entry)


def _last_request_entry(events):
    """La derniere entree "resolution" (avec une demande -- case/
    script/inline/builtin), en ignorant les entrees execution/feedback
    qui n'en ont pas -- utilise par log_feedback() pour savoir sur quoi
    porte l'avis. Un builtin "feedback ..." precedent (log_event() en
    journalise un pour lui-meme aussi, comme n'importe quel builtin)
    est ignore a son tour : sinon un deuxieme #@ feedback ... @# de
    suite s'attribuerait par erreur au premier plutot qu'a la vraie
    commande notee."""
    for e in reversed(events):
        kind = e.get("kind")
        if kind in ("execution", "feedback"):
            continue
        if kind == "builtin" and str(e.get("request", "")).strip().lower().startswith("feedback"):
            continue
        return e
    return None


def log_feedback(feedback: str, comment: str = "") -> dict:
    """Journalise un avis explicite (#@ feedback bon|mauvais [...] @#,
    voir commands.py) sur la derniere resolution -- jamais sur une
    execution ou un avis precedent (voir _last_request_entry()).

    Retourne l'entree visee (pour que l'appelant puisse confirmer sur
    quoi portait l'avis), ou None si le journal ne contient encore
    aucune resolution -- dans ce cas, rien n'est ecrit : un avis sans
    rien a rattacher n'apporte rien, plutot qu'une entree orpheline
    dans le fichier."""
    about = _last_request_entry(read_events(limit=None))
    if about is None:
        return None

    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kind": "feedback",
        "feedback": feedback,
        "about": {
            "request": about.get("request"),
            "kind": about.get("kind"),
            "result": about.get("result"),
        },
    }
    if comment:
        entry["comment"] = comment
    _append(entry)
    return about


def read_events(limit: int = 20):
    """Return the last `limit` resolutions entries, oldest first.
    `limit` None : tout le journal (utilise par log_feedback(), qui
    doit pouvoir remonter au-dela des 20 dernieres entrees si les
    dernieres sont des execution/feedback)."""
    path = _resolutions_path()
    if not path.is_file():
        return []

    events = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if raw:
            events.append(json.loads(raw))
    return events if limit is None else events[-limit:]


def format_event(e: dict) -> str:
    """Une ligne lisible pour un evenement, quel que soit son kind --
    utilise pour une lecture rapide de resolutions.jsonl (pas de
    commande dediee pour l'instant, voir profiles/README.md-style
    checklist : lecture directe du fichier suffit tant que le besoin
    n'est pas confirme)."""
    ts = e.get("timestamp", "?")
    kind = e.get("kind", "?")

    if kind == "execution":
        status = "ok" if e.get("exit_code") == 0 else f"code {e.get('exit_code')}"
        return f"[{ts}] {kind:9} {e.get('expanded', '')!r} -> {status}"

    if kind == "feedback":
        about = e.get("about") or {}
        request = about.get("request")
        on = f" (sur : {request!r})" if request else ""
        comment = f" -- {e['comment']}" if e.get("comment") else ""
        return f"[{ts}] {kind:9} {e.get('feedback', '?')}{on}{comment}"

    score = f" ({e['score'] * 100:.1f}%)" if "score" in e else ""
    return f"[{ts}] {kind:9} {e.get('request', '')!r}{score} -> {e.get('result', '')!r}"
