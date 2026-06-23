FROM python:3.12-slim AS frontend

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      nodejs \
      npm \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g n \
    && n 22

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
    PATH=/root/.local/bin:/root/.cargo/bin:$PATH \
    PYTHONPATH=/app/src \
    HOST=0.0.0.0 \
    WORKBENCH_HERMES_ENABLED=1 \
    HOME=/var/data \
    HERMES_HOME=/var/data/hermes-home \
    HERMES_AGENT_SOURCE=/opt/hermes-agent \
    CODEX_HOME=/var/data/.codex \
    CODEX_AUTH_FILE=/var/data/.codex/auth.json \
    WORKBENCH_HERMES_PROVIDER=openai-codex \
    WORKBENCH_HERMES_MODEL=gpt-5.5 \
    WORKBENCH_HERMES_TOOLSET=mcp-priori_tactical \
    WORKBENCH_HERMES_PYTHON=/opt/hermes-agent/venv/bin/python \
    TQE_DATA_ROOT=/var/data/dataset/canonical/v1 \
    TQE_RAW_ROOT=/var/data/dataset/raw/idsse/figshare-28196177-v1 \
    TQE_RUNTIME_ROOT=/var/data/runtime \
    TQE_CACHE_ROOT=/var/data/cache \
    TQE_DATA_MANIFEST_PATH=/app/config/deploy/demo-data-manifest.json \
    TQE_KNOWLEDGE_PACK_PATH=/app/generated/tactical-knowledge-pack.json

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
      curl \
      git \
      nodejs \
      npm \
      ripgrep \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g n \
    && n 22 \
    && npm install -g @openai/codex@0.131.0 \
    && python -m pip install --upgrade pip

RUN git clone --recurse-submodules https://github.com/NousResearch/hermes-agent.git /opt/hermes-agent \
    && cd /opt/hermes-agent \
    && python -m venv venv \
    && /opt/hermes-agent/venv/bin/python -m pip install --upgrade pip \
    && /opt/hermes-agent/venv/bin/python -m pip install -e ".[all]" \
    && ln -sf /opt/hermes-agent/venv/bin/hermes /usr/local/bin/hermes

COPY pyproject.toml ./
COPY src ./src
COPY scripts ./scripts
COPY config ./config
COPY generated ./generated
COPY docs ./docs
RUN mkdir -p /app/delivery/n1d
COPY delivery/n1d/n1e-origin-bundle.json ./delivery/n1d/n1e-origin-bundle.json
COPY --from=frontend /app/apps/workbench-alpha/dist ./apps/workbench-alpha/dist
RUN python -m pip install --upgrade pip \
    && python -m pip install -e . \
    && chmod +x /app/scripts/render-start.sh /app/scripts/provision-demo-data.py /app/scripts/bootstrap-hermes.sh

EXPOSE 10000
CMD ["./scripts/render-start.sh"]
