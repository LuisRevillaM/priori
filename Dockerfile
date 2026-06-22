FROM node:22-bookworm-slim AS frontend

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
COPY scripts ./scripts
COPY config ./config
COPY generated ./generated
RUN python3 -m venv .venv \
    && .venv/bin/python -m pip install --upgrade pip \
    && .venv/bin/python -m pip install -e .

COPY apps/workbench-alpha/package*.json ./apps/workbench-alpha/
RUN npm --prefix apps/workbench-alpha ci
COPY apps/workbench-alpha ./apps/workbench-alpha
RUN npm --prefix apps/workbench-alpha run build


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    HOST=0.0.0.0 \
    WORKBENCH_HERMES_ENABLED=0 \
    TQE_DATA_ROOT=/var/data/dataset/canonical/v1 \
    TQE_RAW_ROOT=/var/data/dataset/raw/idsse/figshare-28196177-v1 \
    TQE_RUNTIME_ROOT=/var/data/runtime \
    TQE_CACHE_ROOT=/var/data/cache \
    TQE_DATA_MANIFEST_PATH=/app/config/deploy/demo-data-manifest.json \
    TQE_KNOWLEDGE_PACK_PATH=/app/generated/tactical-knowledge-pack.json

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
COPY scripts ./scripts
COPY config ./config
COPY generated ./generated
COPY docs ./docs
COPY --from=frontend /app/apps/workbench-alpha/dist ./apps/workbench-alpha/dist
RUN python -m pip install --upgrade pip \
    && python -m pip install -e . \
    && chmod +x /app/scripts/render-start.sh /app/scripts/provision-demo-data.py

EXPOSE 10000
CMD ["./scripts/render-start.sh"]
