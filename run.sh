#!/usr/bin/env bash
# Lance shss dans Docker : monte le dossier courant comme espace de
# travail, garde le modèle dans un volume nommé (téléchargé une seule
# fois), et détecte automatiquement un GPU NVIDIA.
#
#   ./run.sh                      # REPL
#   ./run.sh -c 'ls #@ trie @#'   # one-shot
#   ./run.sh pull                 # pré-télécharge le modèle puis sort
#
# Variables :
#   SHSS_IMAGE      image à utiliser (défaut: shss:cpu, ou shss:cuda si GPU)
#   SHSS_MODEL_TAG  1.5b-base (défaut) | 3b | 7b
#   SHSS_VOLUME     nom du volume modèle (défaut: shss-models)
set -euo pipefail

VOLUME="${SHSS_VOLUME:-shss-models}"
TAG="${SHSS_MODEL_TAG:-1.5b-base}"

have_image() { docker image inspect "$1" >/dev/null 2>&1; }

gpu_args=()
if [ -n "${SHSS_IMAGE:-}" ]; then
    image="$SHSS_IMAGE"
elif command -v nvidia-smi >/dev/null 2>&1 \
        && docker info 2>/dev/null | grep -qi nvidia \
        && have_image shss:cuda; then
    image="shss:cuda"
    gpu_args=(--gpus all)
else
    image="shss:cpu"
    if command -v nvidia-smi >/dev/null 2>&1 && ! have_image shss:cuda; then
        echo "run.sh: GPU détecté mais image shss:cuda absente -> repli sur shss:cpu" >&2
        echo "        (pour le GPU : docker build --target cuda -t shss:cuda .)" >&2
    fi
fi

if ! have_image "$image"; then
    echo "run.sh: image '$image' introuvable en local. Construis-la :" >&2
    echo "  docker build --target ${image#shss:} -t $image \"$(cd "$(dirname "$0")" && pwd)\"" >&2
    exit 1
fi

docker volume inspect "$VOLUME" >/dev/null 2>&1 || docker volume create "$VOLUME" >/dev/null

# -t seulement si on a un vrai terminal (le REPL en a besoin ; un
# `./run.sh -c '...'` dans un pipe/CI n'en a pas).
tty_args=(-i)
[ -t 0 ] && tty_args=(-i -t)

exec docker run --rm "${tty_args[@]}" "${gpu_args[@]}" \
    -e SHSS_MODEL_TAG="$TAG" \
    -e SHSS_N_THREADS="${SHSS_N_THREADS:-$(nproc)}" \
    -v "$VOLUME:/models" \
    -v "$PWD:/work" -w /work \
    "$image" "$@"
