#!/usr/bin/env python3
"""Produce immutable HERMES-2 probe, frozen-DEV, and owner-phrase evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(__file__).resolve()
FRONTIER_COMMIT = "ab28c64"
CASE_SET_PATH = ROOT / "delivery/packets/scp2-2-dev-cases.json"
HARNESS_PATH = ROOT / "scripts/scp2_2/eval_harness.py"
BASELINE_PATH = ROOT / "delivery/packets/scp2-2-dev-results.json"
BRIDGE_PATH = ROOT / "src/tqe/workshop/hermes_invocation.py"
EVIDENCE_ROOT = ROOT / "delivery/packets/hermes-2-evidence/runs"
CANONICAL_HERMES_HOME = Path.home() / ".hermes-priori"
EXPECTED_CASE_SET_SHA256 = "07a10d76b1f3322e94131090068f19157975fbea65aefbebdb8e17aba2da4b7a"
EXPECTED_LEG_ZERO_HARNESS_SHA256 = "70ba3b0723b118be0c8c3e7420510831b1487d5c15a2c2337b74089d3b1a905f"
EXPECTED_PROVIDER = "openai-codex"
EXPECTED_MODEL = "gpt-5.6-sol"
EXPECTED_BILLING_SURFACE = "chatgpt_subscription"
PROBE_TEXT = "Show player body orientation immediately before receiving the ball."
OWNER_TEXT = (
    "When the ball carrier is pressed and no support arrives, "
    "how often does his team keep the ball?"
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bytes_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def git_value(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def git_bytes(*args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=20,
    )
    return completed.stdout


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
    if bytes_sha256(committed.stdout) != file_sha256(SCRIPT_PATH):
        raise SystemExit(f"evidence producer differs from committed HEAD: {relative}")
    with tempfile.TemporaryDirectory(prefix="hermes2-git-index-") as temp_dir:
        env = dict(os.environ)
        env["GIT_INDEX_FILE"] = str(Path(temp_dir) / "index")
        subprocess.run(
            ["git", "read-tree", "HEAD"],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            timeout=20,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        ).stdout.strip()
    if dirty:
        raise SystemExit("tracked tree is dirty; commit before producing HERMES-2 evidence")


def write_json_once(path: Path, payload: Any) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text_once(path: Path, payload: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def make_run_dir(*, phase: str, model: str, script_sha: str) -> Path:
    stamp = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H%M%SZ0000")
    safe_model = re.sub(r"[^a-zA-Z0-9_.-]+", "-", model)
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    for index in range(10_000):
        candidate = EVIDENCE_ROOT / f"{stamp}{index:04d}-{phase}-{safe_model}-{script_sha[:12]}"
        if not candidate.exists():
            candidate.mkdir(parents=True)
            return candidate
    raise RuntimeError("could not allocate a unique HERMES-2 evidence directory")


def landing_harness_bytes(model: str) -> bytes:
    original = git_bytes("show", f"{FRONTIER_COMMIT}:scripts/scp2_2/eval_harness.py")
    old = b'os.environ.get("HERMES_SCP2_2_MODEL", "gpt-5.5")'
    new = f'os.environ.get("HERMES_SCP2_2_MODEL", "{model}")'.encode()
    if original.count(old) != 1:
        raise RuntimeError("could not identify the one authorized harness-default line")
    return original.replace(old, new)


def fence_evidence(*, phase: str, model: str) -> dict[str, Any]:
    case_sha = file_sha256(CASE_SET_PATH)
    harness_sha = file_sha256(HARNESS_PATH)
    if case_sha != EXPECTED_CASE_SET_SHA256:
        raise RuntimeError(f"frozen DEV hash mismatch: {case_sha}")
    leg_zero_harness = git_bytes("show", f"{FRONTIER_COMMIT}:scripts/scp2_2/eval_harness.py")
    if bytes_sha256(leg_zero_harness) != EXPECTED_LEG_ZERO_HARNESS_SHA256:
        raise RuntimeError("frontier harness no longer matches the leg-zero pin")
    current_harness = HARNESS_PATH.read_bytes()
    allowed = current_harness == leg_zero_harness
    authorized_default_flip = False
    if phase == "landing" and not allowed:
        authorized_default_flip = current_harness == landing_harness_bytes(model)
        allowed = authorized_default_flip
    if not allowed:
        raise RuntimeError("committed harness differs beyond the phase-authorized model default")
    return {
        "frontier_commit": FRONTIER_COMMIT,
        "case_set_path": str(CASE_SET_PATH.relative_to(ROOT)),
        "case_set_sha256": case_sha,
        "expected_case_set_sha256": EXPECTED_CASE_SET_SHA256,
        "harness_path": str(HARNESS_PATH.relative_to(ROOT)),
        "harness_sha256": harness_sha,
        "leg_zero_harness_sha256": EXPECTED_LEG_ZERO_HARNESS_SHA256,
        "harness_exactly_leg_zero": current_harness == leg_zero_harness,
        "authorized_default_flip_only": authorized_default_flip,
        "fence_status": "PASS",
    }


def hermes_python_executable(hermes: str) -> str:
    first_line = Path(hermes).read_text(encoding="utf-8").splitlines()[0]
    if first_line.startswith("#!"):
        candidate = first_line[2:].strip()
        if Path(candidate).exists() and os.access(candidate, os.X_OK):
            return candidate
    return sys.executable


def parse_last_json_line(text: str) -> dict[str, Any]:
    for line in reversed(text.splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise RuntimeError("Hermes inspection did not emit a JSON object")


def inspect_hermes_route() -> dict[str, Any]:
    hermes = shutil.which("hermes")
    if not hermes:
        raise RuntimeError("Hermes executable was not found")
    hermes_python = hermes_python_executable(hermes)
    env = dict(os.environ)
    env["HERMES_HOME"] = str(CANONICAL_HERMES_HOME)
    code = """
