"""Verify M1.1 Gate C: predicate traces and non-match evaluation."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from tqe.runtime.binder import BindError, bind_document
from tqe.runtime.executor import (
    DEFAULT_CANONICAL_ROOT,
    DEFAULT_PLAN_PATH,
    LEGACY_M1_PARITY_PROFILE,
    TacticalQueryExecutor,
    execution_result_rows,
    execute_default_plan,
)
from tqe.runtime.ir import BoundPredicateNode, EvaluationTarget, TacticalQueryDocument
from tqe.verification.m1_1_gate_b import build_report as build_gate_b_report

PREDICATE_TRACE_REPORT = Path("artifacts/m1.1/predicate-trace-report.json")
NON_MATCH_REPORT = Path("artifacts/m1.1/non-match-inspection-report.json")
VERIFY_REPORT = Path("artifacts/m1.1/gate-c-verification-report.json")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pass_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "pass", "message": message, "details": details or {}}


def fail_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "fail", "message": message, "details": details or {}}


def build_report(gate_b_report: dict[str, Any] | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    gate_b = gate_b_report or build_gate_b_report()
    checks.append(
        pass_check("gate_b.precondition", "Gate B verifier passes")
        if gate_b["status"] == "pass"
        else fail_check("gate_b.precondition", "Gate B must pass before Gate C")
    )

    bound, execution = execute_default_plan()
    rows = execution_result_rows(execution)
    trace_payload = [
        trace.model_dump(mode="json", exclude_none=True) for trace in execution.predicate_traces
    ]
    expected_predicates = [
        node.node_id for node in bound.nodes if isinstance(node, BoundPredicateNode)
    ]

    predicate_report = {
        "schema_version": "1.0",
        "milestone": "M1.1",
        "gate": "Gate_C_predicate_trace_non_match_evaluation",
        "generated_at": utc_now_iso(),
        "status": "pass",
        "plan_hash": bound.plan_hash,
        "bound_plan_hash": bound.bound_plan_hash,
        "result_count": len(rows),
        "expected_predicates": expected_predicates,
        "trace_count": len(trace_payload),
        "trace_hash": execution.provenance["runtime_trace_hash"],
        "predicate_traces": trace_payload,
    }
    write_json(PREDICATE_TRACE_REPORT, predicate_report)

    executor = TacticalQueryExecutor(compatibility_profile=LEGACY_M1_PARITY_PROFILE)
    targets = default_evaluation_targets()
    evaluations = [executor.evaluate_target(bound, target) for target in targets]
    non_match_report = {
        "schema_version": "1.0",
        "milestone": "M1.1",
        "gate": "Gate_C_predicate_trace_non_match_evaluation",
        "generated_at": utc_now_iso(),
        "status": "pass",
        "plan_hash": bound.plan_hash,
        "bound_plan_hash": bound.bound_plan_hash,
        "evaluations": evaluations,
    }
    write_json(NON_MATCH_REPORT, non_match_report)

    checks.extend(validate_predicate_traces(rows, trace_payload, expected_predicates))
    checks.extend(validate_non_match_evaluations(evaluations))
    checks.extend(validate_trace_sources(rows))
    checks.extend(validate_invalid_plan_failure())

    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.1",
        "gate": "Gate_C_predicate_trace_non_match_evaluation",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "artifacts": {
            "predicate_trace_report": str(PREDICATE_TRACE_REPORT),
            "non_match_inspection_report": str(NON_MATCH_REPORT),
        },
        "checks": checks,
    }
    write_json(VERIFY_REPORT, report)
    return report


def default_evaluation_targets() -> list[EvaluationTarget]:
    return [
        EvaluationTarget(
            target_id="threshold_near_miss_j03woy_48010",
            match_id="J03WOY",
            period="firstHalf",
            approximate_time_ms=frame_to_ms(48010),
            search_radius_ms=1000,
        ),
        EvaluationTarget(
            target_id="stoppage_excluded_j03woy_27895",
            match_id="J03WOY",
            period="firstHalf",
            approximate_time_ms=frame_to_ms(27895),
            search_radius_ms=1000,
        ),
        EvaluationTarget(
            target_id="quiet_opening_j03woy_first_half",
            match_id="J03WOY",
            period="firstHalf",
            approximate_time_ms=frame_to_ms(10000),
            search_radius_ms=1000,
        ),
    ]


def frame_to_ms(frame_id: int) -> int:
    return int(round(frame_id / 25.0 * 1000.0))


def validate_predicate_traces(
    rows: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    expected_predicates: list[str],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    by_result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trace in traces:
        result_id = str(trace.get("source_evidence", {}).get("result_id", ""))
        by_result[result_id].append(trace)

    result_ids = [str(row["result_id"]) for row in rows]
    missing = [
        result_id
        for result_id in result_ids
        if sorted(trace["predicate_id"] for trace in by_result.get(result_id, []))
        != sorted(expected_predicates)
    ]
    checks.append(
        pass_check(
            "predicate_traces.cover_every_result",
            "every runtime result has one trace for each bound predicate",
            {"result_count": len(rows), "trace_count": len(traces)},
        )
        if not missing and len(traces) == len(rows) * len(expected_predicates)
        else fail_check(
            "predicate_traces.cover_every_result",
            "one or more runtime results are missing full predicate traces",
            {"missing_result_ids": missing[:10], "trace_count": len(traces)},
        )
    )

    malformed: list[dict[str, Any]] = []
    non_pass: list[dict[str, Any]] = []
    for trace in traces:
        source = trace.get("source_evidence", {})
        has_frame_or_window = trace.get("frame_id") is not None or trace.get("window") is not None
        if (
            trace.get("status") not in {"PASS", "FAIL", "UNKNOWN"}
            or trace.get("unit") is None
            or trace.get("value") is None
            or trace.get("threshold") is None
            or not has_frame_or_window
            or not source
            or source.get("result_id") not in result_ids
        ):
            malformed.append(trace)
        if trace.get("status") != "PASS":
            non_pass.append(trace)

    checks.append(
        pass_check("predicate_traces.shape", "predicate traces expose status, value, threshold, unit, frame/window, and source evidence")
        if not malformed
        else fail_check(
            "predicate_traces.shape",
            "predicate traces are missing required evidence fields",
            {"malformed_count": len(malformed), "sample": malformed[:5]},
        )
    )
    checks.append(
        pass_check("predicate_traces.accepted_pass", "all accepted-result predicate traces pass")
        if not non_pass
        else fail_check(
            "predicate_traces.accepted_pass",
            "accepted results contain failed or unknown predicate traces",
            {"sample": non_pass[:5]},
        )
    )
    return checks


def validate_non_match_evaluations(evaluations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["target"]["target_id"]: item for item in evaluations}
    threshold = by_id["threshold_near_miss_j03woy_48010"]
    stoppage = by_id["stoppage_excluded_j03woy_27895"]
    quiet = by_id["quiet_opening_j03woy_first_half"]

    threshold_failed = {item["predicate_id"]: item for item in threshold["failed_predicates"]}
    stoppage_failed = {item["predicate_id"]: item for item in stoppage["failed_predicates"]}
    unknowns = [
        item
        for evaluation in evaluations
        for item in evaluation["failed_predicates"]
        if item["status"] == "UNKNOWN"
    ]
    unknown_without_reason = [
        item for item in unknowns if not item.get("source_evidence", {}).get("reason")
    ]

    return [
        pass_check("non_match.threshold_target", "forced threshold near-miss returns engine-authored failed predicates")
        if threshold["status"] == "NON_MATCH"
        and threshold_failed.get("shift_persists", {}).get("status") == "FAIL"
        else fail_check(
            "non_match.threshold_target",
            "threshold near-miss did not expose shift_persists failure",
            {"evaluation": threshold},
        ),
        pass_check("non_match.stoppage_target", "forced stoppage target returns not_stoppage failure")
        if stoppage["status"] == "NON_MATCH"
        and stoppage_failed.get("not_stoppage", {}).get("status") == "FAIL"
        else fail_check(
            "non_match.stoppage_target",
            "stoppage non-match did not expose not_stoppage failure",
            {"evaluation": stoppage},
        ),
        pass_check("non_match.no_compatible_anchor", "quiet forced window returns NO_COMPATIBLE_ANCHOR")
        if quiet["status"] == "NO_COMPATIBLE_ANCHOR" and quiet["candidate_count"] == 0
        else fail_check(
            "non_match.no_compatible_anchor",
            "quiet forced window found a candidate or returned the wrong status",
            {"evaluation": quiet},
        ),
        pass_check("non_match.unknown_not_false", "UNKNOWN predicates are explicit and carry engine reasons")
        if unknowns and not unknown_without_reason
        else fail_check(
            "non_match.unknown_not_false",
            "UNKNOWN predicates were absent or lacked explicit reasons",
            {"unknown_count": len(unknowns), "sample": unknown_without_reason[:5]},
        ),
    ]


def validate_trace_sources(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    positions_cache: dict[tuple[str, str], Any] = {}
    players_cache: dict[tuple[str, str], set[str]] = {}

    for row in rows:
        match_id = str(row["match_id"])
        period = str(row["period"])
        key = (match_id, period)
        if key not in positions_cache:
            path = DEFAULT_CANONICAL_ROOT / "positions" / f"match_id={match_id}" / f"period={period}.parquet"
            positions_cache[key] = pq.ParquetFile(path).read(
                columns=["frame_id", "team_role", "entity_id", "entity_type", "y_m"]
            ).to_pandas()
        positions = positions_cache[key]
        ball = positions[
            (positions.entity_type == "ball")
            & (positions.frame_id == int(row["wide_entry_frame_id"]))
        ]
        if ball.empty or abs(round(float(ball.iloc[0].y_m), 3) - float(row["wide_entry_y_m"])) > 0.001:
            failures.append({"result_id": row["result_id"], "field": "wide_entry_y_m"})
            continue

        player_key = (match_id, str(row["defending_team_role"]))
        if player_key not in players_cache:
            players_cache[player_key] = outfield_players(match_id, str(row["defending_team_role"]))
        defenders = positions[
            (positions.entity_type == "player")
            & (positions.team_role == row["defending_team_role"])
            & (positions.entity_id.astype(str).isin(players_cache[player_key]))
        ]
        baseline = defenders[
            (defenders.frame_id >= int(row["baseline_start_frame_id"]))
            & (defenders.frame_id <= int(row["baseline_end_frame_id"]))
        ]
        if baseline.empty:
            failures.append({"result_id": row["result_id"], "field": "baseline_empty"})
            continue
        centroid = float(baseline.groupby("frame_id").y_m.mean().mean())
        if abs(round(centroid, 3) - float(row["baseline_defensive_centroid_y_m"])) > 0.001:
            failures.append({"result_id": row["result_id"], "field": "baseline_defensive_centroid_y_m"})

    return [
        pass_check(
            "trace_sources.canonical_coordinates",
            "runtime trace evidence recomputes from canonical ball and defender coordinates",
            {"result_count": len(rows)},
        )
        if not failures
        else fail_check(
            "trace_sources.canonical_coordinates",
            "runtime trace evidence does not match canonical coordinates",
            {"failure_count": len(failures), "sample": failures[:10]},
        )
    ]


def validate_invalid_plan_failure() -> list[dict[str, Any]]:
    payload = json.loads(DEFAULT_PLAN_PATH.read_text(encoding="utf-8"))
    payload["draft_plan"]["nodes"][2]["operator"]["name"] = "unsupported_operator"
    document = TacticalQueryDocument.model_validate(payload)
    try:
        bind_document(document)
    except BindError as exc:
        codes = {issue.code for issue in exc.issues}
        return [
            pass_check(
                "invalid_plan.visible_failure",
                "unsupported plans fail visibly before execution",
                {"issue_codes": sorted(codes)},
            )
            if "unknown_operator" in codes
            else fail_check(
                "invalid_plan.visible_failure",
                "invalid plan failed without the expected visible issue",
                {"issue_codes": sorted(codes)},
            )
        ]
    return [fail_check("invalid_plan.visible_failure", "unsupported plan unexpectedly bound")]


def outfield_players(match_id: str, team_role: str) -> set[str]:
    players = pq.ParquetFile(DEFAULT_CANONICAL_ROOT / "players.parquet").read().to_pandas()
    selected = players[
        (players.match_id == match_id) & (players.team_role == team_role) & (~players.is_goalkeeper)
    ]
    return set(selected.player_id.astype(str))


def main() -> int:
    report = build_report()
    print(f"Wrote {VERIFY_REPORT}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
