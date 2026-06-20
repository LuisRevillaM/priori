"""Verify M1.1R Gate R4: relation anchor decoupling and experimental repair."""

from __future__ import annotations

import ast
import json
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document, bind_document_from_path
from tqe.runtime.catalog import default_catalog
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows
from tqe.runtime.ir import BoundCatalogNode, NodeKind, TacticalQueryDocument

PLAN_PATH = Path("config/query-plans/opposite_corridor_after_shift.experimental.v1.json")
EXECUTOR_PATH = Path("src/tqe/runtime/executor.py")
REPORT_PATH = Path("artifacts/m1.1/gate-r4-verification-report.json")


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
    checks.extend(validate_catalog_contract())
    checks.extend(validate_executor_source_decoupling())
    checks.extend(validate_experimental_plan_execution())
    checks.extend(validate_non_m1_anchor_execution())

    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.1R",
        "gate": "Gate_R4_relation_anchor_decoupling_experimental_repair",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    return report


def validate_catalog_contract() -> list[dict[str, Any]]:
    catalog = default_catalog()
    relation = next(
        (
            entry
            for entry in catalog.relations
            if entry.name == "geometric_progressive_corridor"
            and entry.version == "0.1.0"
        ),
        None,
    )
    destination = next(
        (
            entry
            for entry in catalog.primitives
            if entry.name == "relation_destination_entry_classification"
            and entry.version == "0.1.0"
        ),
        None,
    )
    checks: list[dict[str, Any]] = []
    if relation is None:
        checks.append(fail_check("catalog.relation.present", "geometric_progressive_corridor is missing"))
    else:
        relation_inputs = {item.name for item in relation.inputs}
        relation_fields = set(relation.outputs[0].evidence_fields)
        checks.append(
            pass_check(
                "catalog.relation.explicit_anchors",
                "geometric_progressive_corridor declares an explicit anchors input",
                {"inputs": sorted(relation_inputs)},
            )
            if relation_inputs == {"anchors"}
            else fail_check(
                "catalog.relation.explicit_anchors",
                "geometric_progressive_corridor does not expose only explicit anchors",
                {"inputs": sorted(relation_inputs)},
            )
        )
        checks.append(
            pass_check(
                "catalog.relation.region_bounds",
                "relation episodes expose honest side-lane band region semantics",
                {"fields": sorted(relation_fields)},
            )
            if {"destination_region_type", "destination_region_bounds"}.issubset(relation_fields)
            else fail_check(
                "catalog.relation.region_bounds",
                "relation output lacks destination region semantics fields",
                {"fields": sorted(relation_fields)},
            )
        )

    if destination is None:
        checks.append(
            fail_check(
                "catalog.destination.present",
                "relation_destination_entry_classification is missing",
            )
        )
    else:
        destination_inputs = {item.name for item in destination.inputs}
        parameter_names = {item.name for item in destination.parameters}
        checks.append(
            pass_check(
                "catalog.destination.explicit_relation_input",
                "destination entry consumes relation episodes through a bound input",
                {"inputs": sorted(destination_inputs)},
            )
            if destination_inputs == {"relation_episodes"}
            else fail_check(
                "catalog.destination.explicit_relation_input",
                "destination entry does not declare the expected relation_episodes input",
                {"inputs": sorted(destination_inputs)},
            )
        )
        checks.append(
            pass_check(
                "catalog.destination.no_relation_node_parameter",
                "destination entry no longer accepts a relation_node_id parameter",
                {"parameters": sorted(parameter_names)},
            )
            if "relation_node_id" not in parameter_names and "episode_selection" in parameter_names
            else fail_check(
                "catalog.destination.no_relation_node_parameter",
                "destination entry still has node-id coupling or lacks explicit selection",
                {"parameters": sorted(parameter_names)},
            )
        )
    return checks


def validate_executor_source_decoupling() -> list[dict[str, Any]]:
    tree = ast.parse(EXECUTOR_PATH.read_text(encoding="utf-8"))
    target_functions = {
        "relation_geometric_progressive_corridor",
        "primitive_relation_destination_entry_classification",
    }
    hits: list[dict[str, Any]] = []
    for function in [node for node in tree.body if isinstance(node, ast.FunctionDef)]:
        if function.name not in target_functions:
            continue
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "accepted"
                and isinstance(node.ctx, ast.Load)
            ):
                hits.append({"function": function.name, "line": node.lineno})
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", "") == "node_parameter_text"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "relation_node_id"
            ):
                hits.append({"function": function.name, "line": node.lineno, "parameter": "relation_node_id"})
    return [
        pass_check(
            "executor.no_hidden_accepted_coupling",
            "relation and destination implementations do not read state.accepted or relation_node_id parameters",
        )
        if not hits
        else fail_check(
            "executor.no_hidden_accepted_coupling",
            "relation or destination implementation still has hidden accepted-result coupling",
            {"hits": hits},
        )
    ]


