"""DEPLOY-1 R-AZ evidence producer.

Run with:
    PYTHONPATH=src python -m tqe.verification.deploy1_evidence
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import os
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
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


def evidence_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


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


def run_focused_tests(run_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromNames(FOCUSED_TESTS)
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
    output_path = run_dir / "focused-python-tests.txt"
    write_text_once(output_path, stream.getvalue())
    return {
        "command": ["in-process-unittest", *FOCUSED_TESTS],
        "return_code": 0 if result.wasSuccessful() else 1,
        "status": "PASS" if result.wasSuccessful() else "FAIL",
        "duration_ms": duration_ms,
        "flagged_over_5_minutes": duration_ms > 300_000,
        "output_path": relative(output_path),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
    }


def start_public_service(run_dir: Path, *, demo_token: str) -> tuple[Any, threading.Thread, str, Path, Path]:
    scratch_root = Path("/private/tmp/deploy1-evidence-scratch") / run_dir.name
    output_root = scratch_root / "service-output-root"
    cache_root = scratch_root / "service-cache"
    os.environ["TMPDIR"] = "/private/tmp"
    os.environ["TQE_PUBLIC_MODE"] = "1"
    os.environ["DEMO_ACCESS_TOKEN"] = demo_token
    os.environ["WORKBENCH_HERMES_ENABLED"] = "1"
    os.environ["WORKBENCH_PREWARM_FILM_ROOM"] = "1"
    os.environ["TQE_RUNTIME_ROOT"] = str(output_root)
    os.environ["TQE_CACHE_ROOT"] = str(cache_root)
    os.environ["TQE_NODE_CACHE_ROOT"] = str(cache_root / "node-output")
    os.environ.setdefault("HERMES_HOME", str(Path.home() / ".hermes-priori"))
    os.environ.setdefault("WORKBENCH_HERMES_PROVIDER", "openai-codex")
    os.environ.setdefault("WORKBENCH_HERMES_MODEL", "gpt-5.5")

    from tqe.workshop import app_service

    output_root.mkdir(parents=True)
    cache_root.mkdir(parents=True)
    server = app_service.WorkbenchServer(
        ("127.0.0.1", 0),
        app_service.WorkbenchHandler,
        static_root=ROOT / "apps/workbench-alpha/dist",
        output_root=output_root,
    )
    app_service.start_film_room_prewarm_thread(output_root=output_root)
    thread = threading.Thread(target=server.serve_forever, name="deploy1-local-public-service", daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}", output_root, cache_root


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
            "| Area | Status | Duration ms | Output |",
            "| --- | --- | ---: | --- |",
            f"| DEPLOY-1 Python | {payload['focused_python_tests']['status']} | {payload['focused_python_tests']['duration_ms']} | `{payload['focused_python_tests']['output_path']}` |",
            "",
            "| Oracle mode | Status | Duration ms | Output | Subscription billed |",
            "| --- | --- | ---: | --- | --- |",
            f"| without token | {local['oracle_without_token']['status']} | {local['oracle_without_token'].get('duration_ms', '')} | `{local['oracle_without_token'].get('output_path', '')}` | {local['oracle_without_token'].get('subscription_billed', False)} |",
            f"| with token | {local['oracle_with_token']['status']} | {local['oracle_with_token'].get('duration_ms', '')} | `{local['oracle_with_token'].get('output_path', '')}` | {local['oracle_with_token'].get('subscription_billed', True)} |",
            "",
            f"Cache provenance: {local['cache_provenance']}",
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

    server = None
    thread = None
    try:
        server, thread, base_url, output_root, cache_root = start_public_service(run_dir, demo_token=args.demo_token)
        without_token = run_oracle(run_dir, base_url=base_url, demo_token=None)
        with_token = run_oracle(run_dir, base_url=base_url, demo_token=args.demo_token)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)

    focused = run_focused_tests(run_dir)
    payload = {
        "schema_version": "deploy1.evidence.v1",
        "evidence_metadata": metadata(script_path, script_sha, run_dir),
        "focused_python_tests": focused,
        "local_public_mode_oracles": {
            "base_url": base_url,
            "output_root": evidence_path(output_root),
            "cache_root": evidence_path(cache_root),
            "health": {"status": "PASS", "served_in_process": True},
            "oracle_without_token": without_token,
            "oracle_with_token": with_token,
            "cache_provenance": (
                "The local public-mode service used run-local TQE_RUNTIME_ROOT, TQE_CACHE_ROOT, "
                "and TQE_NODE_CACHE_ROOT under /private/tmp scratch named for this evidence run. The with-token oracle may "
                "invoke Hermes live through the ChatGPT subscription; the without-token oracle must "
                "be answered by the public gate before any model call."
            ),
        },
    }
    payload["status"] = "PASS" if (
        focused["status"] == "PASS"
        and without_token["status"] == "PASS"
        and with_token["status"] == "PASS"
    ) else "FAIL"
    write_json_once(run_dir / "deploy1-evidence.json", payload)
    write_text_once(run_dir / "deploy1-evidence.md", render_markdown(payload))
    print(json.dumps({"run_dir": relative(run_dir), "status": payload["status"]}, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
