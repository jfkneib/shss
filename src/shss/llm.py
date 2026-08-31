import json
import os
import shutil
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

from .context import build_context
from .history import log_event

MODEL_NAME = os.environ.get("SHSS_MODEL_NAME", "qwen2.5-coder")
MODEL_TAG = os.environ.get("SHSS_MODEL_TAG", "1.5b-base")

_KNOWN_OLLAMA_DIRS = [
    os.environ.get("OLLAMA_MODELS"),
    str(Path.home() / ".ollama" / "models"),
    "/usr/share/ollama/.ollama/models",
    "/media/jfk/Ollama/MODEL_OLLAMA",
]

# Emplacement où le paquet Debian (packaging/) installe/télécharge le
# modèle : ni un dossier Ollama, ni géré par SHSS_MODEL_PATH, mais un
# filet de sécurité pour que `shss` marche tout de suite après `apt
# install`, sans configuration.
SYSTEM_MODEL_PATH = "/opt/shss/model/model.gguf"

# Dossier où sont écrits les scripts générés pour les demandes trop
# complexes pour tenir sur une ligne (un par utilisateur, pour ne pas se
# marcher dessus sur une machine partagée).
SCRIPT_DIR = Path(tempfile.gettempdir()) / f"shss-{os.getuid()}"

# Liste curatée de modèles téléchargeables directement (sans Ollama) —
# uniquement la famille qwen2.5-coder, seule testée/fiable avec le
# prompt few-shot de ce fichier (voir "Limites connues" dans le README :
# d'autres familles à taille comparable ont donné de moins bons
# résultats avec ce même prompt). Quantization Q4_K_M pour chaque taille,
# URLs vérifiées manuellement (HEAD request) avant d'être codées en dur.
CURATED_MODEL_FAMILY = "qwen2.5-coder"
CURATED_MODELS = {
    "1.5b-base": (
        (
            "https://huggingface.co/QuantFactory/Qwen2.5-Coder-1.5B-GGUF/"
            "resolve/main/Qwen2.5-Coder-1.5B.Q4_K_M.gguf"
        ),
        941,
    ),
    "3b": (
        (
            "https://huggingface.co/bartowski/Qwen2.5-Coder-3B-GGUF/"
            "resolve/main/Qwen2.5-Coder-3B-Q4_K_M.gguf"
        ),
        1840,
    ),
    "7b": (
        (
            "https://huggingface.co/QuantFactory/Qwen2.5-Coder-7B-GGUF/"
            "resolve/main/Qwen2.5-Coder-7B.Q4_K_M.gguf"
        ),
        4468,
    ),
}

# Emplacement partagé par toute la machine : un modèle téléchargé une
# fois ici (par un admin, via `sudo`) bénéficie à tous les utilisateurs,
# sans re-téléchargement — cohérent avec /opt/shss/model/model.gguf du
# paquet Debian. Consulté par tout le monde, mais seul root peut y écrire.
SYSTEM_MODELS_DIR = Path("/opt/shss/models")

# Repli par utilisateur si le modèle n'est pas (encore) dans l'emplacement
# partagé — c'est là qu'un utilisateur normal (sans sudo) télécharge le
# sien. Le choix du modèle *actif* reste toujours individuel (variables
# d'env par session) ; seul le fichier .gguf lui-même peut être partagé.
MODELS_DIR = Path.home() / ".shss" / "models"

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


def _read_manifest_blob(models_dir, model, tag):
    """Return the GGUF blob path for `model:tag` in `models_dir`'s Ollama
    manifest tree, or None if there's no such manifest/blob there."""
    manifest_path = (
        Path(models_dir) / "manifests" / "registry.ollama.ai" / "library" / model / tag
    )
    if not manifest_path.is_file():
        return None

    manifest = json.loads(manifest_path.read_text())
    for layer in manifest.get("layers", []):
        if layer.get("mediaType") == "application/vnd.ollama.image.model":
            digest = layer["digest"].replace(":", "-", 1)
            blob_path = Path(models_dir) / "blobs" / digest
            if blob_path.is_file():
                return str(blob_path)
    return None


