#!/usr/bin/env bash
# Point d'entrée du conteneur shss.
#
#   1. s'assure qu'un modèle GGUF est présent dans /models (volume) —
#      le télécharge au premier lancement depuis la liste curatée de
#      src/shss/llm.py (aucune URL dupliquée ici) ;
#   2. pointe SHSS_MODEL_PATH dessus ;
#   3. exec shss avec les arguments passés au `docker run`.
#
# Arg spécial « pull » : provisionne le modèle puis sort (pré-chauffage
# d'un volume sans ouvrir le REPL).
set -euo pipefail

TAG="${SHSS_MODEL_TAG:-1.5b-base}"
MODELS_DIR="${SHSS_MODELS_DIR:-/models}"
export SHSS_MODEL_PATH="${SHSS_MODEL_PATH:-$MODELS_DIR/qwen2.5-coder-$TAG.gguf}"
MODEL_PATH="$SHSS_MODEL_PATH"

if [ ! -f "$MODEL_PATH" ]; then
    url="$(python3 - "$TAG" <<'PY'
import sys
import shss.llm as m
tag = sys.argv[1]
try:
    print(m.CURATED_MODELS[tag][0])
except KeyError:
    sys.stderr.write(
        f"shss: tag '{tag}' inconnu — disponibles : {', '.join(m.CURATED_MODELS)}\n"
    )
    sys.exit(1)
PY
)"
    size_mb="$(python3 - "$TAG" <<'PY'
import sys
import shss.llm as m
print(m.CURATED_MODELS[sys.argv[1]][1])
PY
)"
    echo "shss: téléchargement du modèle $TAG (~${size_mb} Mo) vers $MODEL_PATH" >&2
    mkdir -p "$(dirname "$MODEL_PATH")"
    curl -fL --retry 3 --progress-bar -o "$MODEL_PATH.part" "$url"
    mv "$MODEL_PATH.part" "$MODEL_PATH"
    echo "shss: modèle prêt." >&2
fi

if [ "${1:-}" = "pull" ]; then
    echo "shss: modèle prêt -> $SHSS_MODEL_PATH"
    exit 0
fi

exec python3 -m shss.cli "$@"
