"""Verify M1.1R Gate R3: predicate, classification, evidence, and unknown semantics."""

from __future__ import annotations

import ast
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tqe.runtime.binder import bind_document, bind_document_from_path
from tqe.runtime.executor import (
    PeriodState,
    RuntimeParameters,
    TacticalQueryExecutor,
    apply_result_semantics,
    execution_result_rows,
    predicate_persists_for,
    typed_number,
)
from tqe.runtime.ir import (
    BoundPredicateNode,
    ExecutionStatus,
    PredicateTrace,
    TacticalQueryDocument,
    Unit,
    UnknownEvidencePolicy,
)
from tqe.runtime.values import RuntimeValue

PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")
EXECUTOR_PATH = Path("src/tqe/runtime/executor.py")
REPORT_PATH = Path("artifacts/m1.1/gate-r3-verification-report.json")


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
    bound = bind_document_from_path(PLAN_PATH)
    executor = TacticalQueryExecutor()
    execution = executor.execute(bound)
    rows = execution_result_rows(execution)
    trace_payload = [
        trace.model_dump(mode="json", exclude_none=True) for trace in execution.predicate_traces
    ]

    checks.extend(validate_runtime_execution(bound, execution, rows, trace_payload))
    checks.extend(validate_predicate_source_contract())
    checks.extend(validate_classification_rules_change_behavior())
    checks.extend(validate_requested_evidence_change_behavior())
    checks.extend(validate_unknown_policy_behavior(bound))
    checks.extend(validate_tri_state_persists_for(bound))

    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.1R",
        "gate": "Gate_R3_generic_predicate_classification_evidence_unknown",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "execution": {
            "plan_hash": bound.plan_hash,
            "bound_plan_hash": bound.bound_plan_hash,
            "execution_id": execution.execution_id,
            "status": execution.status.value,
            "result_count": len(rows),
            "predicate_trace_count": len(trace_payload),
            "runtime_trace_hash": execution.provenance.get("runtime_trace_hash"),
        },
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    return report


def validate_runtime_execution(
    bound: Any,
    execution: Any,
    rows: list[dict[str, Any]],
    traces: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rule_predicates = {
        predicate_id
        for rule in bound.classification_rules
        for predicate_id in rule.predicate_ids
    }
    result_ids = {str(row["result_id"]) for row in rows}
    trace_ids = {str(trace.get("source_evidence", {}).get("result_id", "")) for trace in traces}
    missing_requested = [
        row["result_id"]
        for row in rows
        if not isinstance(row.get("requested_evidence"), dict)
        or sorted(row["requested_evidence"]) != expected_requested_evidence_keys(bound)
    ]
    missing_rule_matches = [
        row["result_id"]
        for row in rows
        if str(row.get("classification")) != "STOPPAGE"
        and row.get("matched_classification_rules") != [row.get("classification")]
    ]
    classification_labels = {row["classification"] for row in rows}
    return [
        pass_check(
            "runtime.approved_plan_executes",
            "approved plan executes with deterministic traces and requested evidence",
            {
                "status": execution.status.value,
                "result_count": len(rows),
                "trace_count": len(traces),
                "trace_hash": execution.provenance.get("runtime_trace_hash"),
            },
        )
        if execution.status == ExecutionStatus.PASS
        and len(rows) == bound.max_results
        and bool(execution.provenance.get("runtime_trace_hash"))
        and result_ids.issubset(trace_ids)
        else fail_check(
            "runtime.approved_plan_executes",
            "approved plan did not produce the expected R3 runtime shape",
            {
                "status": execution.status.value,
                "result_count": len(rows),
                "max_results": bound.max_results,
                "trace_count": len(traces),
            },
        ),
        pass_check(
            "runtime.classification_rules_match_predicate_outputs",
            "classification-rule labels are attached from predicate trace outputs",
            {"labels": sorted(classification_labels), "rule_predicates": sorted(rule_predicates)},
        )
        if not missing_rule_matches and rule_predicates
        else fail_check(
            "runtime.classification_rules_match_predicate_outputs",
            "one or more results lack the expected matched classification rule",
            {"sample": missing_rule_matches[:10], "rule_predicates": sorted(rule_predicates)},
        ),
        pass_check(
            "runtime.requested_evidence_projected",
            "requested evidence projection is present and plan-shaped",
            {"requested_keys": expected_requested_evidence_keys(bound)},
        )
        if not missing_requested
        else fail_check(
            "runtime.requested_evidence_projected",
            "one or more results do not match requested evidence projection",
            {"sample": missing_requested[:10]},
        ),
    ]


def validate_predicate_source_contract() -> list[dict[str, Any]]:
    tree = ast.parse(EXECUTOR_PATH.read_text(encoding="utf-8"))
    operator_function_names = {
        "predicate_gt",
        "predicate_gte",
        "predicate_lte",
        "predicate_eq",
        "predicate_neq",
        "predicate_persists_for",
        "predicate_exists",
        "predicate_count_at_least",
    }
    predicate_functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in operator_function_names
    ]
    branch_hits: list[dict[str, Any]] = []
    resolver_misses: list[str] = []
    forbidden_attrs = {"node_id", "source_node_id"}
    for function in predicate_functions:
        uses_runtime_resolver = False
        for node in ast.walk(function):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", "")
                if name in {"source_runtime_value", "numeric_source_values"}:
                    uses_runtime_resolver = True
            if isinstance(node, ast.If):
                attrs = {
                    child.attr
                    for child in ast.walk(node.test)
                    if isinstance(child, ast.Attribute)
                }
                hits = sorted(attrs & forbidden_attrs)
                if hits:
                    branch_hits.append(
                        {"function": function.name, "line": node.lineno, "attrs": hits}
                    )
        if not uses_runtime_resolver:
            resolver_misses.append(function.name)

    return [
        pass_check(
            "predicate_source.no_node_id_branches",
            "predicate implementations do not branch on node identity",
            {"checked_functions": [function.name for function in predicate_functions]},
        )
        if not branch_hits
        else fail_check(
            "predicate_source.no_node_id_branches",
            "predicate implementation branches on node identity",
            {"hits": branch_hits},
        ),
        pass_check(
            "predicate_source.uses_typed_runtime_values",
            "predicate implementations consume typed runtime values through resolver helpers",
            {"checked_functions": [function.name for function in predicate_functions]},
        )
        if not resolver_misses
        else fail_check(
            "predicate_source.uses_typed_runtime_values",
            "predicate implementations bypass typed runtime value resolvers",
            {"functions": resolver_misses},
        ),
    ]


