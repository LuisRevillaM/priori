"""Verify M1.1S Gate S2: node execution contract."""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document_from_path
from tqe.runtime.executor import (
    TacticalQueryExecutor,
    catalog_input_value,
    execution_result_rows,
    predicate_eq,
    predicate_exists,
    predicate_gt,
    predicate_gte,
    predicate_lte,
    predicate_neq,
    predicate_persists_for,
    primitive_outcome_classification,
    primitive_relation_destination_entry_classification,
    primitive_signed_lateral_shift,
    record_runtime_values,
    relation_anchor_results,
    runtime_parameters,
)
from tqe.runtime.ir import BoundCatalogNode, NodeKind
from tqe.runtime.values import FrameSignal, RuntimeValue

REPORT_PATH = Path("artifacts/m1.1/gate-s2-verification-report.json")
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
    checks.extend(validate_generic_operators_have_no_candidate_side_channel())
    checks.extend(validate_downstream_nodes_use_catalog_inputs())
    checks.extend(validate_declared_input_substitution_changes_shift_output())
    checks.extend(validate_approved_plan_parity())
    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.1S",
        "gate": "Gate_S2_node_execution_contract",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    return report


def validate_generic_operators_have_no_candidate_side_channel() -> list[dict[str, Any]]:
    operators = [
        predicate_gt,
        predicate_gte,
        predicate_lte,
        predicate_eq,
        predicate_neq,
        predicate_persists_for,
        predicate_exists,
    ]
    forbidden = [
        "state.candidates",
        "\"candidates\"",
        "'candidates'",
        "block_shift",
        "wide_entry",
        "signed_shift_series",
        "minimum_shift_metres",
        "enough_defenders",
    ]
    violations: dict[str, list[str]] = {}
    for operator in operators:
        source = inspect.getsource(operator)
        hits = [token for token in forbidden if token in source]
        if hits:
            violations[operator.__name__] = hits
    return [
        pass_check(
            "operators.no_query_specific_candidate_branches",
            "generic predicate operators do not branch on M1 candidate state or query-specific fields",
            {"operator_count": len(operators)},
        )
        if not violations
        else fail_check(
            "operators.no_query_specific_candidate_branches",
            "generic predicate operators still reference candidate side channels or query-specific fields",
            {"violations": violations},
        )
    ]


def validate_downstream_nodes_use_catalog_inputs() -> list[dict[str, Any]]:
    required = {
        "primitive_signed_lateral_shift": (
            primitive_signed_lateral_shift,
            ["possession_episodes", "entry_episodes", "defensive_centroid"],
        ),
        "primitive_outcome_classification": (
            primitive_outcome_classification,
            ["accepted_shift_episodes"],
        ),
        "relation_anchor_results": (relation_anchor_results, ["anchors"]),
        "primitive_relation_destination_entry_classification": (
            primitive_relation_destination_entry_classification,
            ["relation_episodes"],
        ),
    }
    missing: dict[str, list[str]] = {}
    global_signal_reads: dict[str, list[str]] = {}
    for name, (function, input_names) in required.items():
        source = inspect.getsource(function)
        function_missing = [
            input_name
            for input_name in input_names
            if f'"{input_name}"' not in source or "catalog_input_value" not in source
        ]
        if function_missing:
            missing[name] = function_missing
        forbidden_reads = [token for token in ("state.signals.get",) if token in source]
        if forbidden_reads:
            global_signal_reads[name] = forbidden_reads
    return [
        pass_check(
            "nodes.consume_declared_runtime_inputs",
            "downstream nodes consume their declared inputs through RuntimeValue resolution",
            {"checked_nodes": sorted(required)},
        )
        if not missing and not global_signal_reads
        else fail_check(
            "nodes.consume_declared_runtime_inputs",
            "one or more downstream nodes still bypass declared RuntimeValue inputs",
            {"missing_catalog_inputs": missing, "global_signal_reads": global_signal_reads},
        )
    ]


