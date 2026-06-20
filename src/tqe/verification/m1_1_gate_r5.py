"""Verify M1.1R Gate R5: architecture proof and parity."""

from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.binder import (
    BindError,
    bind_document,
    bind_document_from_path,
    bind_error_codes,
)
from tqe.runtime.catalog import default_catalog
from tqe.runtime.executor import (
    TacticalQueryExecutor,
    apply_result_semantics,
    execution_result_rows,
)
from tqe.runtime.ir import (
    ExecutionStatus,
    PredicateTrace,
    TacticalQueryDocument,
    UnknownEvidencePolicy,
)
from tqe.verification.m1_1_gate_b import build_report as build_gate_b_report

APPROVED_PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")
EXPERIMENTAL_PLAN_PATH = Path("config/query-plans/opposite_corridor_after_shift.experimental.v1.json")
EXECUTOR_PATH = Path("src/tqe/runtime/executor.py")
REPORT_PATH = Path("artifacts/m1.1/gate-r5-verification-report.json")


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
    approved_bound = bind_document_from_path(APPROVED_PLAN_PATH)
    approved_execution = TacticalQueryExecutor().execute(approved_bound)
    approved_rows = execution_result_rows(approved_execution)

    checks.extend(validate_node_id_opacity(approved_rows))
    checks.extend(validate_required_dependency_failure())
    checks.extend(validate_capability_execution())
    checks.extend(validate_plan_driven_semantics())
    checks.extend(validate_executor_source_opacity())
    checks.extend(validate_cache_independent_reproduction(approved_rows))
    checks.extend(validate_m1_parity())

    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.1R",
        "gate": "Gate_R5_architecture_proof_and_parity",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    return report


