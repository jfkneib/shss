import json
import os
from pathlib import Path

MODEL_NAME = os.environ.get("MINIAI_MODEL_NAME", "qwen2.5-coder")
MODEL_TAG = os.environ.get("MINIAI_MODEL_TAG", "1.5b-base")

_KNOWN_OLLAMA_DIRS = [
    os.environ.get("OLLAMA_MODELS"),
    str(Path.home() / ".ollama" / "models"),
    "/usr/share/ollama/.ollama/models",
    "/media/jfk/Ollama/MODEL_OLLAMA",
]

FEW_SHOT = """Tu complètes une ligne de commande bash. Le symbole █ marque l'endroit à remplir.
Réponds uniquement par le texte qui remplace █, sur une seule ligne, sans explication.

Ligne: █
Demande: liste tous les fichiers pdf du dossier courant
Réponse: find . -iname "*.pdf"

Ligne: ls █
Demande: affiche aussi les fichiers caches
Réponse: -la

Ligne: echo debut █ echo fin
Demande: affiche la date du jour
Réponse: && date &&

Ligne: {prefix}█{suffix}
Demande: {request}
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

    raise FileNotFoundError(
        f"GGUF introuvable pour {model}:{tag}. "
        "Définis MINIAI_MODEL_PATH vers un fichier .gguf, "
        f"ou vérifie que `ollama pull {model}:{tag}` a bien été fait."
    )


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

    def generate_bash(self, request: str, prefix: str = "", suffix: str = "") -> str:
        self._ensure_loaded()
        prompt = FEW_SHOT.format(request=request.strip(), prefix=prefix, suffix=suffix)
        out = self._llm(
            prompt,
            max_tokens=64,
            temperature=0.2,
            stop=["\n", "Ligne:"],
        )
        return out["choices"][0]["text"].strip()
