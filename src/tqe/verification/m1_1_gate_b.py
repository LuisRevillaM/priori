"""Verify M1.1 Gate B: runtime execution parity with the frozen M1 oracle."""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from tqe.query.ball_side_block_shift import (
    detect_match as legacy_detect_match,
    load_query_runtime as load_legacy_query_runtime,
    select_proof_results as legacy_select_proof_results,
)
from tqe.runtime.executor import (
    DEFAULT_CANONICAL_ROOT,
    DEFAULT_RAW_ROOT,
    execution_result_rows,
    execute_default_plan,
    runtime_parameters,
    select_proof_results,
    summarize_results,
)
from tqe.verification.m1_1_gate_a import build_report as build_gate_a_report

DEFAULT_CONFIG_PATH = Path("config/queries/ball_side_block_shift.v1.yaml")
PARITY_REPORT = Path("artifacts/m1.1/parity-report.json")
RUNTIME_EXECUTION_REPORT = Path("artifacts/m1.1/runtime-execution.json")
VERIFY_REPORT = Path("artifacts/m1.1/gate-b-verification-report.json")
BASELINE_MANIFEST = Path("delivery/m1/baseline/m1-baseline-manifest.json")
LEGACY_MANIFEST = Path("delivery/m1/baseline/legacy-result-manifest.json")
EXECUTOR_PATH = Path("src/tqe/runtime/executor.py")
LEGACY_SOURCE_FILES = [
    Path("config/queries/ball_side_block_shift.v1.yaml"),
    Path("src/tqe/query/ball_side_block_shift.py"),
    Path("src/tqe/evidence/gate_c_build.py"),
    Path("src/tqe/verification/gate_c.py"),
    Path("apps/replay-proof/src/verifyBundles.ts"),
]

STRICT_FIELDS = [
    "result_id",
    "classification",
    "match_id",
    "period",
    "perspective_team_role",
    "baseline_start_frame_id",
    "baseline_end_frame_id",
    "wide_entry_frame_id",
    "anchor_frame_id",
    "outcome_frame_id",
    "replay_start_frame_id",
    "replay_end_frame_id",
    "quality_status",
    "query_hash",
    "query_id",
    "query_version",
]
FLOAT_FIELDS = [
    "signed_shift_metres",
    "block_shift_score",
    "baseline_defensive_centroid_y_m",
    "wide_entry_y_m",
    "possession_duration_seconds",
]


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pass_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "pass", "message": message, "details": details or {}}


def fail_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "fail", "message": message, "details": details or {}}


def build_report() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    gate_a = build_gate_a_report()
    checks.append(
        pass_check("gate_a.precondition", "Gate A verifier passes")
        if gate_a["status"] == "pass"
        else fail_check("gate_a.precondition", "Gate A verifier must pass before Gate B")
    )

    legacy_runtime = load_legacy_query_runtime(DEFAULT_CONFIG_PATH)
    legacy_all = legacy_accepted_results(legacy_runtime)
    legacy_selected = legacy_select_proof_results(legacy_all, legacy_runtime)

    bound, runtime_execution = execute_default_plan()
    runtime_all = execution_result_rows(runtime_execution)
    _, runtime_repeat = execute_default_plan()
    runtime_repeat_rows = execution_result_rows(runtime_repeat)
    params = runtime_parameters(bound)
    runtime_selected = select_proof_results(runtime_all, params)

    write_json(
        RUNTIME_EXECUTION_REPORT,
        {
            "schema_version": "1.0",
            "generated_at": utc_now_iso(),
            "status": "pass",
            "plan_hash": bound.plan_hash,
            "bound_plan_hash": bound.bound_plan_hash,
            "execution_id": runtime_execution.execution_id,
            "result_summary": summarize_results(runtime_all),
            "selected_result_ids": [item["result_id"] for item in runtime_selected],
            "runtime_trace_hash": runtime_execution.provenance["runtime_trace_hash"],
        },
    )

    checks.extend(compare_complete_outputs(legacy_all, runtime_all))
    checks.extend(compare_selected_outputs(legacy_selected, runtime_selected))
    checks.extend(compare_baseline_manifests(runtime_selected))
    checks.extend(compare_repeat_execution(runtime_execution, runtime_all, runtime_repeat, runtime_repeat_rows))
    checks.extend(check_replay_windows(runtime_selected))
    checks.extend(check_legacy_source_hash())
    checks.extend(check_executor_architecture())

    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.1",
        "gate": "Gate_B_M1_runtime_parity",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "query": {
            "legacy_query_hash": legacy_runtime.query_hash,
            "plan_hash": bound.plan_hash,
            "bound_plan_hash": bound.bound_plan_hash,
        },
        "legacy_summary": summarize_results(legacy_all),
        "runtime_summary": summarize_results(runtime_all),
        "selected_result_ids": [item["result_id"] for item in runtime_selected],
        "checks": checks,
    }
    write_json(PARITY_REPORT, report)
    return report


