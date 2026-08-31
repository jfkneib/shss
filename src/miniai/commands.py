"""Built-in utility commands recognized inside a #@ ... @# tag and
handled directly by miniai — no LLM call, instant, deterministic.

Deliberately plain text, no live/interactive picker: a menu you'd
navigate with arrow keys would need to capture raw keystrokes, which is
exactly what proved unreliable inside a bash `bind -x` handler (see
shell-integration/miniai.bash and docs/getting-started.md). These
commands work identically in the REPL, -c mode, and the bashrc Ctrl-G
integration because they're just text — see try_builtin().
"""

from pathlib import Path

from . import llm as llm_module
from .history import read_events

HELP_TEXT = """Commandes utilitaires miniai (traitees directement, sans appeler le LLM) :
  #@ models @#             liste les modeles Ollama + curates disponibles
  #@ model <tag> @#        change de modele pour la suite de cette session
                            (ex: model 3b, ou model deepseek-coder:1.3b)
  #@ model download <tag> @#  telecharge un modele curate (sans Ollama)
  #@ history [N] @#        affiche les N dernieres resolutions (defaut 20)
  #@ help @#               affiche cette aide"""


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
    # Ollama n'est pas requis pour miniai (voir README) : un fichier .gguf
    # pointe directement via MINIAI_MODEL_PATH marche tout aussi bien,
    # sans qu'Ollama soit installe. Cette commande ne peut lister QUE les
    # modeles geres par Ollama (c'est le seul "registre" disponible sur
    # disque) -- donc toujours montrer le modele reellement actif, meme
    # quand ce n'en est pas un, plutot que de laisser croire qu'il n'y a
    # rien de configure.
    models = llm_module.list_local_models()
    current_name, current_tag = _current_name_tag(mini_llm)

    lines = []
    if models:
        lines.append("Modeles Ollama disponibles :")
        for name, tag in models:
            marker = " (actif)" if (name, tag) == (current_name, current_tag) else ""
            lines.append(f"  - {name}:{tag}{marker}")
        lines.append("")
    else:
        lines.append("Aucun modele Ollama trouve sur cette machine.")
        lines.append("")

    if current_name is None:
        lines.append(f"Modele actif (hors registre Ollama) : {mini_llm.model_path}")
        lines.append(
            "Pour changer : export MINIAI_MODEL_PATH=/chemin/vers/autre.gguf, "
            "ou utilise un modele curate ci-dessous."
        )
    else:
        lines.append("Pour changer : #@ model <tag> @#  (ex: #@ model 3b @#)")

    lines.append("")
    lines.append(
        f"Modeles curates telechargeables sans Ollama ({llm_module.CURATED_MODEL_FAMILY}) :"
    )
    for tag, (_url, size_mb) in llm_module.CURATED_MODELS.items():
        downloaded = Path(llm_module.curated_model_path(tag)).is_file()
        status = "deja telecharge" if downloaded else f"~{size_mb} Mo"
        lines.append(f"  - {tag} ({status})")
    lines.append(
        "Pour telecharger : #@ model download <tag> @#  (ex: #@ model download 3b @#)"
    )

    return "\n".join(lines)


def _format_download_model(tag: str) -> str:
    if tag not in llm_module.CURATED_MODELS:
        options = ", ".join(llm_module.CURATED_MODELS)
        return f"miniai: '{tag}' n'est pas dans la liste curatee ({options})"

    already = Path(llm_module.curated_model_path(tag)).is_file()
    if already:
        return f"miniai: deja telecharge -> {llm_module.curated_model_path(tag)}"

    _url, size_mb = llm_module.CURATED_MODELS[tag]
    try:
        path = llm_module.download_curated_model(tag)
    except OSError as exc:
        return f"miniai: echec du telechargement (~{size_mb} Mo attendus) -- {exc}"

    return f"miniai: modele telecharge -> {path}\nUtilise #@ model {tag} @# pour l'activer."


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

    if lower == "model":
        return (
            "miniai: precise un tag -- #@ model <tag> @#  (ex: #@ model 3b @#)\n"
            "Voir aussi #@ models @# pour la liste, ou Ctrl-Y pour un selecteur interactif."
        )

    if lower.startswith("model download "):
        return _format_download_model(cmd[len("model download "):].strip())

    if lower.startswith("model "):
        return _format_switch_model(mini_llm, cmd[len("model "):].strip())

    if lower == "history" or lower.startswith("history "):
        parts = cmd.split()
        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
        return _format_history(limit)

    if lower in ("help", "aide", "?"):
        return HELP_TEXT

    return None