import json
from hermes_cli.config import load_config
from hermes_cli.fallback_config import get_fallback_chain
from hermes_constants import parse_reasoning_effort
cfg = load_config()
model_cfg = cfg.get("model") or {}
agent_cfg = cfg.get("agent") or {}
payload = {
    "configured_provider": model_cfg.get("provider") if isinstance(model_cfg, dict) else None,
    "configured_model": model_cfg.get("default") if isinstance(model_cfg, dict) else model_cfg,
    "configured_reasoning_effort": agent_cfg.get("reasoning_effort") if isinstance(agent_cfg, dict) else None,
    "fallback_chain": get_fallback_chain(cfg),
    "effort_parser": {
        "max": parse_reasoning_effort("max"),
        "xhigh": parse_reasoning_effort("xhigh"),
    },
}
print(json.dumps(payload, sort_keys=True))
"""
    inspected = subprocess.run(
        [hermes_python, "-c", code],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if inspected.returncode != 0:
        raise RuntimeError(f"Hermes route inspection failed: {inspected.stderr[:500]}")
    payload = parse_last_json_line(inspected.stdout)
    version = subprocess.run(
        [hermes, "--version"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    route = {
        **payload,
        "hermes_executable": hermes,
        "hermes_python": hermes_python,
        "hermes_version": version.stdout.strip(),
        "hermes_home": str(CANONICAL_HERMES_HOME),
        "billing_surface": EXPECTED_BILLING_SURFACE,
        "max_accepted": payload.get("effort_parser", {}).get("max") is not None,
        "selected_effort": "max" if payload.get("effort_parser", {}).get("max") is not None else "xhigh",
        "bridge_path": str(BRIDGE_PATH.relative_to(ROOT)),
        "bridge_sha256": file_sha256(BRIDGE_PATH),
    }
    if route["configured_provider"] != EXPECTED_PROVIDER:
        raise RuntimeError(f"metered or unexpected provider configured: {route['configured_provider']!r}")
    if route["fallback_chain"]:
        raise RuntimeError("fallback providers are configured; subscription-only proof is not closed")
    if route["selected_effort"] != "xhigh":
        raise RuntimeError("installed Hermes unexpectedly accepted max; packet requires a recorded ruling before use")
    if route["configured_reasoning_effort"] != "xhigh":
        raise RuntimeError(f"canonical Hermes effort is not xhigh: {route['configured_reasoning_effort']!r}")
    return route


def model_call(*, text: str, provider: str, model: str) -> dict[str, Any]:
    from tqe.semantic_compiler.hermes_nl import (
        ExpressionOutcome,
        HermesNLModelOutputError,
        compile_nl_request,
    )
    from tqe.semantic_compiler.target_synthesis import synthesize_and_bind

    started_at = dt.datetime.now(dt.UTC)
    started = time.monotonic()
    try:
        outcome = compile_nl_request(text)
    except Exception as exc:  # noqa: BLE001 - live evidence must retain typed failures.
        record: dict[str, Any] = {
            "ok": False,
            "request_text": text,
            "exception_type": type(exc).__name__,
            "exception": str(exc),
        }
        if isinstance(exc, HermesNLModelOutputError):
            record["raw_completion"] = exc.raw_completion
            record["rejected_attempts"] = exc.rejected_attempts
    else:
        transcript = outcome.transcript
        record = {
            "ok": True,
            "request_text": text,
            "outcome": outcome.outcome,
            "outcome_payload": outcome.model_dump(mode="json"),
            "requested_provider": provider,
            "requested_model": model,
            "transcript_provider": transcript.model_provider,
            "transcript_model": transcript.model_name,
            "prompt_hash": transcript.prompt_hash,
            "completion_hash": transcript.completion_hash,
        }
        if isinstance(outcome, ExpressionOutcome):
            try:
                synthesized = synthesize_and_bind(outcome.expression)
            except Exception as exc:  # noqa: BLE001
                record["binds"] = False
                record["synthesis_error"] = f"{type(exc).__name__}: {exc}"
            else:
                record["binds"] = True
                record["synthesized_document_hash"] = synthesized["document_hash"]
        else:
            record["binds"] = None
    record["started_at_utc"] = started_at.isoformat().replace("+00:00", "Z")
    record["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return record


def run_harness(
    *, run_dir: Path, provider: str, model: str, long_threshold_seconds: float
) -> tuple[dict[str, Any], dict[str, Any]]:
    output_path = run_dir / "dev-results.json"
    log_path = run_dir / "dev-harness.txt"
    command = [
        sys.executable,
        str(HARNESS_PATH.relative_to(ROOT)),
        "--case-set",
        str(CASE_SET_PATH.relative_to(ROOT)),
        "--output",
        str(output_path.relative_to(ROOT)),
        "--provider",
        provider,
        "--model",
        model,
        "--long-threshold-seconds",
        str(long_threshold_seconds),
    ]
    env = dict(os.environ)
    env["HERMES_HOME"] = str(CANONICAL_HERMES_HOME)
    env["HERMES_SCP2_2_PROVIDER"] = provider
    env["HERMES_SCP2_2_MODEL"] = model
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(ROOT), env.get("PYTHONPATH", "")])
    print(f"HERMES-2 harness start: model={model}", flush=True)
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=10_800,
    )
    elapsed = round(time.monotonic() - started, 3)
    write_text_once(log_path, completed.stdout + completed.stderr)
    if not output_path.exists():
        raise RuntimeError(
            f"frozen harness produced no result (returncode={completed.returncode}): "
            f"{completed.stderr[:500]}"
        )
    result = json.loads(output_path.read_text(encoding="utf-8"))
    if completed.returncode not in (0, 1):
        raise RuntimeError(f"frozen harness failed structurally with returncode {completed.returncode}")
    if result.get("case_set_sha256") != EXPECTED_CASE_SET_SHA256:
        raise RuntimeError("harness result does not carry the frozen DEV hash")
    expected_tier = {
        "provider": provider,
        "model": model,
        "billing_surface": EXPECTED_BILLING_SURFACE,
    }
    if result.get("model_tier") != expected_tier:
        raise RuntimeError(f"harness model tier mismatch: {result.get('model_tier')!r}")
    invocation = {
        "command": command,
        "returncode": completed.returncode,
        "wall_elapsed_seconds": elapsed,
        "stdout_stderr_path": str(log_path.relative_to(ROOT)),
        "result_path": str(output_path.relative_to(ROOT)),
        "result_sha256": file_sha256(output_path),
    }
    print(
        "HERMES-2 harness complete: "
        f"PASS={result['summary']['pass']} FAIL={result['summary']['fail']} elapsed={elapsed}s",
        flush=True,
    )
    return result, invocation


def failure_attribution(verdict: dict[str, Any]) -> str | None:
    if verdict.get("status") == "PASS":
        return None
    observations = verdict.get("observations") or []
    if any(
        observation.get("exception_type")
        in {"AuthenticationError", "HermesNLAccessError", "TimeoutExpired"}
        or "model invocation failed" in str(observation.get("exception") or "").lower()
        for observation in observations
    ):
        return "model_access_failure"
    if any(
        observation.get("gap_code") == "MODEL_OUTPUT_TRUNCATED"
        or "Truncated" in str(observation.get("exception_type") or "")
        for observation in observations
    ):
        return "truncation"
    if any(
        observation.get("exception_type") == "HermesNLModelOutputError"
        or observation.get("raw_completion") is not None
        for observation in observations
    ):
        return "model_output_shape"
    return "genuine_gap"


def compare_to_baseline(candidate: dict[str, Any]) -> dict[str, Any]:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    baseline_by_id = {row["case_id"]: row for row in baseline["verdicts"]}
    candidate_by_id = {row["case_id"]: row for row in candidate["verdicts"]}
    if set(baseline_by_id) != set(candidate_by_id):
        raise RuntimeError("baseline and candidate case IDs differ")
    rows = []
    for case_id in baseline_by_id:
        before = baseline_by_id[case_id]
        after = candidate_by_id[case_id]
        if before["status"] == "FAIL" and after["status"] == "PASS":
            transition = "newly_passing"
        elif before["status"] == "PASS" and after["status"] == "FAIL":
            transition = "newly_failing"
        elif after["status"] == "PASS":
            transition = "unchanged_pass"
        else:
            transition = "unchanged_fail"
        rows.append(
            {
                "case_id": case_id,
                "baseline_status": before["status"],
                "candidate_status": after["status"],
                "transition": transition,
                "baseline_elapsed_seconds": before.get("elapsed_seconds"),
                "candidate_elapsed_seconds": after.get("elapsed_seconds"),
                "candidate_failure_attribution": failure_attribution(after),
                "candidate_failures": after.get("failures") or [],
            }
        )
    counts = {
        name: sum(1 for row in rows if row["transition"] == name)
        for name in ("newly_passing", "newly_failing", "unchanged_pass", "unchanged_fail")
    }
    newly_failing = [row["case_id"] for row in rows if row["transition"] == "newly_failing"]
    access_failures = [
        row["case_id"]
        for row in rows
        if row["candidate_failure_attribution"] == "model_access_failure"
    ]
    run_valid = not access_failures
    return {
        "baseline_path": str(BASELINE_PATH.relative_to(ROOT)),
        "baseline_sha256": file_sha256(BASELINE_PATH),
        "baseline_summary": baseline["summary"],
        "candidate_summary": candidate["summary"],
        "transition_counts": counts,
        "rows": rows,
        "run_valid_for_model_comparison": run_valid,
        "model_access_failure_cases": access_failures,
        "flip_gate": {
            "pass_count_at_least_historical_baseline": (
                run_valid and candidate["summary"]["pass"] >= baseline["summary"]["pass"]
            ),
            "newly_failing_cases_requiring_wrong_answer_review": newly_failing,
            "human_wrong_answer_review_required": bool(newly_failing),
            "model_access_closed": run_valid,
        },
    }


def metadata(*, phase: str, model: str, provider: str) -> dict[str, Any]:
    return {
        "schema_version": "hermes2.evidence.v1",
        "producing_script": str(SCRIPT_PATH.relative_to(ROOT)),
        "producing_script_sha256": file_sha256(SCRIPT_PATH),
        "run_started_at_utc": dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z"),
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_tree": git_value("rev-parse", "HEAD^{tree}"),
        "branch": git_value("rev-parse", "--abbrev-ref", "HEAD"),
        "phase": phase,
        "provider": provider,
        "model": model,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Produce HERMES-2 immutable evidence.")
    parser.add_argument("--phase", choices=("measurement", "control", "landing"), default="measurement")
    parser.add_argument("--provider", default=EXPECTED_PROVIDER)
    parser.add_argument("--model", default=EXPECTED_MODEL)
    parser.add_argument("--long-threshold-seconds", default=300.0, type=float)
    args = parser.parse_args(argv)
    if args.provider != EXPECTED_PROVIDER:
        raise SystemExit("HERMES-2 permits only the openai-codex subscription provider")
    if args.phase in {"measurement", "landing"} and args.model != EXPECTED_MODEL:
        raise SystemExit(f"{args.phase} phase requires model {EXPECTED_MODEL}")

    require_committed_clean_script()
    script_sha = file_sha256(SCRIPT_PATH)
    run_dir = make_run_dir(phase=args.phase, model=args.model, script_sha=script_sha)
    meta = metadata(phase=args.phase, model=args.model, provider=args.provider)
    write_json_once(run_dir / "metadata.json", meta)
    os.environ["HERMES_HOME"] = str(CANONICAL_HERMES_HOME)
    os.environ["HERMES_SCP2_2_PROVIDER"] = args.provider
    os.environ["HERMES_SCP2_2_MODEL"] = args.model
    runtime_root = run_dir / "hermes-runtime"
    os.environ["TQE_WORKSHOP_OUTPUT_ROOT"] = str(runtime_root)
    os.environ["TQE_RUNTIME_ROOT"] = str(runtime_root)

    try:
        fences = fence_evidence(phase=args.phase, model=args.model)
        write_json_once(run_dir / "fences.json", fences)
        route = inspect_hermes_route()
        write_json_once(run_dir / "route.json", route)

        probe: dict[str, Any] | None = None
        if args.phase == "measurement":
            print("HERMES-2 live model-ID probe start", flush=True)
            probe = model_call(text=PROBE_TEXT, provider=args.provider, model=args.model)
            write_json_once(run_dir / "probe.json", probe)
            print(
                f"HERMES-2 live model-ID probe complete: ok={probe['ok']} "
                f"outcome={probe.get('outcome')}",
                flush=True,
            )
            if not probe["ok"]:
                final = {
                    "evidence_metadata": meta,
                    "status": "PROBE_REJECTED",
                    "fences": fences,
                    "route": route,
                    "probe": probe,
                }
                write_json_once(run_dir / "hermes2-evidence.json", final)
                return 2

        dev_result, harness_invocation = run_harness(
            run_dir=run_dir,
            provider=args.provider,
            model=args.model,
            long_threshold_seconds=args.long_threshold_seconds,
        )
        comparison = compare_to_baseline(dev_result)
        write_json_once(run_dir / "comparison.json", comparison)

        owner_spot_check: dict[str, Any] | None = None
        if args.phase == "measurement":
            print("HERMES-2 owner-phrasing spot-check start", flush=True)
            owner_spot_check = model_call(text=OWNER_TEXT, provider=args.provider, model=args.model)
            write_json_once(run_dir / "owner-phrasing.json", owner_spot_check)
            print(
                "HERMES-2 owner-phrasing spot-check complete: "
                f"outcome={owner_spot_check.get('outcome')} binds={owner_spot_check.get('binds')}",
                flush=True,
            )

        final = {
            "evidence_metadata": meta,
            "status": (
                "COMPLETE"
                if comparison["run_valid_for_model_comparison"]
                else "INVALID_MODEL_ACCESS"
            ),
            "fences": fences,
            "route": route,
            "probe": probe,
            "dev_eval": {
                "invocation": harness_invocation,
                "summary": dev_result["summary"],
                "elapsed_seconds": dev_result["elapsed_seconds"],
                "long_run_flag": dev_result["long_run_flag"],
                "model_tier": dev_result["model_tier"],
            },
            "comparison": comparison,
            "owner_phrasing_spot_check": owner_spot_check,
        }
        write_json_once(run_dir / "hermes2-evidence.json", final)
    except Exception as exc:  # noqa: BLE001 - preserve immutable failure evidence.
        failure = {
            "evidence_metadata": meta,
            "status": "EVIDENCE_PRODUCER_FAILED",
            "exception_type": type(exc).__name__,
            "exception": str(exc),
        }
        write_json_once(run_dir / "failure.json", failure)
        print(json.dumps({"run_dir": str(run_dir.relative_to(ROOT)), **failure}, sort_keys=True), flush=True)
        return 2

    print(
        json.dumps(
            {
                "run_dir": str(run_dir.relative_to(ROOT)),
                "summary": final["dev_eval"]["summary"],
                "status": final["status"],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if final["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