def validate_experimental_plan_execution() -> list[dict[str, Any]]:
    bound = bind_document_from_path(PLAN_PATH)
    execution = TacticalQueryExecutor().execute(bound)
    rows = execution_result_rows(execution)
    relation_nodes = [
        node
        for node in bound.nodes
        if isinstance(node, BoundCatalogNode)
        and node.kind == NodeKind.RELATION
        and node.catalog_ref == "geometric_progressive_corridor"
    ]
    destination_nodes = [
        node
        for node in bound.nodes
        if isinstance(node, BoundCatalogNode)
        and node.catalog_ref == "relation_destination_entry_classification"
    ]
    region_failures = [
        row["result_id"]
        for row in rows
        if row.get("destination_region_type") != "side_lane_band"
        or not valid_bounds(row.get("destination_region_bounds"))
        or row.get("relation_episode_selection") != "first_by_duration_clearance"
        or row.get("relation_anchor_source") != "outcome.classification"
    ]
    by_classification = Counter(str(row["classification"]) for row in rows)
    return [
        pass_check(
            "plan.explicit_inputs",
            "experimental relation and destination nodes retain bound graph inputs",
            {
                "relation_inputs": serialized_inputs(relation_nodes[0]) if relation_nodes else {},
                "destination_inputs": serialized_inputs(destination_nodes[0]) if destination_nodes else {},
            },
        )
        if len(relation_nodes) == 1
        and len(destination_nodes) == 1
        and "anchors" in relation_nodes[0].inputs
        and "relation_episodes" in destination_nodes[0].inputs
        else fail_check(
            "plan.explicit_inputs",
            "experimental plan is missing explicit relation inputs",
            {
                "relation_count": len(relation_nodes),
                "destination_count": len(destination_nodes),
            },
        ),
        pass_check(
            "execution.experimental_plan_repaired",
            "opposite-corridor experimental plan executes without hidden M1 accepted-result coupling",
            {
                "status": execution.status.value,
                "result_count": len(rows),
                "by_classification": dict(sorted(by_classification.items())),
            },
        )
        if execution.status.value == "pass"
        and len(rows) >= 20
        and not region_failures
        and {"DESTINATION_ENTERED", "CORRIDOR_PERSISTED_NO_DESTINATION_ENTRY"}.issubset(by_classification)
        else fail_check(
            "execution.experimental_plan_repaired",
            "experimental plan execution does not satisfy R4 repaired relation contract",
            {
                "status": execution.status.value,
                "result_count": len(rows),
                "by_classification": dict(sorted(by_classification.items())),
                "region_failure_sample": region_failures[:10],
            },
        ),
    ]


def validate_non_m1_anchor_execution() -> list[dict[str, Any]]:
    payload = relaxed_non_m1_anchor_payload()
    bound = bind_document(TacticalQueryDocument.model_validate(payload))
    execution = TacticalQueryExecutor().execute(bound)
    rows = execution_result_rows(execution)
    by_source_classification = Counter(str(row.get("source_classification")) for row in rows)
    stoppage_rows = [row["result_id"] for row in rows if row.get("source_classification") == "STOPPAGE"]
    return [
        pass_check(
            "execution.non_m1_anchor_set",
            "a valid relaxed plan runs relation/destination from anchors outside the M1 accepted set",
            {
                "status": execution.status.value,
                "result_count": len(rows),
                "by_source_classification": dict(sorted(by_source_classification.items())),
                "stoppage_result_ids": stoppage_rows[:10],
            },
        )
        if execution.status.value == "pass" and stoppage_rows
        else fail_check(
            "execution.non_m1_anchor_set",
            "relaxed valid plan did not produce results from non-M1 accepted anchors",
            {
                "status": execution.status.value,
                "result_count": len(rows),
                "by_source_classification": dict(sorted(by_source_classification.items())),
            },
        )
    ]


def relaxed_non_m1_anchor_payload() -> dict[str, Any]:
    payload = deepcopy(json.loads(PLAN_PATH.read_text(encoding="utf-8")))
    payload["default_invocation"]["match_ids"] = ["J03WOY"]
    payload["default_invocation"]["periods"] = ["firstHalf"]
    payload["default_invocation"]["max_results"] = 64
    for node in payload["draft_plan"]["nodes"]:
        if node.get("node_id") != "opposite_corridor":
            continue
        node["parameters"]["side_filter"] = {
            "payload_type": "enum",
            "unit": "none",
            "value": "any",
        }
        node["parameters"]["minimum_duration_seconds"] = {
            "payload_type": "number",
            "unit": "second",
            "value": 0.0,
        }
        node["parameters"]["minimum_clearance_m"] = {
            "payload_type": "number",
            "unit": "metre",
            "value": 0.0,
        }
        node["parameters"]["minimum_progression_m"] = {
            "payload_type": "number",
            "unit": "metre",
            "value": 0.0,
        }
        node["parameters"]["minimum_segment_length_m"] = {
            "payload_type": "number",
            "unit": "metre",
            "value": 0.0,
        }
    return payload


def valid_bounds(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if set(value) != {"min_y_m", "max_y_m"}:
        return False
    return all(isinstance(value[key], int | float) for key in value) and value["min_y_m"] <= value["max_y_m"]


def serialized_inputs(node: BoundCatalogNode) -> dict[str, dict[str, str]]:
    return {
        name: reference.model_dump(mode="json")
        for name, reference in sorted(node.inputs.items())
    }


def main() -> int:
    report = build_report()
    print(f"Wrote {REPORT_PATH}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
