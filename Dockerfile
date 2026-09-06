# syntax=docker/dockerfile:1
# Do not compile the Svelte app in this image. Hugging Face cpu-basic builders
# OOM during Vite (exit 137). Put a production build in main/frontend-dist first
# (`python3 main/scripts/deploy_space.py` does that locally).
FROM python:3.11.13-slim-bookworm
ENV PYTHONUNBUFFERED=1 ENV=prod PORT=7860 HOST=0.0.0.0 DOCKER=true \
    DATA_DIR=/app/backend/data HF_HOME=/app/backend/data/cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/backend/data/cache/embedding \
    TIKTOKEN_CACHE_DIR=/app/backend/data/cache/tiktoken \
    SCARF_NO_ANALYTICS=true DO_NOT_TRACK=true ANONYMIZED_TELEMETRY=false \
    ENABLE_OLLAMA_API=false RAG_EMBEDDING_MODEL_AUTO_UPDATE=false \
    WHISPER_MODEL_AUTO_UPDATE=false UV_LINK_MODE=copy \
    UV_CONCURRENT_DOWNLOADS=1 UV_CONCURRENT_INSTALLS=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libmariadb-dev ffmpeg libsm6 libxext6 curl ca-certificates pandoc git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 1000 --create-home app
WORKDIR /app/backend
COPY main/upstream/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir uv==0.8.17 \
    && uv pip install --system 'torch==2.9.1' 'torchvision==0.24.1' 'torchaudio==2.9.1' --index-url https://download.pytorch.org/whl/cpu \
    && uv pip install --system -r requirements.txt
COPY --chown=1000:1000 main/upstream/backend/ ./
COPY --chown=1000:1000 main/frontend-dist /app/build
COPY --chown=1000:1000 main/upstream/package.json main/upstream/CHANGELOG.md /app/
COPY --chown=1000:1000 main/scripts/entrypoint.sh main/scripts/reset_owner_password.py /app/scripts/
RUN test -f /app/build/index.html \
    && mkdir -p /app/backend/data && chown -R 1000:1000 /app
USER 1000:1000
EXPOSE 7860
HEALTHCHECK --interval=30s --start-period=180s CMD curl --fail --silent http://127.0.0.1:7860/health || exit 1
ENTRYPOINT ["/bin/sh", "/app/scripts/entrypoint.sh"]
