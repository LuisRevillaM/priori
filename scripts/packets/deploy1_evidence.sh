#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

SCRIPT_PATH="scripts/packets/deploy1_evidence.sh"
SCRIPT_SHA="$(shasum -a 256 "$SCRIPT_PATH" | awk '{print $1}')"
STAMP="$(date -u +"%Y-%m-%dT%H%M%SZ0000")"
EVIDENCE_ROOT="delivery/packets/deploy-1-evidence/runs"
RUN_DIR=""
for i in $(seq 0 9999); do
  candidate="$EVIDENCE_ROOT/${STAMP}$(printf "%04d" "$i")-${SCRIPT_SHA:0:12}"
  if [[ ! -e "$candidate" ]]; then
    RUN_DIR="$candidate"
    mkdir -p "$RUN_DIR"
    break
  fi
done
if [[ -z "$RUN_DIR" ]]; then
  echo "could not allocate DEPLOY-1 evidence run dir" >&2
  exit 1
fi

DEMO_TOKEN="${DEMO_TOKEN:-deploy1-local-demo-token}"
PORT="${PORT:-18765}"
BASE_URL="http://127.0.0.1:${PORT}"
PYTHON="${PYTHON:-.venv/bin/python}"
SERVICE_PID=""
export TMPDIR=/private/tmp
export PYTHONPATH=src

