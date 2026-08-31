"""Built-in utility commands recognized inside a #@ ... @# tag and
handled directly by miniai — no LLM call, instant, deterministic.

Deliberately plain text, no live/interactive picker: a menu you'd
navigate with arrow keys would need to capture raw keystrokes, which is
exactly what proved unreliable inside a bash `bind -x` handler (see
shell-integration/miniai.bash and docs/getting-started.md). These
commands work identically in the REPL, -c mode, and the bashrc Ctrl-G
integration because they're just text — see try_builtin().
"""

from . import llm as llm_module
from .history import read_events

HELP_TEXT = """Commandes utilitaires miniai (traitees directement, sans appeler le LLM) :
  #@ models @#        liste les modeles Ollama disponibles sur cette machine
  #@ model <tag> @#   change de modele pour la suite de cette session
                       (ex: model 3b, ou model deepseek-coder:1.3b)
  #@ history [N] @#   affiche les N dernieres resolutions (defaut 20)
  #@ help @#          affiche cette aide"""


def _current_name_tag(mini_llm):
    """Best-effort (name, tag) for the model mini_llm currently points
    to, by matching its blob path against every locally known manifest.
    Returns (None, None) if nothing matches (e.g. MINIAI_MODEL_PATH)."""
    for name, tag in llm_module.list_local_models():
        for models_dir in llm_module._KNOWN_OLLAMA_DIRS:
            if not models_dir:
                continue
            if llm_module._read_manifest_blob(models_dir, name, tag) == mini_llm.model_path:
                return name, tag
    return None, None


def _format_models_list(mini_llm) -> str:
    models = llm_module.list_local_models()
    if not models:
        return "Aucun modele Ollama trouve sur cette machine."

    current_name, current_tag = _current_name_tag(mini_llm)

    lines = ["Modeles Ollama disponibles :"]
    for name, tag in models:
        marker = " (actif)" if (name, tag) == (current_name, current_tag) else ""
        lines.append(f"  - {name}:{tag}{marker}")
    lines.append("")
    lines.append("Pour changer : #@ model <tag> @#  (ex: #@ model 3b @#)")
    return "\n".join(lines)


def _format_switch_model(mini_llm, target: str) -> str:
    if ":" in target:
        model, tag = target.split(":", 1)
    else:
        model, tag = None, target

    try:
        new_path = mini_llm.switch_model(model=model, tag=tag)
    except FileNotFoundError as exc:
        return f"miniai: {exc}"

    return (
        f"miniai: modele change -> {new_path}\n"
        "(actif pour le reste de cette session REPL ; sans effet persistant\n"
        "en mode -c ou via Ctrl-G dans une console normale, qui relancent un\n"
        "process a chaque fois -- exporte MINIAI_MODEL_TAG dans ~/.bashrc\n"
        "pour un changement permanent)"
    )


def _format_history(limit: int) -> str:
    events = read_events(limit)
    if not events:
        return "Historique vide."
    lines = []
    for e in events:
        lines.append(f"[{e['timestamp']}] {e['kind']:6} {e['request']!r} -> {e['result']!r}")
    return "\n".join(lines)


def try_builtin(request: str, mini_llm):
    """Return the replacement text if `request` is a recognized builtin
    command, else None (the caller should fall through to the LLM)."""
    cmd = request.strip()
    lower = cmd.lower()

    if lower in ("models", "modeles", "modèles"):
        return _format_models_list(mini_llm)

    if lower.startswith("model "):
        return _format_switch_model(mini_llm, cmd[len("model "):].strip())

    if lower == "history" or lower.startswith("history "):
        parts = cmd.split()
        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
        return _format_history(limit)

    if lower in ("help", "aide", "?"):
        return HELP_TEXT

    return None