def _discover_ollama_only(model, tag):
    """Search only the known Ollama directories for `model:tag`, ignoring
    SHSS_MODEL_PATH/SYSTEM_MODEL_PATH entirely. Used by switch_model():
    when a user explicitly names a model to switch to, honor that even
    if SHSS_MODEL_PATH is set — a plain discover_gguf_path() call would
    just keep returning the override no matter what tag was asked for."""
    for models_dir in _KNOWN_OLLAMA_DIRS:
        if not models_dir:
            continue
        blob = _read_manifest_blob(models_dir, model, tag)
        if blob:
            return blob

    raise FileNotFoundError(
        f"GGUF introuvable pour {model}:{tag} dans les dossiers Ollama connus. "
        "shss ne peut changer de modele que vers un modele deja tire par Ollama "
        f"(`ollama pull {model}:{tag}`) ; pour un .gguf ailleurs, utilise "
        "SHSS_MODEL_PATH directement."
    )


def discover_gguf_path(model=MODEL_NAME, tag=MODEL_TAG):
    """Locate the raw GGUF blob already pulled by Ollama for `model:tag`,
    without going through the Ollama server/CLI at runtime."""
    override = os.environ.get("SHSS_MODEL_PATH")
    if override:
        return override

    try:
        return _discover_ollama_only(model, tag)
    except FileNotFoundError:
        pass

    if Path(SYSTEM_MODEL_PATH).is_file():
        return SYSTEM_MODEL_PATH

    raise FileNotFoundError(
        f"GGUF introuvable pour {model}:{tag}. "
        "Définis SHSS_MODEL_PATH vers un fichier .gguf, "
        f"ou vérifie que `ollama pull {model}:{tag}` a bien été fait."
    )


def list_local_models():
    """List every (name, tag) whose manifest exists in any known Ollama
    models directory — every model discover_gguf_path() could resolve
    to, for any name/tag, deduplicated and sorted."""
    seen = set()
    results = []
    for models_dir in _KNOWN_OLLAMA_DIRS:
        if not models_dir:
            continue
        library = Path(models_dir) / "manifests" / "registry.ollama.ai" / "library"
        if not library.is_dir():
            continue
        for name_dir in sorted(p for p in library.iterdir() if p.is_dir()):
            for tag_file in sorted(p for p in name_dir.iterdir() if p.is_file()):
                key = (name_dir.name, tag_file.name)
                if key not in seen:
                    seen.add(key)
                    results.append(key)
    return results


def curated_model_path(tag: str) -> str:
    """Where `tag` is (or would be) on disk: the shared system location
    if it's already there (one download benefits every user), else the
    per-user one — regardless of which one actually has the file yet."""
    filename = f"{CURATED_MODEL_FAMILY}-{tag}.gguf"
    system_path = SYSTEM_MODELS_DIR / filename
    if system_path.is_file():
        return str(system_path)
    return str(MODELS_DIR / filename)


def download_curated_model(tag: str) -> str:
    """Download a curated qwen2.5-coder GGUF (skipped if already present,
    system or per-user) and return its path. Blocking — a multi-GB file
    can take a while; only called from an explicit
    "#@ model download <tag> @#", never automatically.

    Run as root (e.g. `sudo shss -c '#@ model download 3b @#'`), it
    downloads to SYSTEM_MODELS_DIR (/opt/shss/models/), shared by
    every user on the machine — one download, everyone benefits, though
    each user still individually chooses which model is *active* for
    them. A normal user without root downloads to their own MODELS_DIR
    instead, since they can't write to /opt/shss/."""
    if tag not in CURATED_MODELS:
        raise KeyError(
            f"'{tag}' n'est pas dans la liste curatée ({', '.join(CURATED_MODELS)})"
        )

    existing = Path(curated_model_path(tag))
    if existing.is_file():
        return str(existing)

    shared = hasattr(os, "geteuid") and os.geteuid() == 0
    dest_dir = SYSTEM_MODELS_DIR if shared else MODELS_DIR
    dest = dest_dir / f"{CURATED_MODEL_FAMILY}-{tag}.gguf"

    url, _size_mb = CURATED_MODELS[tag]
    dest_dir.mkdir(parents=True, exist_ok=True)
    tmp_dest = dest.with_name(dest.name + ".part")
    urllib.request.urlretrieve(url, tmp_dest)
    tmp_dest.rename(dest)
    if shared:
        dest_dir.chmod(0o755)
        dest.chmod(0o644)  # lisible par tous les utilisateurs de la machine
    return str(dest)


