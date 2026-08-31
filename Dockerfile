# syntax=docker/dockerfile:1
#
# Deux cibles :
#   --target cpu   (défaut) : python:slim, inférence CPU. Image ~250 Mo.
#   --target cuda           : base CUDA runtime, offload GPU via --gpus.
#
#   docker build --target cpu  -t shss:cpu  .
#   docker build --target cuda -t shss:cuda .
#
# Le modèle GGUF n'est PAS dans l'image : l'entrypoint le télécharge au
# premier run dans le volume /models (voir docker/entrypoint.sh).

# ---------------------------------------------------------------------------
# CPU — stage de build : compile llama-cpp-python dans un venv isolé
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS build-cpu

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------------------------------------------------------------------------
# CPU — image finale
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS cpu

# libgomp1 : runtime OpenMP dont dépend libllama.so (absent de l'image slim).
RUN apt-get update && apt-get install -y --no-install-recommends \
        bash curl ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build-cpu /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/opt/shss/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SHSS_MODEL_TAG=1.5b-base \
    SHSS_HISTORY_PATH=/models/history.jsonl

COPY src/ /opt/shss/src/
COPY docker/entrypoint.sh /usr/local/bin/shss-entrypoint
RUN chmod +x /usr/local/bin/shss-entrypoint

VOLUME /models
WORKDIR /work
ENTRYPOINT ["shss-entrypoint"]
CMD []

# ---------------------------------------------------------------------------
# CUDA — stage de build : compile llama-cpp-python avec l'offload CUDA
# ---------------------------------------------------------------------------
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04 AS build-cuda

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python3-pip build-essential cmake git \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    CMAKE_ARGS="-DGGML_CUDA=on"

COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------------------------------------------------------------------------
# CUDA — image finale
# ---------------------------------------------------------------------------
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS cuda

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 bash curl ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build-cuda /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/opt/shss/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SHSS_MODEL_TAG=1.5b-base \
    SHSS_HISTORY_PATH=/models/history.jsonl \
    SHSS_N_GPU_LAYERS=-1

COPY src/ /opt/shss/src/
COPY docker/entrypoint.sh /usr/local/bin/shss-entrypoint
RUN chmod +x /usr/local/bin/shss-entrypoint

VOLUME /models
WORKDIR /work
ENTRYPOINT ["shss-entrypoint"]
CMD []