def validate_declared_input_substitution_changes_shift_output() -> list[dict[str, Any]]:
    bound = bind_document_from_path(APPROVED_PLAN_PATH)
    params = runtime_parameters(bound)
    executor = TacticalQueryExecutor()
    original = execute_until_signed_shift(executor, bound, params)
    substituted = execute_until_node(
        executor=executor,
        bound=bound,
        params=params,
        stop_before_node_id="signed_shift",
    )
    centroid_value = catalog_input_value(
        substituted,
        next(node for node in bound.nodes if getattr(node, "node_id", None) == "signed_shift"),
        "defensive_centroid",
    )
    if not isinstance(centroid_value.value, FrameSignal):
        return [
            fail_check(
                "nodes.compatible_input_substitution_changes_semantic_output",
                "defensive centroid did not produce a FrameSignal for substitution",
                {"actual_type": type(centroid_value.value).__name__},
            )
        ]
    signal = centroid_value.value
    scaled = FrameSignal(
        frame_ids=signal.frame_ids,
        values=[
            None if value is None else round(float(value) * 0.5, 6)
            for value in signal.values
        ],
        unknown_mask=signal.unknown_mask,
        unit=signal.unit,
        entity_scope=signal.entity_scope,
    )
    substituted.runtime_values["defensive_centroid"]["centroid_y"] = RuntimeValue(
        output=centroid_value.output,
        value=scaled,
        provenance={**centroid_value.provenance, "substitution_probe": "centroid_y_scaled_0.5"},
    )
    signed_shift_node = next(node for node in bound.nodes if node.node_id == "signed_shift")
    primitive_signed_lateral_shift(substituted, signed_shift_node)
    record_runtime_values(substituted, signed_shift_node)
    original_values = original.runtime_values["signed_shift"]["signed_shift"].frame_values
    substituted_values = substituted.runtime_values["signed_shift"]["signed_shift"].frame_values
    changed = [
        (left, right)
        for left, right in zip(original_values, substituted_values, strict=False)
        if left is not None and right is not None and abs(float(left) - float(right)) > 0.001
    ]
    return [
        pass_check(
            "nodes.compatible_input_substitution_changes_semantic_output",
            "substituting a compatible defensive_centroid RuntimeValue changes signed_lateral_shift output",
            {
                "original_count": len(original_values),
                "substituted_count": len(substituted_values),
                "changed_value_count": len(changed),
            },
        )
        if changed
        else fail_check(
            "nodes.compatible_input_substitution_changes_semantic_output",
            "signed_lateral_shift output did not change after declared input substitution",
            {"original_count": len(original_values), "substituted_count": len(substituted_values)},
        )
    ]


def validate_approved_plan_parity() -> list[dict[str, Any]]:
    bound = bind_document_from_path(APPROVED_PLAN_PATH)
    execution = TacticalQueryExecutor().execute(bound)
    rows = execution_result_rows(execution)
    return [
        pass_check(
            "approved_plan.frozen_parity_preserved",
            "approved plan still returns the frozen 180 results and five traces per result",
            {"result_count": len(rows), "trace_count": len(execution.predicate_traces)},
        )
        if len(rows) == 180 and len(execution.predicate_traces) == 900
        else fail_check(
            "approved_plan.frozen_parity_preserved",
            "approved plan no longer matches frozen result/trace cardinality",
            {"result_count": len(rows), "trace_count": len(execution.predicate_traces)},
        )
    ]


def execute_until_signed_shift(
    executor: TacticalQueryExecutor,
    bound: Any,
    params: Any,
) -> Any:
    return execute_until_node(
        executor=executor,
        bound=bound,
        params=params,
        stop_after_node_id="signed_shift",
    )


def execute_until_node(
    *,
    executor: TacticalQueryExecutor,
    bound: Any,
    params: Any,
    stop_before_node_id: str | None = None,
    stop_after_node_id: str | None = None,
) -> Any:
    state = executor._period_state(  # noqa: SLF001 - verifier exercises node contract directly.
        match_id="J03WQQ",
        period="firstHalf",
        perspective_team_role=bound.perspective_team_role,
        recipe_id=bound.recipe_id,
        recipe_version=bound.recipe_version,
        params=params,
    )
    for node in bound.nodes:
        if node.node_id == stop_before_node_id:
            return state
        if isinstance(node, BoundCatalogNode) and node.kind == NodeKind.PRIMITIVE:
            implementation = executor.primitives[node.catalog_ref]
        elif isinstance(node, BoundCatalogNode) and node.kind == NodeKind.RELATION:
            implementation = executor.relations[node.catalog_ref]
        else:
            implementation = executor.predicates[node.operator.name]
        implementation(state, node)
        record_runtime_values(state, node)
        if node.node_id == stop_after_node_id:
            return state
    return state


def main() -> None:
    report = build_report()
    print(f"Wrote {REPORT_PATH}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
