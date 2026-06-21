"""Verify M1.1S Gate S5: alias-based evidence projection."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.binder import BindError, bind_document
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument

PLAN_PATH = Path("config/query-plans/possession_corridor_availability.experimental.v1.json")
REPORT_PATH = Path("artifacts/m1.1/gate-s5-verification-report.json")


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
    baseline = execute_payload(plan_payload())
    baseline_rows = execution_result_rows(baseline)

    checks.extend(validate_stable_aliases(baseline_rows))
    checks.extend(validate_node_rename_public_shape(baseline_rows))
    checks.extend(validate_evidence_rewire_changes_value(baseline_rows))
    checks.extend(validate_missing_evidence_fails_visibly())
    checks.extend(validate_unsupported_evidence_bind_failure())
    checks.extend(validate_no_default_m1_evidence_leak(baseline_rows))

    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.1S",
        "gate": "Gate_S5_alias_based_evidence_projection",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "execution": {
            "plan_path": str(PLAN_PATH),
            "status": baseline.status.value,
            "result_count": len(baseline_rows),
            "compatibility_profile": baseline.provenance.get("compatibility_profile"),
            "requested_evidence_failure_count": baseline.provenance.get("requested_evidence_failure_count"),
        },
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    return report


def validate_stable_aliases(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected = {
        "relation_id",
        "target_player_id",
        "destination_region",
        "relation_duration_seconds",
        "minimum_clearance_m",
    }
    failures = [
        row["result_id"]
        for row in rows
        if set(row.get("requested_evidence", {})) != expected
        or any("." in key for key in row.get("requested_evidence", {}))
        or any(value is None for value in row.get("requested_evidence", {}).values())
    ]
    return [
        pass_check(
            "evidence.stable_aliases",
            "requested evidence uses stable aliases independent of node IDs",
            {"aliases": sorted(expected), "result_count": len(rows)},
        )
        if rows and not failures
        else fail_check(
            "evidence.stable_aliases",
            "requested evidence aliases are missing, node-shaped, or null",
            {"failure_sample": failures[:10], "result_count": len(rows)},
        )
    ]


def validate_node_rename_public_shape(baseline_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload = plan_payload()
    rename_node(payload, "progressive_corridor", "renamed_corridor")
    rename_signal_refs(payload, "progressive_corridor", "renamed_corridor")
    renamed_rows = execution_result_rows(execute_payload(payload))
    baseline_public = public_rows(baseline_rows)
    renamed_public = public_rows(renamed_rows)
    return [
        pass_check(
            "evidence.node_rename_public_shape",
            "renaming an evidence-producing node preserves public result shape",
            {"result_count": len(baseline_public)},
        )
        if baseline_public == renamed_public and baseline_public
        else fail_check(
            "evidence.node_rename_public_shape",
            "node rename changed public rows or requested evidence",
            {
                "baseline_count": len(baseline_public),
                "renamed_count": len(renamed_public),
                "baseline_sample": baseline_public[:1],
                "renamed_sample": renamed_public[:1],
            },
        )
    ]


def validate_evidence_rewire_changes_value(baseline_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload = plan_payload()
    for request in payload["draft_plan"]["requested_evidence"]:
        if request["alias"] == "relation_duration_seconds":
            request["field"] = "minimum_clearance_m"
            request["alias"] = "rewired_metric"
    rewired_rows = execution_result_rows(execute_payload(payload))
    baseline_values = [row["requested_evidence"]["relation_duration_seconds"] for row in baseline_rows[:10]]
    rewired_values = [row["requested_evidence"]["rewired_metric"] for row in rewired_rows[:10]]
    rewired_keys = {tuple(sorted(row.get("requested_evidence", {}))) for row in rewired_rows}
    return [
        pass_check(
            "evidence.rewire_changes_value",
            "rewiring an evidence request to another declared field changes projected values",
            {
                "baseline_values": baseline_values[:5],
                "rewired_values": rewired_values[:5],
                "rewired_keys": [list(item) for item in sorted(rewired_keys)],
            },
        )
        if baseline_values
        and rewired_values
        and baseline_values != rewired_values
        and all("rewired_metric" in keys for keys in rewired_keys)
        else fail_check(
            "evidence.rewire_changes_value",
            "evidence rewire did not change projected values",
            {
                "baseline_values": baseline_values[:5],
                "rewired_values": rewired_values[:5],
                "rewired_keys": [list(item) for item in sorted(rewired_keys)],
            },
        )
    ]


def validate_missing_evidence_fails_visibly() -> list[dict[str, Any]]:
    payload = plan_payload()
    for request in payload["draft_plan"]["requested_evidence"]:
        if request["alias"] == "relation_id":
            request["source"] = {"source_node_id": "has_progressive_corridor", "output_name": "predicate"}
            request["field"] = "predicate_value"
            request["alias"] = "missing_predicate_value"
    execution = execute_payload(payload)
    rows = execution_result_rows(execution)
    failure_count = execution.provenance.get("requested_evidence_failure_count")
    failures = execution.provenance.get("requested_evidence_failures")
    return [
        pass_check(
            "evidence.missing_required_fails_visibly",
            "missing requested evidence fails visibly instead of silently passing nulls",
            {
                "status": execution.status.value,
                "result_count": len(rows),
                "failure_count": failure_count,
                "failure_sample": failures[:3] if isinstance(failures, list) else failures,
            },
        )
        if execution.status == ExecutionStatus.INCOMPLETE
        and isinstance(failure_count, int)
        and failure_count > 0
        and isinstance(failures, list)
        else fail_check(
            "evidence.missing_required_fails_visibly",
            "missing requested evidence did not produce visible incomplete status",
            {
                "status": execution.status.value,
                "failure_count": failure_count,
                "failures": failures,
            },
        )
    ]


def validate_unsupported_evidence_bind_failure() -> list[dict[str, Any]]:
    payload = plan_payload()
    payload["draft_plan"]["requested_evidence"][0]["field"] = "not_a_declared_field"
    try:
        bind_document(TacticalQueryDocument.model_validate(payload))
    except BindError as error:
        codes = {issue.code for issue in error.issues}
        return [
            pass_check(
                "evidence.unsupported_field_bind_failure",
                "unsupported evidence fields fail at bind time",
                {"codes": sorted(codes)},
            )
            if "unsupported_evidence_field" in codes
            else fail_check(
                "evidence.unsupported_field_bind_failure",
                "bind failed for a different reason",
                {"codes": sorted(codes)},
            )
        ]
    return [
        fail_check(
            "evidence.unsupported_field_bind_failure",
            "unsupported evidence field unexpectedly bound successfully",
        )
    ]


def validate_no_default_m1_evidence_leak(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    forbidden = {
        "block_shift_score",
        "wide_entry_frame_id",
        "signed_shift_metres",
        "baseline_defensive_centroid_y_m",
        "source_classification",
        "destination_entry_frame_id",
    }
    leaks = [
        {"result_id": row["result_id"], "keys": sorted(forbidden.intersection(row))}
        for row in rows
        if forbidden.intersection(row)
    ]
    requested_leaks = [
        {
            "result_id": row["result_id"],
            "keys": sorted(forbidden.intersection(row.get("requested_evidence", {}))),
        }
        for row in rows
        if forbidden.intersection(row.get("requested_evidence", {}))
    ]
    return [
        pass_check(
            "evidence.no_default_m1_evidence_leak",
            "query results include only requested evidence, not hardcoded M1 evidence",
            {"result_count": len(rows)},
        )
        if rows and not leaks and not requested_leaks
        else fail_check(
            "evidence.no_default_m1_evidence_leak",
            "M1-specific evidence leaked into second-plan public rows",
            {"row_leaks": leaks[:10], "requested_leaks": requested_leaks[:10]},
        )
    ]


def public_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "classification": row["classification"],
            "match_id": row["match_id"],
            "period": row["period"],
            "anchor_frame_id": row["anchor_frame_id"],
            "requested_evidence": row.get("requested_evidence"),
        }
        for row in rows
    ]


def rename_node(payload: dict[str, Any], old: str, new: str) -> None:
    for node in payload["draft_plan"]["nodes"]:
        if node["node_id"] == old:
            node["node_id"] = new


def rename_signal_refs(payload: dict[str, Any], old: str, new: str) -> None:
    for node in payload["draft_plan"]["nodes"]:
        if "input" in node and node["input"].get("source_node_id") == old:
            node["input"]["source_node_id"] = new
        for ref in node.get("inputs", {}).values():
            if ref.get("source_node_id") == old:
                ref["source_node_id"] = new
    for request in payload["draft_plan"]["requested_evidence"]:
        if request["source"].get("source_node_id") == old:
            request["source"]["source_node_id"] = new
    anchor_source = payload["draft_plan"].get("anchor_source")
    if anchor_source and anchor_source.get("source_node_id") == old:
        anchor_source["source_node_id"] = new


def execute_payload(payload: dict[str, Any]) -> Any:
    bound = bind_document(TacticalQueryDocument.model_validate(payload))
    return TacticalQueryExecutor().execute(bound)


def plan_payload() -> dict[str, Any]:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def main() -> None:
    report = build_report()
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
