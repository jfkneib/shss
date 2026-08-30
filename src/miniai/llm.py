import json
import os
import tempfile
import time
import uuid
from pathlib import Path

from .context import build_context
from .history import log_event

MODEL_NAME = os.environ.get("MINIAI_MODEL_NAME", "qwen2.5-coder")
MODEL_TAG = os.environ.get("MINIAI_MODEL_TAG", "1.5b-base")

_KNOWN_OLLAMA_DIRS = [
    os.environ.get("OLLAMA_MODELS"),
    str(Path.home() / ".ollama" / "models"),
    "/usr/share/ollama/.ollama/models",
    "/media/jfk/Ollama/MODEL_OLLAMA",
]

# Emplacement où le paquet Debian (packaging/) installe/télécharge le
# modèle : ni un dossier Ollama, ni géré par MINIAI_MODEL_PATH, mais un
# filet de sécurité pour que `miniai` marche tout de suite après `apt
# install`, sans configuration.
SYSTEM_MODEL_PATH = "/opt/miniai/model/model.gguf"

# Dossier où sont écrits les scripts générés pour les demandes trop
# complexes pour tenir sur une ligne (un par utilisateur, pour ne pas se
# marcher dessus sur une machine partagée).
SCRIPT_DIR = Path(tempfile.gettempdir()) / f"miniai-{os.getuid()}"

_SHEBANG_EXTENSIONS = [
    ("python", ".py"),
    ("bash", ".sh"),
    ("sh", ".sh"),
    ("perl", ".pl"),
    ("node", ".js"),
]

FEW_SHOT = """Tu réponds à une demande soit par un fragment bash à insérer dans une
ligne existante (le symbole █ marque l'endroit à remplir), soit par un
script complet si la tâche demande plusieurs étapes (fichiers,
transformation de données, etc). Pour un script, commence directement par
une ligne shebang comme #!/usr/bin/env python3 ou #!/usr/bin/env bash, et
choisis le langage le plus adapté. Le script s'exécute seul, sans aucun
argument en ligne de commande : n'utilise jamais sys.argv ni $1/$2, écris
en dur dans le code les noms de fichiers mentionnés dans la demande.
Sinon, réponds par du bash sur une seule ligne, sans explication. Une
ligne "Contexte" peut donner le contenu réel d'un fichier mentionné :
utilise-le pour écrire un code adapté (ex: le bon séparateur de colonnes)
plutôt que de deviner.

Ligne: █
Demande: liste tous les fichiers pdf du dossier courant
Réponse: find . -iname "*.pdf"

Ligne: ls █
Demande: affiche aussi les fichiers caches
Réponse: -la

Ligne: echo debut █ echo fin
Demande: affiche la date du jour
Réponse: && date &&

Ligne: █
Demande: formate le fichier notes.txt en JSON valide et écris le résultat dans notes.json
Réponse: #!/usr/bin/env python3
import json
with open("notes.txt") as f:
    lignes = [l.strip() for l in f if l.strip()]
with open("notes.json", "w") as f:
    json.dump(lignes, f, ensure_ascii=False, indent=2)

Ligne: █
Contexte : Aperçu de /tmp/a.csv :
nom,age
alice,30
bob,25
Demande: convertis /tmp/a.csv en JSON et écris le résultat dans /tmp/a.json
Réponse: #!/usr/bin/env python3
import csv, json
with open("/tmp/a.csv") as f:
    lignes = list(csv.DictReader(f))
with open("/tmp/a.json", "w") as f:
    json.dump(lignes, f, ensure_ascii=False, indent=2)

Ligne: {prefix}█{suffix}
{context}Demande: {request}
Réponse:"""


def discover_gguf_path(model=MODEL_NAME, tag=MODEL_TAG):
    """Locate the raw GGUF blob already pulled by Ollama for `model:tag`,
    without going through the Ollama server/CLI at runtime."""
    override = os.environ.get("MINIAI_MODEL_PATH")
    if override:
        return override

    for models_dir in _KNOWN_OLLAMA_DIRS:
        if not models_dir:
            continue
        manifest_path = (
            Path(models_dir)
            / "manifests"
            / "registry.ollama.ai"
            / "library"
            / model
            / tag
        )
        if not manifest_path.is_file():
            continue

        manifest = json.loads(manifest_path.read_text())
        for layer in manifest.get("layers", []):
            if layer.get("mediaType") == "application/vnd.ollama.image.model":
                digest = layer["digest"].replace(":", "-", 1)
                blob_path = Path(models_dir) / "blobs" / digest
                if blob_path.is_file():
                    return str(blob_path)

    if Path(SYSTEM_MODEL_PATH).is_file():
        return SYSTEM_MODEL_PATH

    raise FileNotFoundError(
        f"GGUF introuvable pour {model}:{tag}. "
        "Définis MINIAI_MODEL_PATH vers un fichier .gguf, "
        f"ou vérifie que `ollama pull {model}:{tag}` a bien été fait."
    )


class ResolutionCancelled(Exception):
    """Raised when a `confirm` callback declines a generated result."""


def _script_extension(shebang_line: str) -> str:
    for keyword, ext in _SHEBANG_EXTENSIONS:
        if keyword in shebang_line:
            return ext
    return ".sh"


def _write_script(text: str) -> str:
    """Save a model-generated script (starting with a shebang line) to a
    fresh, timestamped, per-user file in tmp and return its path."""
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    ext = _script_extension(text.splitlines()[0])
    name = f"{time.strftime('%Y%m%d-%H%M%S')}_{uuid.uuid4().hex[:6]}{ext}"
    path = SCRIPT_DIR / name
    path.write_text(text, encoding="utf-8")
    path.chmod(0o700)
    return str(path)


class MiniLLM:
    def __init__(self, model_path=None, n_ctx=2048):
        self.model_path = model_path or discover_gguf_path()
        self._llm = None
        self._n_ctx = n_ctx

    def _ensure_loaded(self):
        if self._llm is None:
            from llama_cpp import Llama

            self._llm = Llama(
                model_path=self.model_path,
                n_ctx=self._n_ctx,
                verbose=False,
            )

    def generate_bash(
        self, request: str, prefix: str = "", suffix: str = "", confirm=None
    ) -> str:
        """Generate a bash fragment or script for `request`.

        If `confirm` is given, it's called with the text that would be
        used (the one-line fragment, or the full script source) before
        anything is written or logged; returning a falsy value raises
        ResolutionCancelled and leaves no trace (no file, no history
        entry). Used to let the caller show a "utiliser ce résultat ?"
        prompt for Ctrl-G, without slowing down the plain Enter-driven
        resolution path (which never passes `confirm`).
        """
        self._ensure_loaded()
        request = request.strip()
        context = build_context(request)
        prompt = FEW_SHOT.format(request=request, prefix=prefix, suffix=suffix, context=context)
        out = self._llm(
            prompt,
            max_tokens=200,
            temperature=0.2,
            stop=["\nLigne:"],
        )
        text = out["choices"][0]["text"].strip()

        if text.startswith("#!"):
            kind = "script"
            display = text
        else:
            # Pas un script : un seul fragment sur une ligne, on ignore
            # tout ce que le modèle aurait pu générer en trop après.
            kind = "inline"
            display = text.split("\n", 1)[0].strip()

        if confirm is not None and not confirm(display):
            raise ResolutionCancelled()

        result = _write_script(text) if kind == "script" else display

        log_event(request, prefix, suffix, result, kind)
        return result