def legacy_accepted_results(legacy_runtime: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match_id in legacy_runtime.config.evaluation_match_ids:
        accepted, _near = legacy_detect_match(
            runtime=legacy_runtime,
            match_id=match_id,
            canonical_root=DEFAULT_CANONICAL_ROOT,
            raw_root=DEFAULT_RAW_ROOT,
        )
        rows.extend(accepted)
    return rows


def compare_complete_outputs(
    legacy_all: list[dict[str, Any]],
    runtime_all: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    legacy_ids = [item["result_id"] for item in legacy_all]
    runtime_ids = [item["result_id"] for item in runtime_all]
    checks.append(
        pass_check(
            "parity.all_result_ids_ordered",
            "runtime accepted result IDs match legacy in order",
            {"count": len(runtime_ids)},
        )
        if legacy_ids == runtime_ids
        else fail_check(
            "parity.all_result_ids_ordered",
            "runtime accepted result IDs differ from legacy",
            {"legacy_count": len(legacy_ids), "runtime_count": len(runtime_ids)},
        )
    )
    checks.append(
        pass_check("parity.all_summary", "runtime accepted summary matches legacy")
        if summarize_results(legacy_all) == summarize_results(runtime_all)
        else fail_check(
            "parity.all_summary",
            "runtime accepted summary differs from legacy",
            {"legacy": summarize_results(legacy_all), "runtime": summarize_results(runtime_all)},
        )
    )

    mismatches = result_mismatches(legacy_all, runtime_all)
    checks.append(
        pass_check("parity.all_fields", "runtime accepted fields match legacy within tolerance")
        if not mismatches
        else fail_check(
            "parity.all_fields",
            "runtime accepted fields differ from legacy",
            {"mismatch_count": len(mismatches), "sample": mismatches[:10]},
        )
    )
    return checks


def compare_selected_outputs(
    legacy_selected: list[dict[str, Any]],
    runtime_selected: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    legacy_ids = [item["result_id"] for item in legacy_selected]
    runtime_ids = [item["result_id"] for item in runtime_selected]
    checks.append(
        pass_check(
            "parity.selected_result_ids",
            "runtime selected proof result IDs match legacy",
            {"selected_count": len(runtime_ids)},
        )
        if legacy_ids == runtime_ids
        else fail_check(
            "parity.selected_result_ids",
            "runtime selected proof result IDs differ from legacy",
            {"legacy": legacy_ids, "runtime": runtime_ids},
        )
    )
    mismatches = result_mismatches(legacy_selected, runtime_selected)
    checks.append(
        pass_check("parity.selected_fields", "runtime selected fields match legacy within tolerance")
        if not mismatches
        else fail_check(
            "parity.selected_fields",
            "runtime selected fields differ from legacy",
            {"mismatch_count": len(mismatches), "sample": mismatches[:10]},
        )
    )
    return checks


def compare_baseline_manifests(runtime_selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baseline = json.loads(BASELINE_MANIFEST.read_text(encoding="utf-8"))
    legacy_manifest = json.loads(LEGACY_MANIFEST.read_text(encoding="utf-8"))
    runtime_ids = [item["result_id"] for item in runtime_selected]
    baseline_ids = baseline["legacy_result_manifest"]["selected_result_ids"]
    manifest_ids = [item["result_id"] for item in legacy_manifest["selected_results"]]
    return [
        pass_check("baseline.selected_ids", "runtime selected result IDs match baseline manifest")
        if runtime_ids == baseline_ids == manifest_ids
        else fail_check(
            "baseline.selected_ids",
            "runtime selected result IDs differ from baseline manifest",
            {"runtime": runtime_ids, "baseline": baseline_ids, "legacy_manifest": manifest_ids},
        ),
        pass_check("baseline.query_hash", "runtime uses frozen M1 query hash")
        if all(item["query_hash"] == baseline["query_freeze"]["query_hash"] for item in runtime_selected)
        else fail_check("baseline.query_hash", "runtime did not use frozen M1 query hash"),
    ]


def compare_repeat_execution(
    first_execution: Any,
    first_rows: list[dict[str, Any]],
    repeat_execution: Any,
    repeat_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    first_ids = [item["result_id"] for item in first_rows]
    repeat_ids = [item["result_id"] for item in repeat_rows]
    return [
        pass_check("determinism.result_ids", "repeated runtime result IDs are identical")
        if first_ids == repeat_ids
        else fail_check("determinism.result_ids", "repeated runtime result IDs differ"),
        pass_check("determinism.execution_id", "repeated runtime execution IDs are identical")
        if first_execution.execution_id == repeat_execution.execution_id
        else fail_check("determinism.execution_id", "repeated runtime execution IDs differ"),
        pass_check("determinism.trace_hash", "repeated runtime trace hashes are identical")
        if first_execution.provenance["runtime_trace_hash"]
        == repeat_execution.provenance["runtime_trace_hash"]
        else fail_check("determinism.trace_hash", "repeated runtime trace hashes differ"),
    ]


def check_replay_windows(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for result in selected:
        frames_path = (
            DEFAULT_CANONICAL_ROOT
            / "frames"
            / f"match_id={result['match_id']}"
            / f"period={result['period']}.parquet"
        )
        positions_path = (
            DEFAULT_CANONICAL_ROOT
            / "positions"
            / f"match_id={result['match_id']}"
            / f"period={result['period']}.parquet"
        )
        frame_ids = set(pq.ParquetFile(frames_path).read(columns=["frame_id"]).column("frame_id").to_pylist())
        position_frame_ids = set(
            pq.ParquetFile(positions_path).read(columns=["frame_id"]).column("frame_id").to_pylist()
        )
        required = {
            int(result["replay_start_frame_id"]),
            int(result["replay_end_frame_id"]),
            int(result["baseline_start_frame_id"]),
            int(result["baseline_end_frame_id"]),
            int(result["wide_entry_frame_id"]),
            int(result["anchor_frame_id"]),
            int(result["outcome_frame_id"]),
        }
        if not required.issubset(frame_ids) or not required.issubset(position_frame_ids):
            failures.append({"result_id": result["result_id"], "missing": sorted(required - frame_ids)})
    return [
        pass_check(
            "replay_windows.canonical_traceability",
            "selected replay windows and predicate frames are present in canonical frame/position sources",
            {"selected_count": len(selected)},
        )
        if not failures
        else fail_check(
            "replay_windows.canonical_traceability",
            "selected replay windows are not fully traceable to canonical sources",
            {"failures": failures[:10]},
        )
    ]


def check_legacy_source_hash() -> list[dict[str, Any]]:
    baseline = json.loads(BASELINE_MANIFEST.read_text(encoding="utf-8"))
    combined = combined_sha256(LEGACY_SOURCE_FILES)
    expected = baseline["legacy_detector_source_hash"]["combined_sha256"]
    return [
        pass_check("legacy_oracle.source_hash", "legacy detector source hash still matches baseline")
        if combined == expected
        else fail_check(
            "legacy_oracle.source_hash",
            "legacy detector source hash changed after baseline freeze",
            {"expected": expected, "actual": combined},
        )
    ]


def check_executor_architecture() -> list[dict[str, Any]]:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    branch_names = {"query_id", "recipe_id", "plan_id"}
    branch_hits: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            names = {child.id for child in ast.walk(node.test) if isinstance(child, ast.Name)}
            attrs = {child.attr for child in ast.walk(node.test) if isinstance(child, ast.Attribute)}
            hit = sorted((names | attrs) & branch_names)
            if hit:
                branch_hits.append({"line": node.lineno, "names": hit})
    return [
        pass_check("architecture.no_query_id_branch", "executor has no query/recipe/plan ID conditionals")
        if not branch_hits
        else fail_check(
            "architecture.no_query_id_branch",
            "executor branches on query/recipe/plan identity",
            {"branch_hits": branch_hits},
        )
    ]


def result_mismatches(
    legacy_rows: list[dict[str, Any]],
    runtime_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for index, (legacy, runtime) in enumerate(zip(legacy_rows, runtime_rows, strict=False)):
        if legacy.get("result_id") != runtime.get("result_id"):
            mismatches.append(
                {
                    "index": index,
                    "field": "result_id",
                    "legacy": legacy.get("result_id"),
                    "runtime": runtime.get("result_id"),
                }
            )
            continue
        for field in STRICT_FIELDS:
            if legacy.get(field) != runtime.get(field):
                mismatches.append(
                    {
                        "result_id": legacy.get("result_id"),
                        "field": field,
                        "legacy": legacy.get(field),
                        "runtime": runtime.get(field),
                    }
                )
        for field in FLOAT_FIELDS:
            legacy_value = float(legacy.get(field, 0.0))
            runtime_value = float(runtime.get(field, 0.0))
            if abs(legacy_value - runtime_value) > 0.001:
                mismatches.append(
                    {
                        "result_id": legacy.get("result_id"),
                        "field": field,
                        "legacy": legacy_value,
                        "runtime": runtime_value,
                    }
                )
    if len(legacy_rows) != len(runtime_rows):
        mismatches.append(
            {
                "field": "row_count",
                "legacy": len(legacy_rows),
                "runtime": len(runtime_rows),
            }
        )
    return mismatches


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def combined_sha256(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: str(item)):
        digest.update(str(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> int:
    report = build_report()
    write_json(VERIFY_REPORT, report)
    print(f"Wrote {PARITY_REPORT}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
