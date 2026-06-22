#!/usr/bin/env bash
set -euo pipefail

export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-10000}"
export TQE_DATA_ROOT="${TQE_DATA_ROOT:-/var/data/dataset/canonical/v1}"
export TQE_RAW_ROOT="${TQE_RAW_ROOT:-/var/data/dataset/raw/idsse/figshare-28196177-v1}"
export TQE_RUNTIME_ROOT="${TQE_RUNTIME_ROOT:-/var/data/runtime}"
export TQE_CACHE_ROOT="${TQE_CACHE_ROOT:-/var/data/cache}"
export TQE_DATA_MANIFEST_PATH="${TQE_DATA_MANIFEST_PATH:-/app/config/deploy/demo-data-manifest.json}"
export TQE_KNOWLEDGE_PACK_PATH="${TQE_KNOWLEDGE_PACK_PATH:-/app/generated/tactical-knowledge-pack.json}"
export WORKBENCH_HERMES_ENABLED="${WORKBENCH_HERMES_ENABLED:-1}"
export HOME="${HOME:-/var/data}"
export HERMES_HOME="${HERMES_HOME:-/var/data/hermes-home}"
export CODEX_HOME="${CODEX_HOME:-/var/data/.codex}"
export HERMES_AGENT_SOURCE="${HERMES_AGENT_SOURCE:-/opt/hermes-agent}"
export WORKBENCH_HERMES_PYTHON="${WORKBENCH_HERMES_PYTHON:-/opt/hermes-agent/venv/bin/python}"

mkdir -p "$TQE_DATA_ROOT" "$TQE_RAW_ROOT" "$TQE_RUNTIME_ROOT" "$TQE_CACHE_ROOT"

python /app/scripts/provision-demo-data.py \
  --dataset-root /var/data/dataset \
  --manifest "$TQE_DATA_MANIFEST_PATH"

if [[ "$WORKBENCH_HERMES_ENABLED" == "1" ]]; then
  /app/scripts/bootstrap-hermes.sh
fi

exec python -m tqe.workshop.app_service \
  --host "$HOST" \
  --port "$PORT" \
  --static-root /app/apps/workbench-alpha/dist \
  --output-root "$TQE_RUNTIME_ROOT"
