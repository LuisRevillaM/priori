#!/usr/bin/env python3
"""PERF-1 fix-round focused test evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "delivery" / "packets" / "perf-1-evidence" / "fix-focused-tests"

FOCUSED_TESTS = [
    "tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_cache_key_mutates_for_every_director_component",
    "tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_cache_key_canonicalizes_expanded_defaults",
    "tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_persistent_cache_detects_corrupt_output_without_serving",
    "tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_persistent_cache_detects_corrupt_preimage_without_serving",
    "tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_persistent_cache_round_trips_frame_signal_outputs",
    "tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_encode_cache_output_rejects_ambiguous_containers",
    "tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_parallel_pool_falls_back_when_process_pool_is_unavailable",
    "tests.test_m1_1_runtime.M11RuntimeTests.test_parallel_period_execution_matches_sequential_ordering",
]


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


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


def make_run_dir(script_sha: str) -> Path:
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    for index in range(10_000):
        candidate = EVIDENCE_ROOT / f"{timestamp}{index:04d}-{script_sha[:12]}"
        if not candidate.exists():
            candidate.mkdir(parents=True)
            return candidate
    raise RuntimeError("could not allocate unique PERF-1 focused-test evidence directory")


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


def run_tests() -> tuple[subprocess.CompletedProcess[str], float]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "-v", *FOCUSED_TESTS],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed, round((time.perf_counter() - started) * 1000.0, 3)


def render_markdown(payload: dict[str, Any]) -> str:
    metadata = payload["evidence_metadata"]
    lines = [
        "<!-- evidence_metadata: "
        + json.dumps(metadata, sort_keys=True, separators=(",", ":"))
        + " -->",
        "# PERF-1 Fix Focused Test Evidence",
        "",
        f"- Status: `{payload['status']}`",
        f"- Duration: `{payload['duration_ms']} ms`",
        f"- Return code: `{payload['return_code']}`",
        "",
        "| Test |",
        "| --- |",
    ]
    lines.extend(f"| `{test}` |" for test in payload["tests"])
    lines.extend(
        [
            "",
            "## Stdout",
            "",
            "```",
            payload["stdout"].rstrip(),
            "```",
            "",
            "## Stderr",
            "",
            "```",
            payload["stderr"].rstrip(),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    script_path = Path(__file__).resolve()
    script_sha = file_sha256(script_path)
    run_dir = make_run_dir(script_sha)
    run_started_at = utc_now()
    completed, duration_ms = run_tests()
    metadata = {
        "schema_version": "perf1.focused_test_evidence_metadata.v1",
        "produced_by": relative(script_path),
        "producing_script_sha256": script_sha,
        "run_started_at": run_started_at,
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_tree": git_value("rev-parse", "HEAD^{tree}"),
        "git_branch": git_value("branch", "--show-current"),
        "run_dir": relative(run_dir),
    }
    payload = {
        "schema_version": "perf1.focused_test_evidence.v1",
        "evidence_metadata": metadata,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "return_code": completed.returncode,
        "duration_ms": duration_ms,
        "tests": list(FOCUSED_TESTS),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    write_json_once(run_dir / "perf1-focused-tests.json", payload)
    write_text_once(run_dir / "perf1-focused-tests.md", render_markdown(payload))
    print(json.dumps({"run_dir": relative(run_dir), "status": payload["status"]}, indent=2, sort_keys=True))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