def validate_classification_rules_change_behavior() -> list[dict[str, Any]]:
    payload = clone_plan_payload()
    switched_rule = next(
        rule for rule in payload["draft_plan"]["classification_rules"] if rule["label"] == "SWITCHED"
    )
    payload["draft_plan"]["classification_mode"] = "partial_declared"
    payload["draft_plan"]["classification_rules"] = [switched_rule]
    payload["default_invocation"]["max_results"] = 50
    document = TacticalQueryDocument.model_validate(payload)
    bound = bind_document(document)
    execution = TacticalQueryExecutor().execute(bound)
    rows = execution_result_rows(execution)
    labels = {row["classification"] for row in rows}
    bad_rule_matches = [
        row["result_id"]
        for row in rows
        if row.get("matched_classification_rules") != ["SWITCHED"]
    ]
    return [
        pass_check(
            "classification_rules.change_behavior",
            "narrowing classification rules narrows result classifications",
            {"count": len(rows), "labels": sorted(labels)},
        )
        if rows and labels == {"SWITCHED"} and not bad_rule_matches
        else fail_check(
            "classification_rules.change_behavior",
            "classification-rule mutation did not change runtime behavior",
            {
                "count": len(rows),
                "labels": sorted(labels),
                "bad_rule_match_sample": bad_rule_matches[:10],
            },
        )
    ]


def validate_requested_evidence_change_behavior() -> list[dict[str, Any]]:
    payload = clone_plan_payload()
    payload["draft_plan"]["requested_evidence"] = [
        {
            "source": {"source_node_id": "signed_shift", "output_name": "signed_shift"},
            "field": "signed_shift_metres",
        }
    ]
    payload["default_invocation"]["max_results"] = 5
    document = TacticalQueryDocument.model_validate(payload)
    bound = bind_document(document)
    execution = TacticalQueryExecutor().execute(bound)
    rows = execution_result_rows(execution)
    keys = {
        tuple(sorted(row.get("requested_evidence", {}).keys()))
        for row in rows
    }
    return [
        pass_check(
            "requested_evidence.change_behavior",
            "changing requested evidence changes result evidence projection",
            {"projection_keys": [list(item) for item in sorted(keys)]},
        )
        if rows and keys == {("signed_shift.signed_shift_metres",)}
        else fail_check(
            "requested_evidence.change_behavior",
            "requested-evidence mutation did not change projection",
            {"projection_keys": [list(item) for item in sorted(keys)]},
        )
    ]