def _env_int(name: str, default):
    """int() of env var `name`, or `default` if unset/empty/unparseable."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _gpu_layers() -> int:
    """How many model layers to offload to the GPU.

    `SHSS_N_GPU_LAYERS` unset or "auto" (the default): offload everything
    (-1) when an NVIDIA GPU looks present (`nvidia-smi` on PATH), nothing
    (0) otherwise. An explicit integer always wins. A non-zero value is
    harmless on a CPU-only llama.cpp build — llama.cpp just ignores it —
    so the same image works with and without `--gpus`.
    """
    raw = os.environ.get("SHSS_N_GPU_LAYERS", "auto").strip().lower()
    if raw in ("", "auto"):
        return -1 if shutil.which("nvidia-smi") else 0
    try:
        return int(raw)
    except ValueError:
        return 0


class ResolutionCancelled(Exception):
    """Raised when a `confirm` callback declines a generated result."""


def _script_extension(shebang_line: str) -> str:
    for keyword, ext in _SHEBANG_EXTENSIONS:
        if keyword in shebang_line:
            return ext
    return ".sh"


def _as_display_script(text: str) -> str:
    """Wrap plain text (e.g. a builtin command's output) as a tiny bash
    script that just prints it via a quoted heredoc — safe regardless of
    quotes/`$`/backticks in the text, since nothing inside a
    single-quoted heredoc delimiter is expanded."""
    return "#!/usr/bin/env bash\ncat <<'SHSS_EOF'\n" + text + "\nSHSS_EOF\n"


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
        # SHSS_N_CTX lets a deployment shrink the context window (the
        # few-shot prompt + a file preview fit well under 1024) to cut
        # RAM and prompt-eval time.
        self._n_ctx = _env_int("SHSS_N_CTX", n_ctx)

    def _ensure_loaded(self):
        if self._llm is None:
            from llama_cpp import Llama

            self._llm = Llama(
                model_path=self.model_path,
                n_ctx=self._n_ctx,
                # None => llama.cpp picks a default; SHSS_N_THREADS should
                # be set to the number of physical cores (llama.cpp often
                # guesses badly inside a container).
                n_threads=_env_int("SHSS_N_THREADS", None),
                n_gpu_layers=_gpu_layers(),
                verbose=False,
            )

    def switch_model(self, model=None, tag=None, path=None):
        """Point this instance at a different GGUF, reloaded lazily on
        the next generate_bash() call. Persists for the rest of this
        process's life (the REPL's whole session; a single resolution
        in -c / the bashrc Ctrl-G integration, which start a fresh
        process each time).

        Uses _discover_ollama_only(), not discover_gguf_path(): the
        latter checks SHSS_MODEL_PATH first, which would silently
        ignore whatever model/tag was explicitly requested here and
        keep returning the same override no matter what. Falls back to
        an already-downloaded curated model (~/.shss/models/, see
        download_curated_model()) if Ollama doesn't have it — this is
        the only way to switch models at all without Ollama installed.
        """
        if path:
            new_path = path
        else:
            model = model or MODEL_NAME
            tag = tag or MODEL_TAG
            try:
                new_path = _discover_ollama_only(model, tag)
            except FileNotFoundError as exc:
                curated_path = Path(curated_model_path(tag))
                if model == CURATED_MODEL_FAMILY and curated_path.is_file():
                    new_path = str(curated_path)
                elif model == CURATED_MODEL_FAMILY and tag in CURATED_MODELS:
                    size_mb = CURATED_MODELS[tag][1]
                    raise FileNotFoundError(
                        f"{model}:{tag} introuvable via Ollama, et pas encore téléchargé "
                        f"(#@ model download {tag} @#, ~{size_mb} Mo)"
                    ) from exc
                else:
                    raise
        self.model_path = new_path
        self._llm = None
        return new_path

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

        `request` is checked against built-in commands (see commands.py)
        first — "models", "model <tag>", "history [N]", "help" — which
        never touch the LLM at all and never ask for confirmation
        (deterministic, instant, nothing to review).
        """
        request = request.strip()

        from .commands import try_builtin

        builtin_output = try_builtin(request, self)
        if builtin_output is not None:
            result = _write_script(_as_display_script(builtin_output))
            log_event(request, prefix, suffix, result, "builtin")
            return result

        self._ensure_loaded()
        context = build_context(request)
        prompt = FEW_SHOT.format(request=request, prefix=prefix, suffix=suffix, context=context)
        out = self._llm(
            prompt,
            max_tokens=200,
            temperature=0.2,
            repeat_penalty=1.1,
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
