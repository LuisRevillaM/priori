"""Verify M1.1S Gate S6: second real generic plan and relation proof."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import (
    TacticalQueryExecutor,
    execute_plan_from_path,
    execution_result_rows,
    runtime_parameters,
)
from tqe.runtime.ir import BoundCatalogNode, ExecutionStatus, NodeKind, TacticalQueryDocument

PLAN_PATH = Path("config/query-plans/possession_corridor_availability.experimental.v1.json")
REPORT_PATH = Path("artifacts/m1.1/gate-s6-verification-report.json")


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
    bound, execution = execute_plan_from_path(PLAN_PATH)
    rows = execution_result_rows(execution)

    checks.extend(validate_real_second_plan_rows(execution, rows))
    checks.extend(validate_non_block_shift_plan_shape(bound, rows))
    checks.extend(validate_possession_anchor_relation(bound))
    checks.extend(validate_generic_classification(rows, execution.predicate_traces))
    checks.extend(validate_declared_evidence(rows))
    checks.extend(validate_period_runtime_state(bound))
    checks.extend(validate_determinism())
    checks.extend(validate_gate_d_relation_precondition())

    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.1S",
        "gate": "Gate_S6_second_real_plan_relation_proof",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "execution": {
            "plan_path": str(PLAN_PATH),
            "execution_id": execution.execution_id,
            "status": execution.status.value,
            "result_count": len(rows),
            "trace_count": len(execution.predicate_traces),
            "compatibility_profile": execution.provenance.get("compatibility_profile"),
            "by_label": dict(sorted(Counter(str(row["classification"]) for row in rows).items())),
        },
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    return report


def validate_real_second_plan_rows(execution: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = Counter(str(row["classification"]) for row in rows)
    return [
        pass_check(
            "second_plan.real_generic_rows",
            "non-block-shift generic plan emits real QueryResult rows",
            {"result_count": len(rows), "labels": dict(sorted(labels.items()))},
        )
        if execution.status == ExecutionStatus.PASS
        and execution.provenance.get("compatibility_profile") == "generic"
        and len(rows) > 0
        and set(labels) == {"PROGRESSIVE_CORRIDOR_AVAILABLE"}
        else fail_check(
            "second_plan.real_generic_rows",
            "second plan did not emit expected generic rows",
            {
                "status": execution.status.value,
                "result_count": len(rows),
                "labels": dict(sorted(labels.items())),
                "compatibility_profile": execution.provenance.get("compatibility_profile"),
            },
        )
    ]


def validate_non_block_shift_plan_shape(bound: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    forbidden_node_ids = {
        "ball_lateral",
        "wide_entry_threshold",
        "wide_entry_persists",
        "defensive_centroid",
        "signed_shift",
        "shift_threshold",
        "shift_persists",
        "outcome",
        "not_stoppage",
        "destination_entry",
    }
    forbidden_catalog_refs = {
        "ball_lateral_fraction",
        "defensive_outfield_centroid",
        "signed_lateral_shift",
        "outcome_classification",
        "relation_destination_entry_classification",
    }
    node_ids = {node.node_id for node in bound.nodes}
    catalog_refs = {
        node.catalog_ref
        for node in bound.nodes
        if isinstance(node, BoundCatalogNode)
    }
    forbidden_fields = {"block_shift_score", "wide_entry_frame_id", "signed_shift_metres"}
    row_violations = [
        row["result_id"]
        for row in rows
        if forbidden_fields.intersection(row)
    ]
    return [
        pass_check(
            "second_plan.non_block_shift_shape",
            "second plan does not use the M1 wide-entry/block-shift/outcome spine",
            {
                "node_ids": sorted(node_ids),
                "catalog_refs": sorted(catalog_refs),
                "result_count": len(rows),
            },
        )
        if not forbidden_node_ids.intersection(node_ids)
        and not forbidden_catalog_refs.intersection(catalog_refs)
        and not row_violations
        else fail_check(
            "second_plan.non_block_shift_shape",
            "second plan still uses M1-shaped nodes or fields",
            {
                "forbidden_node_ids": sorted(forbidden_node_ids.intersection(node_ids)),
                "forbidden_catalog_refs": sorted(forbidden_catalog_refs.intersection(catalog_refs)),
                "row_violations": row_violations[:10],
            },
        )
    ]


def validate_possession_anchor_relation(bound: Any) -> list[dict[str, Any]]:
    relation_nodes = [
        node
        for node in bound.nodes
        if isinstance(node, BoundCatalogNode) and node.kind == NodeKind.RELATION
    ]
    valid = (
        len(relation_nodes) == 1
        and relation_nodes[0].catalog_ref == "geometric_progressive_corridor_from_anchor_set"
        and relation_nodes[0].inputs["anchors"].source_node_id == "possession"
        and relation_nodes[0].inputs["anchors"].output_name == "anchors"
        and bound.anchor_source.source_node_id == "possession"
        and bound.anchor_source.output_name == "anchors"
    )
    return [
        pass_check(
            "second_plan.possession_anchor_relation",
            "corridor relation executes from a non-M1 possession anchor set",
            {
                "relation_node_count": len(relation_nodes),
                "anchor_source": f"{bound.anchor_source.source_node_id}.{bound.anchor_source.output_name}",
            },
        )
        if valid
        else fail_check(
            "second_plan.possession_anchor_relation",
            "corridor relation is not wired to possession anchors",
            {"relation_node_count": len(relation_nodes)},
        )
    ]


def validate_generic_classification(rows: list[dict[str, Any]], traces: list[Any]) -> list[dict[str, Any]]:
    matched = [
        row
        for row in rows
        if row.get("matched_classification_rules") == ["PROGRESSIVE_CORRIDOR_AVAILABLE"]
    ]
    trace_predicates = {trace.predicate_id for trace in traces}
    return [
        pass_check(
            "second_plan.rule_driven_classification",
            "second plan classifications come from declared generic rules and predicate traces",
            {"matched_count": len(matched), "trace_predicates": sorted(trace_predicates)},
        )
        if rows and len(matched) == len(rows) and trace_predicates == {"has_progressive_corridor"}
        else fail_check(
            "second_plan.rule_driven_classification",
            "second plan rows are not fully rule-driven",
            {
                "matched_count": len(matched),
                "result_count": len(rows),
                "trace_predicates": sorted(trace_predicates),
            },
        )
    ]


def validate_declared_evidence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    required = {
        "relation_id",
        "target_player_id",
        "destination_region",
        "relation_duration_seconds",
        "minimum_clearance_m",
    }
    failures = [
        row["result_id"]
        for row in rows
        if set(row.get("requested_evidence", {})) != required
        or any(value is None for value in row.get("requested_evidence", {}).values())
        or any("." in key for key in row.get("requested_evidence", {}))
    ]
    return [
        pass_check(
            "second_plan.declared_alias_evidence",
            "second plan requested evidence uses stable aliases from declared relation outputs",
            {"result_count": len(rows), "aliases": sorted(required)},
        )
        if rows and not failures
        else fail_check(
            "second_plan.declared_alias_evidence",
            "second plan evidence is missing, null, or node-ID shaped",
            {"failure_sample": failures[:10], "result_count": len(rows)},
        )
    ]


def validate_period_runtime_state(bound: Any) -> list[dict[str, Any]]:
    executor = TacticalQueryExecutor()
    params = runtime_parameters(bound)
    state = executor._execute_period(  # noqa: SLF001 - verifier checks the runtime contract.
        bound_plan=bound,
        match_id=bound.match_ids[0],
        period=bound.periods[0],
        params=params,
    )
    relation_value = state.runtime_values.get("progressive_corridor", {}).get("episodes")
    episode_count = (
        len(relation_value.value)
        if relation_value is not None and isinstance(relation_value.value, list)
        else 0
    )
    return [
        pass_check(
            "second_plan.no_terminal_state_accepted",
            "second plan relation episodes are declared runtime output, not terminal state.accepted handoff",
            {"episode_count": episode_count, "accepted_count": len(state.accepted)},
        )
        if episode_count > 0 and not state.accepted
        else fail_check(
            "second_plan.no_terminal_state_accepted",
            "second plan used terminal accepted handoff or produced no relation episodes",
            {"episode_count": episode_count, "accepted_count": len(state.accepted)},
        )
    ]


def validate_determinism() -> list[dict[str, Any]]:
    first_rows = execution_result_rows(execute_plan_from_path(PLAN_PATH)[1])
    second_rows = execution_result_rows(execute_plan_from_path(PLAN_PATH)[1])
    first_ids = [row["result_id"] for row in first_rows]
    second_ids = [row["result_id"] for row in second_rows]
    return [
        pass_check(
            "second_plan.deterministic_ids_order",
            "second plan result IDs and ordering are deterministic",
            {"result_count": len(first_ids)},
        )
        if first_ids == second_ids and first_ids
        else fail_check(
            "second_plan.deterministic_ids_order",
            "second plan result IDs or ordering changed across runs",
            {"first": first_ids[:10], "second": second_ids[:10]},
        )
    ]


def validate_gate_d_relation_precondition() -> list[dict[str, Any]]:
    path = Path("artifacts/m1.1/gate-d-verification-report.json")
    if not path.exists():
        return [fail_check("relation.capability_controls", "Gate D relation proof report is missing")]
    report = json.loads(path.read_text(encoding="utf-8"))
    return [
        pass_check(
            "relation.capability_controls",
            "existing relation capability proof remains passing",
            {"summary": report.get("summary")},
        )
        if report.get("status") == "pass"
        else fail_check(
            "relation.capability_controls",
            "existing relation capability proof is not passing",
            {"status": report.get("status"), "summary": report.get("summary")},
        )
    ]


def plan_payload() -> dict[str, Any]:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def main() -> None:
    bind_document(TacticalQueryDocument.model_validate(plan_payload()))
    report = build_report()
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
