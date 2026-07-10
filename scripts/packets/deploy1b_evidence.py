#!/usr/bin/env python3
"""Produce immutable DEPLOY-1B Render inventory and live-oracle evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(__file__).resolve()
ORACLE_PATH = ROOT / "delivery/oracles/DEPLOY-1/deploy_smoke.py"
EVIDENCE_ROOT = ROOT / "delivery/packets/deploy-1b-evidence/runs"
API_BASE = "https://api.render.com/v1"
SAFE_ENV_VALUES = {
    "TQE_DATA_ROOT",
    "TQE_RAW_ROOT",
    "TQE_RUNTIME_ROOT",
    "TQE_CACHE_ROOT",
    "TQE_NODE_CACHE_ROOT",
    "TQE_EXECUTION_WORKERS",
    "TQE_PUBLIC_MODE",
    "WORKBENCH_HERMES_ENABLED",
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_value(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, check=False, capture_output=True, text=True, timeout=20
    )
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def require_committed_clean_script() -> None:
    relative = SCRIPT_PATH.relative_to(ROOT).as_posix()
    committed = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        timeout=20,
    )
    if committed.returncode != 0:
        raise SystemExit(f"evidence producer is not committed at HEAD: {relative}")
    if hashlib.sha256(committed.stdout).hexdigest() != file_sha256(SCRIPT_PATH):
        raise SystemExit(f"evidence producer differs from committed HEAD: {relative}")
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    ).stdout.strip()
    if dirty:
        raise SystemExit("tracked tree is dirty; commit before producing DEPLOY-1B evidence")


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def make_run_dir(script_sha: str) -> Path:
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().strftime("%Y-%m-%dT%H%M%SZ0000")
    for index in range(10_000):
        candidate = EVIDENCE_ROOT / f"{stamp}{index:04d}-{script_sha[:12]}"
        if not candidate.exists():
            candidate.mkdir(parents=True)
            return candidate
    raise RuntimeError("could not allocate a unique DEPLOY-1B evidence directory")


def write_json_once(path: Path, payload: Any) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence: {path}")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text_once(path: Path, payload: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence: {path}")
    path.write_text(payload, encoding="utf-8")


def render_get(api_key: str, path: str, params: dict[str, Any] | None = None) -> Any:
    query = urllib.parse.urlencode(
        {key: str(value) for key, value in (params or {}).items() if value is not None}
    )
    url = f"{API_BASE}{path}" + (f"?{query}" if query else "")
    curl_config = (
        f'header = "Authorization: Bearer {api_key}"\n'
        'header = "Accept: application/json"\n'
    )
    completed = subprocess.run(
        ["curl", "--fail-with-body", "--silent", "--show-error", "--config", "-", url],
        input=curl_config,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Render API GET failed for {path}: {completed.stderr.strip()}")
    return json.loads(completed.stdout)


def render_list(api_key: str, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        page_params = {**params, "limit": 100, "cursor": cursor}
        page = render_get(api_key, path, page_params)
        if not isinstance(page, list):
            raise RuntimeError(f"Render API list returned non-list for {path}")
        rows.extend(row for row in page if isinstance(row, dict))
        if len(page) < 100:
            return rows
        cursor = str(page[-1].get("cursor") or "")
        if not cursor:
            return rows


def sanitize_service(wrapper: dict[str, Any]) -> dict[str, Any]:
    service = wrapper.get("service") if isinstance(wrapper.get("service"), dict) else wrapper
    details = service.get("serviceDetails") if isinstance(service.get("serviceDetails"), dict) else {}
    disk = details.get("disk") if isinstance(details.get("disk"), dict) else None
    return {
        "id": service.get("id"),
        "name": service.get("name"),
        "type": service.get("type"),
        "repo": service.get("repo"),
        "branch": service.get("branch"),
        "auto_deploy": service.get("autoDeploy"),
        "suspended": service.get("suspended"),
        "updated_at": service.get("updatedAt"),
        "plan": details.get("plan"),
        "region": details.get("region"),
        "runtime": details.get("runtime"),
        "url": details.get("url"),
        "health_check_path": details.get("healthCheckPath"),
        "disk": (
            {
                key: disk.get(key)
                for key in ("id", "name", "sizeGB", "mountPath")
            }
            if disk
            else None
        ),
    }


def sanitize_disk(wrapper: dict[str, Any]) -> dict[str, Any]:
    disk = wrapper.get("disk") if isinstance(wrapper.get("disk"), dict) else wrapper
    return {
        key: disk.get(key)
        for key in ("id", "name", "sizeGB", "mountPath", "serviceId", "createdAt", "updatedAt")
    }


def sanitize_env_group(wrapper: dict[str, Any]) -> dict[str, Any]:
    group = wrapper.get("envGroup") if isinstance(wrapper.get("envGroup"), dict) else wrapper
    return {key: group.get(key) for key in ("id", "name", "ownerId", "createdAt", "updatedAt")}


def sanitize_env_vars(rows: Any) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for wrapper in rows if isinstance(rows, list) else []:
        env_var = wrapper.get("envVar") if isinstance(wrapper.get("envVar"), dict) else wrapper
        key = str(env_var.get("key") or "")
        value = str(env_var.get("value") or "")
        record: dict[str, Any] = {"key": key, "configured": bool(value)}
        if key in SAFE_ENV_VALUES:
            record["value"] = value
        sanitized.append(record)
    return sorted(sanitized, key=lambda row: str(row["key"]))


def collect_render_evidence(
    *, api_key: str, owner_id: str, service_id: str, deploy_id: str
) -> dict[str, Any]:
    services_raw = render_list(
        api_key, "/services", {"ownerId": owner_id, "includePreviews": "true"}
    )
    disks_raw = render_list(api_key, "/disks", {"ownerId": owner_id})
    groups_raw = render_list(api_key, "/env-groups", {"ownerId": owner_id})
    service = sanitize_service(render_get(api_key, f"/services/{service_id}"))
    deploy = render_get(api_key, f"/services/{service_id}/deploys/{deploy_id}")
    env_vars = sanitize_env_vars(render_get(api_key, f"/services/{service_id}/env-vars"))
    created_at = str(deploy.get("createdAt") or utc_now().isoformat())
    logs_payload = render_get(
        api_key,
        "/logs",
        {
            "ownerId": owner_id,
            "resource": service_id,
            "type": "app",
            "direction": "forward",
            "limit": 200,
            "startTime": created_at,
            "endTime": utc_now().isoformat(),
        },
    )
    relevant_needles = (
        "Demo data",
        "Film Room prewarm",
        "Prewarming Film Room flagship",
        "Prewarmed Film Room flagship",
        "Out of memory",
        "Your service is live",
        "Available at your primary URL",
    )
    relevant_logs = []
    for row in logs_payload.get("logs", []) if isinstance(logs_payload, dict) else []:
        message = str(row.get("message") or "")
        if any(needle in message for needle in relevant_needles):
            relevant_logs.append({"timestamp": row.get("timestamp"), "message": message})
    services = [sanitize_service(row) for row in services_raw]
    disks = [sanitize_disk(row) for row in disks_raw]
    env_groups = [sanitize_env_group(row) for row in groups_raw]
    return {
        "inventory": {
            "service_count": len(services),
            "disk_count": len(disks),
            "disk_total_size_gb": sum(int(row.get("sizeGB") or 0) for row in disks),
            "env_group_count": len(env_groups),
            "services": services,
            "disks": disks,
            "env_groups": env_groups,
        },
        "target_service": service,
        "target_env_vars": env_vars,
        "deploy": {
            key: deploy.get(key)
            for key in ("id", "status", "trigger", "createdAt", "updatedAt", "startedAt", "finishedAt")
        }
        | {"commit_id": (deploy.get("commit") or {}).get("id")},
        "relevant_logs": relevant_logs,
    }


def run_oracle(run_dir: Path, base_url: str) -> dict[str, Any]:
    command = [sys.executable, str(ORACLE_PATH), "--base-url", base_url]
    started = utc_now()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=900,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        return_code = completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + "\nORACLE TIMEOUT\n"
        return_code = 124
        timed_out = True
    output = stdout + stderr
    output_path = run_dir / "oracle-without-token.txt"
    write_text_once(output_path, output)
    return {
        "command": command,
        "base_url": base_url,
        "demo_token_supplied": False,
        "started_at": started.replace(microsecond=0).isoformat(),
        "duration_ms": round((utc_now() - started).total_seconds() * 1000, 3),
        "return_code": return_code,
        "timed_out": timed_out,
        "status": "PASS" if return_code == 0 else "FAIL",
        "output_path": output_path.relative_to(ROOT).as_posix(),
    }


def evaluate(render: dict[str, Any], oracle: dict[str, Any]) -> dict[str, str]:
    logs = [str(row.get("message") or "") for row in render.get("relevant_logs", [])]
    env = {str(row.get("key")): row for row in render.get("target_env_vars", [])}
    provisioning_ok = any(
        message in {"Demo data already satisfies manifest.", "Demo data provisioned and verified."}
        for message in logs
    )
    prewarmed = [message for message in logs if message.startswith("Prewarmed Film Room flagship ")]
    prewarm_ok = len(prewarmed) >= 2 and not any("skipped missing plan" in message for message in logs)
    expected_env = {
        "TQE_PUBLIC_MODE": "1",
        "WORKBENCH_HERMES_ENABLED": "0",
        "TQE_EXECUTION_WORKERS": "4",
        "TQE_NODE_CACHE_ROOT": "/var/data/cache/node-output",
    }
    config_ok = all(env.get(key, {}).get("value") == value for key, value in expected_env.items())
    config_ok = config_ok and bool(env.get("DEMO_ACCESS_TOKEN", {}).get("configured"))
    service = render.get("target_service", {})
    config_ok = config_ok and service.get("name") == "entrelineas-film-room"
    return {
        "render_deploy": "PASS" if render.get("deploy", {}).get("status") == "live" else "FAIL",
        "required_configuration": "PASS" if config_ok else "FAIL",
        "data_provisioning": "PASS" if provisioning_ok else "FAIL",
        "flagship_prewarm": "PASS" if prewarm_ok else "FAIL",
        "fenced_oracle": oracle["status"],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    metadata = payload["evidence_metadata"]
    rows = [
        "<!-- evidence_metadata: "
        + json.dumps(metadata, sort_keys=True, separators=(",", ":"))
        + " -->",
        "# DEPLOY-1B Evidence",
        "",
        f"Live URL: `{payload['oracle']['base_url']}`",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    rows.extend(f"| {name} | {status} |" for name, status in payload["checks"].items())
    rows.extend(
        [
            "",
            f"Services enumerated: {payload['render']['inventory']['service_count']}",
            f"Disks enumerated: {payload['render']['inventory']['disk_count']}",
            f"Environment groups enumerated: {payload['render']['inventory']['env_group_count']}",
            "",
            f"Oracle output: `{payload['oracle']['output_path']}`",
            "",
        ]
    )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--owner-id", required=True)
    parser.add_argument("--service-id", required=True)
    parser.add_argument("--deploy-id", required=True)
    args = parser.parse_args(argv)
    api_key = os.environ.get("RENDER_API_KEY", "")
    if not api_key:
        raise SystemExit("RENDER_API_KEY is not set")
    require_committed_clean_script()
    script_sha = file_sha256(SCRIPT_PATH)
    run_dir = make_run_dir(script_sha)
    render = collect_render_evidence(
        api_key=api_key,
        owner_id=args.owner_id,
        service_id=args.service_id,
        deploy_id=args.deploy_id,
    )
    oracle = run_oracle(run_dir, args.base_url.rstrip("/"))
    checks = evaluate(render, oracle)
    status = "PASS" if all(value == "PASS" for value in checks.values()) else "FAIL"
    payload = {
        "schema_version": "deploy1b.evidence.v1",
        "status": status,
        "evidence_metadata": {
            "schema_version": "deploy1b.evidence_metadata.v1",
            "produced_by": SCRIPT_PATH.relative_to(ROOT).as_posix(),
            "producing_script_sha256": script_sha,
            "run_started_at": utc_now().replace(microsecond=0).isoformat(),
            "git_branch": git_value("branch", "--show-current"),
            "git_commit": git_value("rev-parse", "HEAD"),
            "git_tree": git_value("rev-parse", "HEAD^{tree}"),
            "run_dir": run_dir.relative_to(ROOT).as_posix(),
            "oracle_path": ORACLE_PATH.relative_to(ROOT).as_posix(),
            "oracle_sha256": file_sha256(ORACLE_PATH),
        },
        "checks": checks,
        "render": render,
        "oracle": oracle,
    }
    write_json_once(run_dir / "deploy1b-evidence.json", payload)
    write_text_once(run_dir / "deploy1b-evidence.md", render_markdown(payload))
    print(json.dumps({"run_dir": run_dir.relative_to(ROOT).as_posix(), "status": status}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
