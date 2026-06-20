"""Verify M1.1S Gate S3: anchor and predicate trace core."""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document_from_path
from tqe.runtime.executor import (
    TacticalQueryExecutor,
    accepted_predicate_traces,
    execution_result_rows,
    runtime_anchors,
    runtime_parameters,
)
from tqe.runtime.ir import EvaluationTarget
from tqe.verification.m1_1_gate_r3 import build_report as build_gate_r3_report

REPORT_PATH = Path("artifacts/m1.1/gate-s3-verification-report.json")
APPROVED_PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pass_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "pass", "message": message, "details": details or {}}


def fail_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "fail", "message": message, "details": details or {}}


def build_report() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    bound = bind_document_from_path(APPROVED_PLAN_PATH)
    executor = TacticalQueryExecutor()
    state = executor._execute_period(  # noqa: SLF001 - verifier inspects anchor core directly.
        bound_plan=bound,
        match_id="J03WOY",
        period="firstHalf",
        params=runtime_parameters(bound),
    )
    anchors = runtime_anchors(state, bound.anchor_source)

    checks.extend(validate_runtime_anchor_set(state, anchors))
    checks.extend(validate_target_evaluation_uses_anchor_core(executor, bound))
    checks.extend(validate_trace_extraction_uses_anchor_core(state))
    checks.extend(validate_unknown_policy_proof_still_passes())
    checks.extend(validate_approved_plan_parity(bound, executor))

    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.1S",
        "gate": "Gate_S3_anchor_predicate_trace_core",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    return report


def validate_runtime_anchor_set(state: Any, anchors: list[Any]) -> list[dict[str, Any]]:
    accepted_count = len(state.accepted)
    anchored_sources = sorted({f"{anchor.source_node_id}.{anchor.output_name}" for anchor in anchors})
    invalid = [
        anchor.anchor_id
        for anchor in anchors
        if not anchor.anchor_id
        or anchor.match_id != state.match_id
        or anchor.period != state.period
        or not isinstance(anchor.anchor_frame_id, int)
        or not isinstance(anchor.attributes, dict)
    ]
    return [
        pass_check(
            "anchors.runtime_anchor_set_independent_of_accepted_results",
            "runtime anchor set is produced from declared runtime outputs and is broader than accepted results",
            {
                "anchor_count": len(anchors),
                "accepted_count": accepted_count,
                "sources": anchored_sources,
            },
        )
        if len(anchors) > accepted_count and not invalid
        else fail_check(
            "anchors.runtime_anchor_set_independent_of_accepted_results",
            "runtime anchors were missing, malformed, or limited to accepted results",
            {
                "anchor_count": len(anchors),
                "accepted_count": accepted_count,
                "invalid_sample": invalid[:10],
                "sources": anchored_sources,
            },
        )
    ]


def validate_target_evaluation_uses_anchor_core(
    executor: TacticalQueryExecutor,
    bound: Any,
) -> list[dict[str, Any]]:
    source = inspect.getsource(TacticalQueryExecutor.evaluate_target)
    forbidden = "state.candidates" in source
    threshold = executor.evaluate_target(
        bound,
        EvaluationTarget(
            target_id="threshold_near_miss_j03woy_48010",
            match_id="J03WOY",
            period="firstHalf",
            approximate_time_ms=int(round(48010 / 25.0 * 1000.0)),
            search_radius_ms=1000,
        ),
    )
    unknowns = [
        trace
        for trace in threshold["predicate_traces"]
        if trace.get("status") == "UNKNOWN"
        and trace.get("source_evidence", {}).get("reason")
    ]
    closest = threshold.get("closest_candidate") or {}
    return [
        pass_check(
            "target_evaluation.uses_runtime_anchors",
            "target evaluation derives compatible anchors from runtime outputs, not state.candidates",
            {
                "status": threshold["status"],
                "candidate_count": threshold["candidate_count"],
                "anchor_id": closest.get("anchor_id"),
                "unknown_count": len(unknowns),
            },
        )
        if not forbidden
        and threshold["status"] == "NON_MATCH"
        and threshold["candidate_count"] >= 1
        and closest.get("anchor_id")
        and unknowns
        else fail_check(
            "target_evaluation.uses_runtime_anchors",
            "target evaluation still depends on candidate state or failed to produce anchor-backed traces",
            {
                "uses_state_candidates": forbidden,
                "evaluation": threshold,
                "unknown_count": len(unknowns),
            },
        )
    ]


def validate_trace_extraction_uses_anchor_core(state: Any) -> list[dict[str, Any]]:
    source = inspect.getsource(accepted_predicate_traces)
    traces = accepted_predicate_traces(state)
    accepted_ids = {str(result["result_id"]) for result in state.accepted}
    trace_ids = {str(trace.source_evidence.get("result_id")) for trace in traces}
    missing_anchor_ids = [
        trace.predicate_id
        for trace in traces
        if not trace.source_evidence.get("anchor_id")
    ]
    return [
        pass_check(
            "predicate_traces.accepted_results_use_anchor_records",
            "accepted-result traces are emitted from anchor/result records without walking state.candidates",
            {
                "accepted_count": len(state.accepted),
                "trace_count": len(traces),
            },
        )
        if "state.candidates" not in source
        and accepted_ids.issubset(trace_ids)
        and not missing_anchor_ids
        else fail_check(
            "predicate_traces.accepted_results_use_anchor_records",
            "accepted-result traces still depend on candidate dictionaries or lack anchor evidence",
            {
                "uses_state_candidates": "state.candidates" in source,
                "accepted_count": len(state.accepted),
                "trace_count": len(traces),
                "missing_anchor_id_sample": missing_anchor_ids[:10],
            },
        )
    ]


def validate_unknown_policy_proof_still_passes() -> list[dict[str, Any]]:
    report = build_gate_r3_report()
    check_status = {check["id"]: check["status"] for check in report["checks"]}
    required = {
        "unknown_policy.changes_behavior",
        "persists_for.tri_state_boolean_signal",
    }
    failed = sorted(check_id for check_id in required if check_status.get(check_id) != "pass")
    return [
        pass_check(
            "unknowns.actual_execution_policy_paths",
            "actual predicate/unknown policy proof still passes through node execution",
            {"gate_r3_status": report["status"], "required_checks": sorted(required)},
        )
        if report["status"] == "pass" and not failed
        else fail_check(
            "unknowns.actual_execution_policy_paths",
            "unknown propagation or unknown policy proof regressed",
            {"gate_r3_status": report["status"], "failed_required_checks": failed},
        )
    ]


def validate_approved_plan_parity(bound: Any, executor: TacticalQueryExecutor) -> list[dict[str, Any]]:
    execution = executor.execute(bound)
    rows = execution_result_rows(execution)
    traces = execution.predicate_traces
    return [
        pass_check(
            "approved_plan.parity_preserved",
            "approved plan still returns the frozen 180 results and 900 predicate traces",
            {"result_count": len(rows), "trace_count": len(traces)},
        )
        if len(rows) == 180 and len(traces) == 900
        else fail_check(
            "approved_plan.parity_preserved",
            "approved plan parity changed under anchor-core refactor",
            {"result_count": len(rows), "trace_count": len(traces)},
        )
    ]


def main() -> None:
    report = build_report()
    print(f"Wrote {REPORT_PATH}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