def validate_unknown_policy_behavior(bound: Any) -> list[dict[str, Any]]:
    result = {"result_id": "synthetic_result", "classification": "SWITCHED"}
    trace = PredicateTrace(
        predicate_id="wide_entry_persists",
        status="UNKNOWN",
        source_evidence={"result_id": "synthetic_result"},
    )
    include_results, include_traces, include_status = apply_result_semantics(
        results=[dict(result)],
        trace_records=[trace],
        bound_plan=bound.model_copy(
            update={"unknown_evidence_policy": UnknownEvidencePolicy.INCLUDE_WITH_WARNING}
        ),
    )
    exclude_results, exclude_traces, exclude_status = apply_result_semantics(
        results=[dict(result)],
        trace_records=[trace],
        bound_plan=bound.model_copy(
            update={"unknown_evidence_policy": UnknownEvidencePolicy.EXCLUDE_CANDIDATE}
        ),
    )
    invalid_results, invalid_traces, invalid_status = apply_result_semantics(
        results=[dict(result)],
        trace_records=[trace],
        bound_plan=bound.model_copy(
            update={"unknown_evidence_policy": UnknownEvidencePolicy.INVALIDATE_EXECUTION}
        ),
    )
    return [
        pass_check(
            "unknown_policy.changes_behavior",
            "unknown policy include/exclude/invalidate paths diverge",
            {
                "include": {"status": include_status.value, "result_count": len(include_results), "trace_count": len(include_traces)},
                "exclude": {"status": exclude_status.value, "result_count": len(exclude_results), "trace_count": len(exclude_traces)},
                "invalidate": {"status": invalid_status.value, "result_count": len(invalid_results), "trace_count": len(invalid_traces)},
            },
        )
        if include_status == ExecutionStatus.PASS
        and len(include_results) == 1
        and exclude_status == ExecutionStatus.PASS
        and not exclude_results
        and not exclude_traces
        and invalid_status == ExecutionStatus.INCOMPLETE
        and len(invalid_results) == 1
        else fail_check(
            "unknown_policy.changes_behavior",
            "unknown policy did not affect result semantics",
            {
                "include": {"status": include_status.value, "result_count": len(include_results), "trace_count": len(include_traces)},
                "exclude": {"status": exclude_status.value, "result_count": len(exclude_results), "trace_count": len(exclude_traces)},
                "invalidate": {"status": invalid_status.value, "result_count": len(invalid_results), "trace_count": len(invalid_traces)},
            },
        )
    ]


def validate_tri_state_persists_for(bound: Any) -> list[dict[str, Any]]:
    node = next(
        node
        for node in bound.nodes
        if isinstance(node, BoundPredicateNode) and node.operator.name == "persists_for"
    ).model_copy(update={"duration": typed_number(0.4, Unit.SECOND)})
    source_output = node.input_type
    state = synthetic_period_state()
    values = [True, True, None, True, True, True, False, True]
    state.signals[node.input.source_node_id] = {
        node.input.output_name: values,
        "predicate_facts": [
            {
                "status": "PASS" if value is True else ("FAIL" if value is False else "UNKNOWN"),
                "value": None,
                "threshold": None,
                "unit": Unit.NONE.value,
                "frame_id": int(frame_id),
                "window": None,
                "source_evidence": {"source_node_id": "synthetic_bool"},
            }
            for frame_id, value in zip(state.frame_ids, values, strict=True)
        ],
    }
    state.runtime_values[node.input.source_node_id] = {
        node.input.output_name: RuntimeValue(output=source_output, value=values)
    }
    predicate_persists_for(state, node)
    episodes = state.signals[node.node_id]["episodes"]
    windows = [(episode["start_frame_id"], episode["end_frame_id"]) for episode in episodes]
    return [
        pass_check(
            "persists_for.tri_state_boolean_signal",
            "persists_for consumes True/False/UNKNOWN frame signal and emits episodes without crossing UNKNOWN",
            {"windows": windows, "episode_count": len(episodes)},
        )
        if windows == [(100, 101), (103, 105)]
        and all("_predicate_status" in episode for episode in episodes)
        else fail_check(
            "persists_for.tri_state_boolean_signal",
            "persists_for did not respect tri-state boolean semantics",
            {"windows": windows, "episodes": episodes},
        )
    ]


def expected_requested_evidence_keys(bound: Any) -> list[str]:
    return sorted(
        f"{request.source.source_node_id}.{request.field}"
        for request in bound.requested_evidence
    )


def clone_plan_payload() -> dict[str, Any]:
    return deepcopy(json.loads(PLAN_PATH.read_text(encoding="utf-8")))


def synthetic_period_state() -> PeriodState:
    return PeriodState(
        match_id="synthetic",
        period="firstHalf",
        params=RuntimeParameters(values={"analysis_rate_hz": 5}),
        recipe_id="synthetic_recipe",
        recipe_version="1.0.0",
        perspective_team_role="home",
        perspective_team_id="home_team",
        defending_team_role="away",
        defending_team_id="away_team",
        canonical_root=Path("."),
        raw_tracking=Path("."),
        positions=pd.DataFrame(),
        frame_ids=np.arange(100, 108, dtype=np.int64),
        ball_y=np.array([], dtype=float),
        possession_role=np.array([], dtype=object),
        ball_alive=np.array([], dtype=bool),
        defender_count=pd.Series(dtype=int),
        defender_centroid_y=pd.Series(dtype=float),
    )


def main() -> int:
    report = build_report()
    print(f"Wrote {REPORT_PATH}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