cleanup() {
  if [[ -n "${SERVICE_PID}" ]]; then
    kill "$SERVICE_PID" >/dev/null 2>&1 || true
    wait "$SERVICE_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

millis() {
  "$PYTHON" - <<'PY'
import time
print(int(time.time() * 1000))
PY
}

run_logged() {
  local name="$1"
  local timeout_seconds="$2"
  shift 2
  local output_path="$RUN_DIR/${name}.txt"
  local start_ms
  local end_ms
  start_ms="$(millis)"
  set +e
  "$@" >"$output_path" 2>&1
  local rc=$?
  set -e
  end_ms="$(millis)"
  "$PYTHON" - "$RUN_DIR/${name}.status.json" "$rc" "$start_ms" "$end_ms" "$output_path" "$timeout_seconds" "$@" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
rc = int(sys.argv[2])
start_ms = int(sys.argv[3])
end_ms = int(sys.argv[4])
output_path = sys.argv[5]
timeout_seconds = int(sys.argv[6])
command = sys.argv[7:]
duration = end_ms - start_ms
path.write_text(json.dumps({
    "command": command,
    "return_code": rc,
    "status": "PASS" if rc == 0 else "FAIL",
    "duration_ms": duration,
    "flagged_over_5_minutes": duration > 300000,
    "timeout_seconds": timeout_seconds,
    "output_path": output_path,
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  return "$rc"
}

set +e
run_logged focused-python-tests 240 \
  "$PYTHON" -m unittest -v tests.test_deploy1_public_mode
FOCUSED_RC=$?
set -e

mkdir -p "$RUN_DIR/service-output-root" "$RUN_DIR/service-cache"
HOST=127.0.0.1 \
PORT="$PORT" \
TQE_PUBLIC_MODE=1 \
DEMO_ACCESS_TOKEN="$DEMO_TOKEN" \
WORKBENCH_HERMES_ENABLED=1 \
WORKBENCH_PREWARM_FILM_ROOM=1 \
TQE_RUNTIME_ROOT="$RUN_DIR/service-output-root" \
TQE_CACHE_ROOT="$RUN_DIR/service-cache" \
TQE_NODE_CACHE_ROOT="$RUN_DIR/service-cache/node-output" \
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes-priori}" \
WORKBENCH_HERMES_PROVIDER="${WORKBENCH_HERMES_PROVIDER:-openai-codex}" \
WORKBENCH_HERMES_MODEL="${WORKBENCH_HERMES_MODEL:-gpt-5.5}" \
"$PYTHON" -m tqe.workshop.app_service \
  --host 127.0.0.1 \
  --port "$PORT" \
  --static-root apps/workbench-alpha/dist \
  --output-root "$RUN_DIR/service-output-root" \
  >"$RUN_DIR/local-public-service.log" 2>&1 &
SERVICE_PID=$!

HEALTH_STATUS="FAIL"
HEALTH_ATTEMPTS=0
HEALTH_LAST_ERROR=""
for _ in $(seq 1 120); do
  HEALTH_ATTEMPTS=$((HEALTH_ATTEMPTS + 1))
  set +e
  "$PYTHON" - "$BASE_URL/healthz" <<'PY' >/tmp/deploy1-health.txt 2>&1
import sys
import urllib.request
with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
    raise SystemExit(0 if response.status == 200 else 1)
PY
  rc=$?
  HEALTH_LAST_ERROR="$(cat /tmp/deploy1-health.txt)"
  set -e
  if [[ "$rc" == "0" ]]; then
    HEALTH_STATUS="PASS"
    break
  fi
  sleep 0.25
done

WITHOUT_RC=1
WITH_RC=1
if [[ "$HEALTH_STATUS" == "PASS" ]]; then
  set +e
  run_logged oracle-without-token 900 "$PYTHON" delivery/oracles/DEPLOY-1/deploy_smoke.py --base-url "$BASE_URL"
  WITHOUT_RC=$?
  run_logged oracle-with-token 900 "$PYTHON" delivery/oracles/DEPLOY-1/deploy_smoke.py --base-url "$BASE_URL" --demo-token "$DEMO_TOKEN"
  WITH_RC=$?
  set -e
fi

"$PYTHON" - "$RUN_DIR" "$SCRIPT_PATH" "$SCRIPT_SHA" "$BASE_URL" "$HEALTH_STATUS" "$HEALTH_ATTEMPTS" "$HEALTH_LAST_ERROR" "$FOCUSED_RC" "$WITHOUT_RC" "$WITH_RC" <<'PY'
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
script_path = sys.argv[2]
script_sha = sys.argv[3]
base_url = sys.argv[4]
health_status = sys.argv[5]
health_attempts = int(sys.argv[6])
health_last_error = sys.argv[7]
focused_rc = int(sys.argv[8])
without_rc = int(sys.argv[9])
with_rc = int(sys.argv[10])
root = Path.cwd()

def rel(path: Path) -> str:
    return path.resolve().relative_to(root).as_posix()

def git(*args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=root, check=False, capture_output=True, text=True)
    return completed.stdout.strip() if completed.returncode == 0 and completed.stdout.strip() else "unknown"

def read_status(name: str, fallback: dict) -> dict:
    path = run_dir / f"{name}.status.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["output_path"] = rel(Path(payload["output_path"]))
        return payload
    return fallback

focused = read_status("focused-python-tests", {"status": "FAIL", "return_code": focused_rc})
without = read_status("oracle-without-token", {
    "status": "FAIL",
    "return_code": without_rc,
    "reason": "service_health_failed",
})
with_token = read_status("oracle-with-token", {
    "status": "FAIL",
    "return_code": with_rc,
    "reason": "service_health_failed",
})
without["demo_token_supplied"] = False
without["subscription_billed"] = False
without["billing_surface"] = "No live model call expected; public gate must answer before Hermes."
with_token["demo_token_supplied"] = True
with_token["subscription_billed"] = True
with_token["billing_surface"] = "ChatGPT subscription via openai-codex Hermes CLI for the oracle live ask"

payload = {
    "schema_version": "deploy1.evidence.v1",
    "status": "PASS" if focused["status"] == "PASS" and health_status == "PASS" and without["status"] == "PASS" and with_token["status"] == "PASS" else "FAIL",
    "evidence_metadata": {
        "schema_version": "deploy1.evidence_metadata.v1",
        "produced_by": script_path,
        "producing_script_sha256": script_sha,
        "run_started_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "git_branch": git("branch", "--show-current"),
        "git_commit": git("rev-parse", "HEAD"),
        "git_tree": git("rev-parse", "HEAD^{tree}"),
        "run_dir": rel(run_dir),
        "oracle_path": "delivery/oracles/DEPLOY-1/deploy_smoke.py",
        "oracle_sha256": subprocess.check_output(["shasum", "-a", "256", "delivery/oracles/DEPLOY-1/deploy_smoke.py"], text=True).split()[0],
    },
    "focused_python_tests": focused,
    "local_public_mode_oracles": {
        "base_url": base_url,
        "service_log": rel(run_dir / "local-public-service.log"),
        "output_root": rel(run_dir / "service-output-root"),
        "cache_root": rel(run_dir / "service-cache"),
        "health": {
            "status": health_status,
            "attempts": health_attempts,
            "last_error": health_last_error,
        },
        "oracle_without_token": without,
        "oracle_with_token": with_token,
        "cache_provenance": "The local public-mode service used run-local TQE_RUNTIME_ROOT, TQE_CACHE_ROOT, and TQE_NODE_CACHE_ROOT under this evidence directory. The with-token oracle may invoke Hermes live through the ChatGPT subscription; the without-token oracle must be answered by the public gate before any model call.",
    },
}
(run_dir / "deploy1-evidence.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
lines = [
    "<!-- evidence_metadata: " + json.dumps(payload["evidence_metadata"], sort_keys=True, separators=(",", ":")) + " -->",
    "# DEPLOY-1 Evidence",
    "",
    "| Area | Status | Duration ms | Output |",
    "| --- | --- | ---: | --- |",
    f"| DEPLOY-1 Python | {focused.get('status')} | {focused.get('duration_ms', '')} | `{focused.get('output_path', '')}` |",
    "",
    "| Oracle mode | Status | Duration ms | Output | Subscription billed |",
    "| --- | --- | ---: | --- | --- |",
    f"| without token | {without.get('status')} | {without.get('duration_ms', '')} | `{without.get('output_path', '')}` | {without.get('subscription_billed')} |",
    f"| with token | {with_token.get('status')} | {with_token.get('duration_ms', '')} | `{with_token.get('output_path', '')}` | {with_token.get('subscription_billed')} |",
    "",
    f"Service log: `{payload['local_public_mode_oracles']['service_log']}`",
    "",
]
(run_dir / "deploy1-evidence.md").write_text("\n".join(lines), encoding="utf-8")
print(json.dumps({"run_dir": rel(run_dir), "status": payload["status"]}, indent=2, sort_keys=True))
raise SystemExit(0 if payload["status"] == "PASS" else 1)
PY
