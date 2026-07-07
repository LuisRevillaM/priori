#!/usr/bin/env python3
"""SMOKE-1 R-AZ evidence producer."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tqe.workshop.app_service import film_room_ask_request  # noqa: E402

EVIDENCE_ROOT = ROOT / "delivery/packets/smoke-1-evidence/runs"
OWNER_ASK = "When the ball carrier is pressed and no support arrives, how often does his team keep the ball?"
PYTHON_FOCUSED_TESTS = [
    "tests.test_smoke1_honest_errors",
    "tests.test_scp2_2_hermes_nl",
]


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
    raise RuntimeError("could not allocate unique SMOKE-1 evidence directory")


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
        "output_path": relative(output_path),
    }


def run_python_focused_tests(run_dir: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    return run_command(
        [sys.executable, "-m", "unittest", "-v", *PYTHON_FOCUSED_TESTS],
        output_path=run_dir / "focused-python-tests.txt",
        timeout=240,
        env=env,
    )


def run_ui_error_tests(run_dir: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["TMPDIR"] = "/private/tmp"
    return run_command(
        ["npm", "--prefix", "apps/workbench-alpha", "run", "test:unit"],
        output_path=run_dir / "focused-ui-tests.txt",
        timeout=240,
        env=env,
    )


def compact_owner_response(response: dict[str, Any]) -> dict[str, Any]:
    refusal = response.get("refusal") if isinstance(response.get("refusal"), dict) else {}
    answer = response.get("answer") if isinstance(response.get("answer"), dict) else {}
    return {
        "ok": response.get("ok"),
        "outcome": response.get("outcome"),
        "provider": response.get("provider"),
        "model": response.get("model"),
        "has_answer": bool(answer),
        "has_refusal": bool(refusal),
        "refusal_gap": refusal.get("gap_code"),
        "refusal_missing_capability": refusal.get("missing_capability"),
        "synthesis_error": refusal.get("synthesis_error") if isinstance(refusal.get("synthesis_error"), dict) else None,
        "latency_ms": response.get("latency_ms"),
        "latency_breakdown_ms": response.get("latency_breakdown_ms"),
        "moment_total_count": answer.get("moment_total_count"),
    }


def run_owner_ask(run_dir: Path, *, attempts: int) -> dict[str, Any]:
    if attempts < 1 or attempts > 5:
        raise ValueError("owner ask attempts must be between 1 and 5")
    records: list[dict[str, Any]] = []
    for attempt in range(1, attempts + 1):
        output_root = run_dir / f"owner-ask-output-root-attempt-{attempt}"
        output_root.mkdir(parents=True, exist_ok=False)
        started = time.perf_counter()
        try:
            response = film_room_ask_request({"text": OWNER_ASK}, output_root=output_root)
            duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
            record = {
                "attempt": attempt,
                "status": "PASS",
                "subscription_billed": True,
                "billing_surface": "ChatGPT subscription via openai-codex Hermes CLI",
                "question": OWNER_ASK,
                "duration_ms": duration_ms,
                "output_root": relative(output_root),
                "response": compact_owner_response(response),
            }
            records.append(record)
            if response.get("ok") is True:
                break
        except Exception as exc:  # noqa: BLE001
            duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
            records.append(
                {
                    "attempt": attempt,
                    "status": "ERROR",
                    "subscription_billed": True,
                    "billing_surface": "ChatGPT subscription via openai-codex Hermes CLI",
                    "question": OWNER_ASK,
                    "duration_ms": duration_ms,
                    "output_root": relative(output_root),
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                    "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                }
            )
    return {
        "attempt_limit": attempts,
        "attempt_count": len(records),
        "records": records,
        "cache_provenance": (
            "Each owner-ask attempt uses a fresh run-local output_root under the evidence directory. "
            "No persistent execution-cache path is configured by this script; Hermes model calls remain live "
            "subscription-billed through openai-codex."
        ),
    }


def metadata(script_path: Path, script_sha: str, run_dir: Path) -> dict[str, Any]:
    return {
        "schema_version": "smoke1.evidence_metadata.v1",
        "produced_by": relative(script_path),
        "producing_script_sha256": script_sha,
        "run_started_at": utc_now(),
        "git_branch": git_value("branch", "--show-current"),
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_tree": git_value("rev-parse", "HEAD^{tree}"),
        "run_dir": relative(run_dir),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    owner = payload["owner_ask"]
    owner_rows = [
        "| Attempt | Status | Duration ms | Outcome | Gap |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for record in owner["records"]:
        response = record.get("response") if isinstance(record.get("response"), dict) else {}
        owner_rows.append(
            "| {attempt} | {status} | {duration} | {outcome} | {gap} |".format(
                attempt=record["attempt"],
                status=record["status"],
                duration=record["duration_ms"],
                outcome=response.get("outcome", record.get("exception_type", "")),
                gap=response.get("refusal_gap", record.get("exception_message", "")),
            )
        )
    return "\n".join(
        [
            "<!-- evidence_metadata: "
            + json.dumps(payload["evidence_metadata"], sort_keys=True, separators=(",", ":"))
            + " -->",
            "# SMOKE-1 Evidence",
            "",
            "## Focused Tests",
            "",
            "| Area | Status | Duration ms | Output |",
            "| --- | --- | ---: | --- |",
            f"| Python | {payload['focused_python_tests']['status']} | {payload['focused_python_tests']['duration_ms']} | `{payload['focused_python_tests']['output_path']}` |",
            f"| Film Room UI | {payload['focused_ui_tests']['status']} | {payload['focused_ui_tests']['duration_ms']} | `{payload['focused_ui_tests']['output_path']}` |",
            "",
            "## Owner Ask",
            "",
            *owner_rows,
            "",
            f"Billing: {owner['records'][0]['billing_surface'] if owner['records'] else 'not run'}",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-attempts", type=int, default=1, help="live owner-ask attempts, 1-5")
    args = parser.parse_args(argv)
    script_path = Path(__file__).resolve()
    script_sha = file_sha256(script_path)
    run_dir = make_run_dir(script_sha)
    payload = {
        "schema_version": "smoke1.evidence.v1",
        "evidence_metadata": metadata(script_path, script_sha, run_dir),
        "focused_python_tests": run_python_focused_tests(run_dir),
        "focused_ui_tests": run_ui_error_tests(run_dir),
        "owner_ask": run_owner_ask(run_dir, attempts=args.owner_attempts),
    }
    status = "PASS" if all(
        item["status"] == "PASS"
        for item in (payload["focused_python_tests"], payload["focused_ui_tests"])
    ) and payload["owner_ask"]["records"] and payload["owner_ask"]["records"][-1]["status"] == "PASS" else "FAIL"
    payload["status"] = status
    write_json_once(run_dir / "smoke1-evidence.json", payload)
    write_text_once(run_dir / "smoke1-evidence.md", render_markdown(payload))
    print(json.dumps({"run_dir": relative(run_dir), "status": status}, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
