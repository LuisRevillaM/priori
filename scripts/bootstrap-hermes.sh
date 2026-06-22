#!/usr/bin/env bash
set -euo pipefail

export HOME="${HOME:-/var/data}"
export HERMES_HOME="${HERMES_HOME:-/var/data/hermes-home}"
export HERMES_AGENT_SOURCE="${HERMES_AGENT_SOURCE:-/opt/hermes-agent}"
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export CODEX_AUTH_FILE="${CODEX_AUTH_FILE:-$CODEX_HOME/auth.json}"
export WORKBENCH_HERMES_PROVIDER="${WORKBENCH_HERMES_PROVIDER:-openai-codex}"
export WORKBENCH_HERMES_MODEL="${WORKBENCH_HERMES_MODEL:-gpt-5.5}"
export WORKBENCH_HERMES_TOOLSET="${WORKBENCH_HERMES_TOOLSET:-mcp-priori_tactical}"
export WORKBENCH_HERMES_PYTHON="${WORKBENCH_HERMES_PYTHON:-/opt/hermes-agent/venv/bin/python}"

mkdir -p "$HERMES_HOME" "$CODEX_HOME"
chmod 700 "$HERMES_HOME" "$CODEX_HOME" 2>/dev/null || true

if [[ -n "${CODEX_AUTH_JSON_B64:-}" && ! -f "$CODEX_AUTH_FILE" ]]; then
  tmp_auth="$(mktemp)"
  if ! printf '%s' "$CODEX_AUTH_JSON_B64" | base64 -d > "$tmp_auth"; then
    rm -f "$tmp_auth"
    echo "invalid_env=CODEX_AUTH_JSON_B64" >&2
    exit 1
  fi
  if ! node -e 'JSON.parse(require("fs").readFileSync(process.argv[1], "utf8"))' "$tmp_auth"; then
    rm -f "$tmp_auth"
    echo "invalid_json=CODEX_AUTH_JSON_B64" >&2
    exit 1
  fi
  install -m 600 "$tmp_auth" "$CODEX_AUTH_FILE"
  rm -f "$tmp_auth"
fi

cat > "$HERMES_HOME/config.yaml" <<YAML
model:
  provider: ${WORKBENCH_HERMES_PROVIDER}
  default: ${WORKBENCH_HERMES_MODEL}
agent:
  reasoning_effort: xhigh
mcp_servers:
  priori_tactical:
    command: /usr/local/bin/python
    args:
      - -m
      - tqe.workshop.mcp_server
    env:
      PYTHONPATH: /app/src
      TQE_WORKSHOP_OUTPUT_ROOT: ${TQE_RUNTIME_ROOT}
      TQE_DATA_ROOT: ${TQE_DATA_ROOT}
      TQE_RAW_ROOT: ${TQE_RAW_ROOT}
      TQE_RUNTIME_ROOT: ${TQE_RUNTIME_ROOT}
      TQE_CACHE_ROOT: ${TQE_CACHE_ROOT}
      TQE_KNOWLEDGE_PACK_PATH: ${TQE_KNOWLEDGE_PACK_PATH}
    timeout: 120
    connect_timeout: 30
    supports_parallel_tool_calls: false
    tools:
      include:
        - list_capabilities
        - search_recipes
        - describe_capability
        - submit_query_plan
        - validate_query_plan
        - inspect_result
        - inspect_non_match
        - retrieve_replay_window
      resources: false
      prompts: false
YAML

python_bin="$WORKBENCH_HERMES_PYTHON"
if [[ ! -x "$python_bin" ]]; then
  python_bin="$(command -v python3 || true)"
fi

if [[ -n "$python_bin" ]]; then
  "$python_bin" - <<'PY'
import json
import os
import tempfile
from datetime import datetime, timezone

auth_path = os.path.join(os.environ["HERMES_HOME"], "auth.json")
codex_auth_path = os.environ.get("CODEX_AUTH_FILE", "")

def load_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            value = json.load(fh)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}

auth_store = load_json(auth_path)
providers = auth_store.get("providers")
if not isinstance(providers, dict):
    providers = {}

state = providers.get("openai-codex")
tokens = state.get("tokens") if isinstance(state, dict) else None
if isinstance(tokens, dict) and tokens.get("access_token") and tokens.get("refresh_token"):
    print("hermes_codex_auth_status=present")
    raise SystemExit(0)

codex_auth = load_json(codex_auth_path)
codex_tokens = codex_auth.get("tokens")
if not isinstance(codex_tokens, dict):
    print("hermes_codex_auth_status=missing")
    raise SystemExit(0)

access_token = codex_tokens.get("access_token")
refresh_token = codex_tokens.get("refresh_token")
if not access_token or not refresh_token:
    print("hermes_codex_auth_status=missing")
    raise SystemExit(0)

providers["openai-codex"] = {
    "tokens": {
        "access_token": access_token,
        "refresh_token": refresh_token,
    },
    "last_refresh": codex_auth.get("last_refresh")
    or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "auth_mode": codex_auth.get("auth_mode") or "chatgpt",
}
auth_store["providers"] = providers
auth_store["active_provider"] = "openai-codex"

os.makedirs(os.path.dirname(auth_path), exist_ok=True)
fd, tmp_path = tempfile.mkstemp(prefix=".auth.", suffix=".json", dir=os.path.dirname(auth_path))
try:
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(auth_store, fh, indent=2)
        fh.write("\n")
    os.chmod(tmp_path, 0o600)
    os.replace(tmp_path, auth_path)
finally:
    try:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    except OSError:
        pass

print("hermes_codex_auth_status=imported_from_codex_home")
PY
fi

if command -v hermes >/dev/null 2>&1; then
  echo "hermes_binary_status=present"
  hermes --version 2>/dev/null | sed 's/^/hermes_version=/' || true
else
  echo "hermes_binary_status=missing"
fi

if [[ -f "$CODEX_AUTH_FILE" ]]; then
  echo "codex_auth_status=present"
else
  echo "codex_auth_status=missing"
fi

if [[ -f "$HERMES_HOME/auth.json" ]]; then
  echo "hermes_auth_status=present"
else
  echo "hermes_auth_status=missing"
fi