def validate_node_id_opacity(approved_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload = renamed_node_payload(clone_plan_payload(APPROVED_PLAN_PATH))
    bound = bind_document(TacticalQueryDocument.model_validate(payload))
    execution = TacticalQueryExecutor().execute(bound)
    renamed_rows = execution_result_rows(execution)
    original_normalized = [normalize_result_for_node_rename(row) for row in approved_rows]
    renamed_normalized = [normalize_result_for_node_rename(row) for row in renamed_rows]
    return [
        pass_check(
            "architecture.node_id_rename_opacity",
            "renaming every approved-plan node while preserving references leaves runtime results unchanged",
            {
                "result_count": len(renamed_rows),
                "renamed_plan_hash": bound.plan_hash,
                "renamed_bound_plan_hash": bound.bound_plan_hash,
            },
        )
        if execution.status == ExecutionStatus.PASS and original_normalized == renamed_normalized
        else fail_check(
            "architecture.node_id_rename_opacity",
            "node-id rename changed approved-plan runtime behavior",
            {
                "status": execution.status.value,
                "original_count": len(approved_rows),
                "renamed_count": len(renamed_rows),
            },
        )
    ]


def validate_required_dependency_failure() -> list[dict[str, Any]]:
    payload = clone_plan_payload(APPROVED_PLAN_PATH)
    for node in payload["draft_plan"]["nodes"]:
        if node.get("catalog_ref") == "signed_lateral_shift":
            del node["inputs"]["possession_episodes"]
            break
    try:
        bind_document(TacticalQueryDocument.model_validate(payload))
    except BindError as error:
        codes = sorted(bind_error_codes(error))
        return [
            pass_check(
                "binder.removing_required_dependency_fails",
                "removing signed_lateral_shift.possession_episodes fails binding",
                {"codes": codes},
            )
            if "missing_node_input" in codes
            else fail_check(
                "binder.removing_required_dependency_fails",
                "invalid dependency removal failed with the wrong issue code",
                {"codes": codes},
            )
        ]
    return [
        fail_check(
            "binder.removing_required_dependency_fails",
            "binder accepted a plan missing a required dependency",
        )
    ]


def validate_capability_execution() -> list[dict[str, Any]]:
    approved_bound = bind_document_from_path(APPROVED_PLAN_PATH)
    experimental_bound = bind_document_from_path(EXPERIMENTAL_PLAN_PATH)
    simple_bound = bind_document(TacticalQueryDocument.model_validate(simple_non_block_shift_payload()))
    executor = TacticalQueryExecutor()
    executions = {
        "approved": executor.execute(approved_bound),
        "experimental": executor.execute(experimental_bound),
        "simple_non_block_shift": executor.execute(simple_bound),
    }
    plans = {
        "approved": approved_bound,
        "experimental": experimental_bound,
        "simple_non_block_shift": simple_bound,
    }
    coverage = capability_coverage(plans)
    catalog = default_catalog()
    advertised = {
        "primitives": sorted(entry.name for entry in catalog.primitives),
        "relations": sorted(entry.name for entry in catalog.relations),
        "operators": sorted(entry.name for entry in catalog.operators),
    }
    missing = {
        kind: sorted(set(names) - set(coverage[kind]))
        for kind, names in advertised.items()
    }
    execution_failures = [
        {
            "plan": name,
            "status": execution.status.value,
            "runtime_value_count": execution.provenance.get("runtime_value_count"),
            "result_count": len(execution.results),
        }
        for name, execution in executions.items()
        if execution.status != ExecutionStatus.PASS
        or int(execution.provenance.get("runtime_value_count", 0)) <= 0
    ]
    simple_rows = execution_result_rows(executions["simple_non_block_shift"])
    forbidden_simple_fields = {
        key
        for row in simple_rows
        for key in row
        if key in {"signed_shift_metres", "block_shift_score", "baseline_defensive_centroid_y_m"}
    }
    return [
        pass_check(
            "capabilities.all_advertised_execute",
            "approved, experimental, and simple valid plans execute every advertised capability",
            {
                "advertised": advertised,
                "coverage": coverage,
                "execution_summaries": {
                    name: {
                        "status": execution.status.value,
                        "result_count": len(execution.results),
                        "runtime_value_count": execution.provenance.get("runtime_value_count"),
                    }
                    for name, execution in executions.items()
                },
            },
        )
        if not any(missing.values()) and not execution_failures
        else fail_check(
            "capabilities.all_advertised_execute",
            "one or more advertised capabilities are not covered by successful plan execution",
            {"missing": missing, "execution_failures": execution_failures},
        ),
        pass_check(
            "architecture.second_simple_plan",
            "second simple plan executes without block-shift fields",
            {
                "status": executions["simple_non_block_shift"].status.value,
                "result_count": len(simple_rows),
                "runtime_value_count": executions["simple_non_block_shift"].provenance.get("runtime_value_count"),
            },
        )
        if executions["simple_non_block_shift"].status == ExecutionStatus.PASS and not forbidden_simple_fields
        else fail_check(
            "architecture.second_simple_plan",
            "simple plan did not execute cleanly or leaked block-shift fields",
            {"forbidden_fields": sorted(forbidden_simple_fields)},
        ),
    ]


def validate_plan_driven_semantics() -> list[dict[str, Any]]:
    executor = TacticalQueryExecutor()
    classification_payload = clone_plan_payload(APPROVED_PLAN_PATH)
    switched_rule = next(
        rule
        for rule in classification_payload["draft_plan"]["classification_rules"]
        if rule["label"] == "SWITCHED"
    )
    classification_payload["draft_plan"]["classification_mode"] = "partial_declared"
    classification_payload["draft_plan"]["classification_rules"] = [switched_rule]
    classification_payload["default_invocation"]["max_results"] = 50
    classification_execution = executor.execute(
        bind_document(TacticalQueryDocument.model_validate(classification_payload))
    )
    classification_rows = execution_result_rows(classification_execution)

    evidence_payload = clone_plan_payload(APPROVED_PLAN_PATH)
    evidence_payload["draft_plan"]["requested_evidence"] = [
        {
            "source": {"source_node_id": "signed_shift", "output_name": "signed_shift"},
            "field": "signed_shift_metres",
        }
    ]
    evidence_payload["default_invocation"]["max_results"] = 5
    evidence_execution = executor.execute(
        bind_document(TacticalQueryDocument.model_validate(evidence_payload))
    )
    evidence_rows = execution_result_rows(evidence_execution)
    evidence_keys = {
        tuple(sorted(row.get("requested_evidence", {}).keys()))
        for row in evidence_rows
    }

    bound = bind_document_from_path(APPROVED_PLAN_PATH)
    result = {"result_id": "synthetic_result", "classification": "SWITCHED"}
    trace = PredicateTrace(
        predicate_id="synthetic_predicate",
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
    labels = {row["classification"] for row in classification_rows}
    return [
        pass_check(
            "semantics.classification_rules_change_behavior",
            "changing classification rules changes runtime classifications",
            {"count": len(classification_rows), "labels": sorted(labels)},
        )
        if classification_rows and labels == {"SWITCHED"}
        else fail_check(
            "semantics.classification_rules_change_behavior",
            "classification rule mutation did not narrow runtime classifications",
            {"count": len(classification_rows), "labels": sorted(labels)},
        ),
        pass_check(
            "semantics.requested_evidence_changes_projection",
            "changing requested evidence changes result projection",
            {"projection_keys": [list(item) for item in sorted(evidence_keys)]},
        )
        if evidence_rows and evidence_keys == {("signed_shift.signed_shift_metres",)}
        else fail_check(
            "semantics.requested_evidence_changes_projection",
            "requested evidence mutation did not change projection",
            {"projection_keys": [list(item) for item in sorted(evidence_keys)]},
        ),
        pass_check(
            "semantics.unknown_policy_changes_behavior",
            "unknown policy include/exclude/invalidate paths diverge",
            {
                "include": {
                    "status": include_status.value,
                    "result_count": len(include_results),
                    "trace_count": len(include_traces),
                },
                "exclude": {
                    "status": exclude_status.value,
                    "result_count": len(exclude_results),
                    "trace_count": len(exclude_traces),
                },
                "invalidate": {
                    "status": invalid_status.value,
                    "result_count": len(invalid_results),
                    "trace_count": len(invalid_traces),
                },
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
            "semantics.unknown_policy_changes_behavior",
            "unknown policy did not alter runtime semantics",
        ),
    ]


def validate_executor_source_opacity() -> list[dict[str, Any]]:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    approved_predicate_ids = approved_recipe_predicate_ids()
    hits = [predicate_id for predicate_id in approved_predicate_ids if predicate_id in source]
    return [
        pass_check(
            "architecture.executor_has_no_approved_predicate_ids",
            "generic executor source contains none of the approved recipe predicate IDs",
            {"checked_predicate_ids": sorted(approved_predicate_ids)},
        )
        if not hits
        else fail_check(
            "architecture.executor_has_no_approved_predicate_ids",
            "generic executor source still contains approved recipe predicate IDs",
            {"hits": hits},
        )
    ]


def validate_cache_independent_reproduction(
    approved_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cache_path = Path("artifacts/m1.1")
    moved_path = Path("artifacts/m1.1.r5-cache-tmp")
    if moved_path.exists():
        return [
            fail_check(
                "reproduction.cache_independent",
                "temporary R5 cache path already exists",
                {"path": str(moved_path)},
            )
        ]
    try:
        if cache_path.exists():
            cache_path.rename(moved_path)
        _, execution = run_approved_plan()
        rows_without_cache = execution_result_rows(execution)
    finally:
        if moved_path.exists() and not cache_path.exists():
            moved_path.rename(cache_path)
    return [
        pass_check(
            "reproduction.cache_independent",
            "approved runtime reproduces results after generated artifacts cache is removed",
            {"result_count": len(rows_without_cache)},
        )
        if normalized_result_ids(approved_rows) == normalized_result_ids(rows_without_cache)
        else fail_check(
            "reproduction.cache_independent",
            "runtime result IDs changed when generated artifacts cache was unavailable",
            {
                "original_count": len(approved_rows),
                "cacheless_count": len(rows_without_cache),
            },
        )
    ]


def validate_m1_parity() -> list[dict[str, Any]]:
    gate_b = build_gate_b_report()
    return [
        pass_check(
            "parity.corrected_runtime_matches_m1",
            "Gate B full-output parity still passes after M1.1R corrections",
            {"summary": gate_b["summary"]},
        )
        if gate_b["status"] == "pass"
        else fail_check(
            "parity.corrected_runtime_matches_m1",
            "Gate B parity failed after M1.1R corrections",
            {"summary": gate_b.get("summary")},
        )
    ]


def run_approved_plan() -> tuple[Any, Any]:
    bound = bind_document_from_path(APPROVED_PLAN_PATH)
    execution = TacticalQueryExecutor().execute(bound)
    return bound, execution


def clone_plan_payload(path: Path) -> dict[str, Any]:
    return deepcopy(json.loads(path.read_text(encoding="utf-8")))


def renamed_node_payload(payload: dict[str, Any]) -> dict[str, Any]:
    nodes = payload["draft_plan"]["nodes"]
    mapping = {node["node_id"]: f"r5_{node['node_id']}" for node in nodes}
    for node in nodes:
        node["node_id"] = mapping[node["node_id"]]
        for reference in node.get("inputs", {}).values():
            reference["source_node_id"] = mapping[reference["source_node_id"]]
        if "input" in node:
            node["input"]["source_node_id"] = mapping[node["input"]["source_node_id"]]
    for rule in payload["draft_plan"]["classification_rules"]:
        rule["predicate_ids"] = [mapping[predicate_id] for predicate_id in rule["predicate_ids"]]
    for request in payload["draft_plan"]["requested_evidence"]:
        request["source"]["source_node_id"] = mapping[request["source"]["source_node_id"]]
    anchor_source = payload["draft_plan"].get("anchor_source")
    if isinstance(anchor_source, dict):
        anchor_source["source_node_id"] = mapping[anchor_source["source_node_id"]]
    payload["draft_plan"]["plan_id"] = "r5_renamed_approved_plan"
    payload["default_invocation"]["invocation_id"] = "r5_renamed_invocation"
    return payload


def normalize_result_for_node_rename(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        key: value
        for key, value in row.items()
        if key not in {"requested_evidence"}
    }
    if "matched_classification_rules" in normalized:
        normalized["matched_classification_rules"] = sorted(normalized["matched_classification_rules"])
    return normalized


def normalized_result_ids(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row["result_id"]) for row in rows]


def capability_coverage(plans: dict[str, Any]) -> dict[str, list[str]]:
    coverage: dict[str, set[str]] = {
        "primitives": set(),
        "relations": set(),
        "operators": set(),
    }
    for bound in plans.values():
        for node in bound.nodes:
            kind = getattr(node, "kind", None)
            if kind is None:
                continue
            if kind.value == "primitive":
                coverage["primitives"].add(node.catalog_ref)
            elif kind.value == "relation":
                coverage["relations"].add(node.catalog_ref)
            elif kind.value == "predicate":
                coverage["operators"].add(node.operator.name)
    return {kind: sorted(values) for kind, values in coverage.items()}


def simple_non_block_shift_payload() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": "r5_simple_possession_v1",
            "recipe_version": "0.1.0",
            "display_name": "R5 Simple Possession",
            "description": "Minimal non-block-shift plan used to prove the runtime can execute a second tactical shape.",
            "default_unknown_evidence_policy": "exclude_candidate",
            "allowed_claims": ["The perspective team had possession episodes."],
            "disallowed_claims": ["No block-shift, corridor, optimality, or video claim is made."],
            "limitations": ["Verification-only plan."],
            "output_classifications": ["POSSESSION_PRESENT"],
            "parameters": [
                parameter_definition("analysis_rate_hz", "number", "hertz", 5, "Analysis cadence."),
                parameter_definition("maximum_analysis_gap_ms", "number", "millisecond", 250, "Maximum analysis gap."),
                parameter_definition("minimum_possession_seconds", "number", "second", 8.0, "Minimum possession duration."),
            ],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": "r5_simple_j03woy",
            "match_ids": ["J03WOY"],
            "periods": ["firstHalf"],
            "perspective_team_role": "home",
            "parameters": {},
            "max_results": 10,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": "r5_simple_possession_plan",
            "plan_version": "0.1.0",
            "recipe_id": "r5_simple_possession_v1",
            "recipe_version": "0.1.0",
            "status": "experimental",
            "unknown_evidence_policy": "exclude_candidate",
            "classification_mode": "partial_declared",
            "complexity_limits": {
                "max_plan_nodes": 10,
                "max_nesting_depth": 4,
                "max_temporal_horizon_seconds": 5.0,
                "max_returned_moments": 10,
                "max_relations_per_anchor": 1,
                "max_execution_cost": 1000,
            },
            "nodes": [
                {"kind": "primitive", "node_id": "possession", "catalog_ref": "possession_segment", "version": "0.1.0"},
                {"kind": "primitive", "node_id": "ball_lateral", "catalog_ref": "ball_lateral_fraction", "version": "0.1.0"},
                {
                    "kind": "predicate",
                    "node_id": "central_lte",
                    "input": {"source_node_id": "ball_lateral", "output_name": "fraction"},
                    "operator": {"name": "lte", "version": "1.0.0"},
                    "compare": {"payload_type": "number", "unit": "fraction", "value": 0.33},
                },
                {
                    "kind": "predicate",
                    "node_id": "central_eq_true",
                    "input": {"source_node_id": "central_lte", "output_name": "predicate"},
                    "operator": {"name": "eq", "version": "1.0.0"},
                    "compare": {"payload_type": "boolean", "unit": "none", "value": True},
                },
                {
                    "kind": "predicate",
                    "node_id": "central_persists",
                    "input": {"source_node_id": "central_eq_true", "output_name": "predicate"},
                    "operator": {"name": "persists_for", "version": "1.0.0"},
                    "duration": {"payload_type": "number", "unit": "second", "value": 0.4},
                },
                {
                    "kind": "predicate",
                    "node_id": "has_possession",
                    "input": {"source_node_id": "possession", "output_name": "episodes"},
                    "operator": {"name": "exists", "version": "1.0.0"},
                },
                {
                    "kind": "predicate",
                    "node_id": "enough_possessions",
                    "input": {"source_node_id": "possession", "output_name": "episodes"},
                    "operator": {"name": "count_at_least", "version": "1.0.0"},
                    "compare": {"payload_type": "number", "unit": "count", "value": 1},
                },
            ],
            "classification_rules": [
                {
                    "label": "POSSESSION_PRESENT",
                    "predicate_ids": ["has_possession", "enough_possessions"],
                    "description": "The period has possession episodes.",
                }
            ],
            "anchor_source": {"source_node_id": "possession", "output_name": "anchors"},
            "requested_evidence": [],
        },
    }


def parameter_definition(
    name: str,
    payload_type: str,
    unit: str,
    value: float,
    description: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "payload_type": payload_type,
        "unit": unit,
        "required": False,
        "default": {"payload_type": payload_type, "unit": unit, "value": value},
        "description": description,
    }


def approved_recipe_predicate_ids() -> set[str]:
    payload = clone_plan_payload(APPROVED_PLAN_PATH)
    return {
        node["node_id"]
        for node in payload["draft_plan"]["nodes"]
        if node.get("kind") == "predicate"
    }


def main() -> int:
    report = build_report()
    print(f"Wrote {REPORT_PATH}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
