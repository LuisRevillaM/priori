#!/usr/bin/env python3
"""DEPLOY-1 R-AZ evidence producer."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import http.client
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
EVIDENCE_ROOT = ROOT / "delivery/packets/deploy-1-evidence/runs"
ORACLE = ROOT / "delivery/oracles/DEPLOY-1/deploy_smoke.py"
FOCUSED_TESTS = ["tests.test_deploy1_public_mode"]


def utc_stamp() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H%M%SZ0000")


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_value(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return completed.stdout.strip() if completed.returncode == 0 and completed.stdout.strip() else "unknown"


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def write_json_once(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text_once(path: Path, text: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_run_dir(script_sha: str) -> Path:
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    timestamp = utc_stamp()
    for index in range(10_000):
        candidate = EVIDENCE_ROOT / f"{timestamp}{index:04d}-{script_sha[:12]}"
        if not candidate.exists():
            candidate.mkdir(parents=True)
            return candidate
    raise RuntimeError("could not allocate unique DEPLOY-1 evidence directory")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(port: int, *, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    attempts = 0
    last_error = ""
    while time.monotonic() < deadline:
        attempts += 1
        try:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            connection.request("GET", "/healthz")
            response = connection.getresponse()
            response.read()
            connection.close()
            if response.status == 200:
                return {"status": "PASS", "attempts": attempts}
            last_error = f"HTTP {response.status}"
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(0.25)
    return {"status": "FAIL", "attempts": attempts, "last_error": last_error}


def run_command(args: list[str], *, output_path: Path, timeout: int, env: dict[str, str] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
    write_text_once(output_path, completed.stdout + completed.stderr)
    return {
        "command": args,
        "return_code": completed.returncode,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "duration_ms": duration_ms,
        "flagged_over_5_minutes": duration_ms > 300_000,
        "output_path": relative(output_path),
    }


def run_focused_tests(run_dir: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    return run_command(
        [sys.executable, "-m", "unittest", "-v", *FOCUSED_TESTS],
        output_path=run_dir / "focused-python-tests.txt",
        timeout=240,
        env=env,
    )


def run_oracle(run_dir: Path, *, base_url: str, demo_token: str | None) -> dict[str, Any]:
    args = [sys.executable, str(ORACLE), "--base-url", base_url]
    output_path = run_dir / ("oracle-with-token.txt" if demo_token else "oracle-without-token.txt")
    if demo_token:
        args.extend(["--demo-token", demo_token])
    record = run_command(args, output_path=output_path, timeout=900)
    record["demo_token_supplied"] = bool(demo_token)
    if demo_token:
        record["subscription_billed"] = True
        record["billing_surface"] = "ChatGPT subscription via openai-codex Hermes CLI for the oracle live ask"
    else:
        record["subscription_billed"] = False
        record["billing_surface"] = "No live model call expected; public gate must answer before Hermes."
    return record


def run_local_public_service_oracles(run_dir: Path, *, demo_token: str) -> dict[str, Any]:
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    output_root = run_dir / "service-output-root"
    cache_root = run_dir / "service-cache"
    output_root.mkdir()
    cache_root.mkdir()
    env = dict(os.environ)
    env.update(
        {
            "PYTHONPATH": str(SRC),
            "HOST": "127.0.0.1",
            "PORT": str(port),
            "TQE_PUBLIC_MODE": "1",
            "DEMO_ACCESS_TOKEN": demo_token,
            "WORKBENCH_HERMES_ENABLED": "1",
            "WORKBENCH_PREWARM_FILM_ROOM": "1",
            "TQE_RUNTIME_ROOT": str(output_root),
            "TQE_CACHE_ROOT": str(cache_root),
            "TQE_NODE_CACHE_ROOT": str(cache_root / "node-output"),
            "HERMES_HOME": os.environ.get("HERMES_HOME", str(Path.home() / ".hermes-priori")),
            "WORKBENCH_HERMES_PROVIDER": os.environ.get("WORKBENCH_HERMES_PROVIDER", "openai-codex"),
            "WORKBENCH_HERMES_MODEL": os.environ.get("WORKBENCH_HERMES_MODEL", "gpt-5.5"),
        }
    )
    service_log = run_dir / "local-public-service.log"
    with service_log.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "tqe.workshop.app_service",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--static-root",
                "apps/workbench-alpha/dist",
                "--output-root",
                str(output_root),
            ],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            health = wait_for_health(port, timeout_seconds=30)
            without_token = run_oracle(run_dir, base_url=base_url, demo_token=None) if health["status"] == "PASS" else {
                "status": "FAIL",
                "reason": "service_health_failed",
            }
            with_token = run_oracle(run_dir, base_url=base_url, demo_token=demo_token) if health["status"] == "PASS" else {
                "status": "FAIL",
                "reason": "service_health_failed",
            }
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    return {
        "base_url": base_url,
        "service_log": relative(service_log),
        "output_root": relative(output_root),
        "cache_root": relative(cache_root),
        "health": health,
        "oracle_without_token": without_token,
        "oracle_with_token": with_token,
        "cache_provenance": (
            "The local public-mode service used run-local TQE_RUNTIME_ROOT, TQE_CACHE_ROOT, and "
            "TQE_NODE_CACHE_ROOT under this evidence directory. The with-token oracle may invoke "
            "Hermes live through the ChatGPT subscription; the without-token oracle must be answered "
            "by the public gate before any model call."
        ),
    }


def metadata(script_path: Path, script_sha: str, run_dir: Path) -> dict[str, Any]:
    return {
        "schema_version": "deploy1.evidence_metadata.v1",
        "produced_by": relative(script_path),
        "producing_script_sha256": script_sha,
        "run_started_at": utc_now(),
        "git_branch": git_value("branch", "--show-current"),
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_tree": git_value("rev-parse", "HEAD^{tree}"),
        "run_dir": relative(run_dir),
        "oracle_path": relative(ORACLE),
        "oracle_sha256": file_sha256(ORACLE),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    local = payload["local_public_mode_oracles"]
    return "\n".join(
        [
            "<!-- evidence_metadata: "
            + json.dumps(payload["evidence_metadata"], sort_keys=True, separators=(",", ":"))
            + " -->",
            "# DEPLOY-1 Evidence",
            "",
            "## Focused Tests",
            "",
            "| Area | Status | Duration ms | Output |",
            "| --- | --- | ---: | --- |",
            f"| DEPLOY-1 Python | {payload['focused_python_tests']['status']} | {payload['focused_python_tests']['duration_ms']} | `{payload['focused_python_tests']['output_path']}` |",
            "",
            "## Local Public-Mode Oracle",
            "",
            "| Mode | Status | Duration ms | Output | Subscription billed |",
            "| --- | --- | ---: | --- | --- |",
            f"| without token | {local['oracle_without_token']['status']} | {local['oracle_without_token'].get('duration_ms', '')} | `{local['oracle_without_token'].get('output_path', '')}` | {local['oracle_without_token'].get('subscription_billed', False)} |",
            f"| with token | {local['oracle_with_token']['status']} | {local['oracle_with_token'].get('duration_ms', '')} | `{local['oracle_with_token'].get('output_path', '')}` | {local['oracle_with_token'].get('subscription_billed', True)} |",
            "",
            f"Service log: `{local['service_log']}`",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo-token", default="deploy1-local-demo-token")
    args = parser.parse_args(argv)
    script_path = Path(__file__).resolve()
    script_sha = file_sha256(script_path)
    run_dir = make_run_dir(script_sha)
    payload = {
        "schema_version": "deploy1.evidence.v1",
        "evidence_metadata": metadata(script_path, script_sha, run_dir),
        "focused_python_tests": run_focused_tests(run_dir),
        "local_public_mode_oracles": run_local_public_service_oracles(run_dir, demo_token=args.demo_token),
    }
    oracle_records = payload["local_public_mode_oracles"]
    status = "PASS" if (
        payload["focused_python_tests"]["status"] == "PASS"
        and oracle_records["health"]["status"] == "PASS"
        and oracle_records["oracle_without_token"]["status"] == "PASS"
        and oracle_records["oracle_with_token"]["status"] == "PASS"
    ) else "FAIL"
    payload["status"] = status
    write_json_once(run_dir / "deploy1-evidence.json", payload)
    write_text_once(run_dir / "deploy1-evidence.md", render_markdown(payload))
    print(json.dumps({"run_dir": relative(run_dir), "status": status}, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
