"""Verify N1B capability output domains and runtime parameter contract."""

from __future__ import annotations

import ast
import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tqe.runtime.binder import HOST_RUNTIME_PARAMETER_DEFAULTS, bind_document
from tqe.runtime.executor import (
    PeriodState,
    RuntimeParameters,
    primitive_relation_destination_entry_classification,
)
from tqe.runtime.ir import BoundCatalogNode, TacticalQueryDocument
from tqe.runtime.values import RuntimeValue
from tqe.write_mode import output_path
from tqe.workshop.m1_2 import (
    CallerProfile,
    ExecuteQueryPlanRequest,
    SubmitQueryPlanRequest,
    ToolDispatchRequest,
    dispatch_model_visible,
    execute_query_plan,
    host_confirm_bound_plan,
    utc_now_iso,
    write_json,
)

FAILED_DRAFT_ID = "draft_412f54700786817a"
FAILED_BOUND_ID = "bound_a4cdbc77075c85e7"
FAILED_DRAFT_PATH = Path("config/evaluation") / f"n1b_failed_hermes_draft_{FAILED_DRAFT_ID.removeprefix('draft_')}.json"
N1B_ROOT = Path("artifacts/n1b")
N1B_WORKSHOP_ROOT = N1B_ROOT / "workshop"
CORRECTED_PLAN_PATH = N1B_ROOT / "n1b-corrected-failed-hermes-plan.json"
REPORT_PATH = N1B_ROOT / "n1b-verification-report.json"
EXECUTOR_PATH = Path("src/tqe/runtime/executor.py")
QUERY_PLAN_DIR = Path("config/query-plans")


def check(check_id: str, passed: bool, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": "pass" if passed else "fail",
        "message": message,
        "details": details or {},
    }


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def failed_document() -> dict[str, Any]:
    return read_json(FAILED_DRAFT_PATH)["document"]


def corrected_document() -> dict[str, Any]:
    document = deepcopy(failed_document())
    document["default_invocation"]["match_ids"] = ["J03WOY"]
    document["default_invocation"]["max_results"] = 5
    for node in document["draft_plan"]["nodes"]:
        if node["node_id"] == "destination_region_entered":
            node["compare"]["value"] = "PASS"
    return document


def host_runtime_default_values() -> dict[str, Any]:
    return {
        name: definition.default.value
        for name, definition in HOST_RUNTIME_PARAMETER_DEFAULTS.items()
        if definition.default is not None
    }


def exact_failed_validation() -> dict[str, Any]:
    if N1B_WORKSHOP_ROOT.exists():
        shutil.rmtree(N1B_WORKSHOP_ROOT)
    submitted = dispatch_model_visible(
        ToolDispatchRequest(
            tool_name="submit_query_plan",
            arguments={
                "plan_document": failed_document(),
                "source_label": "n1b_replay_failed_hermes_plan",
            },
        ),
        output_root=N1B_WORKSHOP_ROOT,
        caller_profile=CallerProfile.HERMES_S2I_MCP,
    )
    validated = dispatch_model_visible(
        ToolDispatchRequest(
            tool_name="validate_query_plan",
            arguments={"draft_plan_id": submitted["draft_plan_id"]},
        ),
        output_root=N1B_WORKSHOP_ROOT,
        caller_profile=CallerProfile.HERMES_S2I_MCP,
    )
    return {
        "submitted": submitted,
        "validated": validated,
        "issues": validated.get("issues", []),
        "ok": validated.get("ok"),
    }


def submit_validate_execute_corrected() -> dict[str, Any]:
    if N1B_WORKSHOP_ROOT.exists():
        shutil.rmtree(N1B_WORKSHOP_ROOT)
    document = corrected_document()
    write_json(output_path(CORRECTED_PLAN_PATH), document)
    submitted = dispatch_model_visible(
        ToolDispatchRequest(
            tool_name="submit_query_plan",
            arguments={
                "plan_document": document,
                "source_label": "n1b_corrected_failed_hermes_plan",
            },
        ),
        output_root=N1B_WORKSHOP_ROOT,
        caller_profile=CallerProfile.HERMES_S2I_MCP,
    )
    validated = dispatch_model_visible(
        ToolDispatchRequest(
            tool_name="validate_query_plan",
            arguments={"draft_plan_id": submitted["draft_plan_id"]},
        ),
        output_root=N1B_WORKSHOP_ROOT,
        caller_profile=CallerProfile.HERMES_S2I_MCP,
    )
    if not validated.get("ok", True):
        return {
            "submitted": submitted,
            "validated": validated,
            "confirmed": {},
            "executed": {},
            "bound_parameters": {},
        }
    bound_path = N1B_WORKSHOP_ROOT / "handles" / "bound-plans" / f"{validated['bound_plan_id']}.json"
    bound_record = read_json(bound_path)
    confirmed = host_confirm_bound_plan(
        validated["bound_plan_id"],
        reviewer="n1b_controller",
        output_root=N1B_WORKSHOP_ROOT,
    ).model_dump(mode="json")
    executed = execute_query_plan(
        ExecuteQueryPlanRequest(
            bound_plan_id=validated["bound_plan_id"],
            execution_authorization_id=confirmed["execution_authorization_id"],
            result_limit=3,
        ),
        output_root=N1B_WORKSHOP_ROOT,
    ).model_dump(mode="json")
    return {
        "submitted": submitted,
        "validated": validated,
        "confirmed": confirmed,
        "executed": executed,
        "bound_parameters": {
            item["name"]: item
            for item in bound_record["bound_plan"]["resolved_parameters"]
        },
        "bound_outputs": {
            f"{node['node_id']}.{output['name']}": output
            for node in bound_record["bound_plan"]["nodes"]
            if node.get("kind") in {"primitive", "relation"}
            for output in node.get("outputs", [])
        },
    }


def unknown_destination_entry_fixture() -> dict[str, Any]:
    """Exercise generic destination-entry UNKNOWN propagation with missing ball evidence."""
    bound = bind_document(TacticalQueryDocument.model_validate(corrected_document()))
    destination_node = next(
        node
        for node in bound.nodes
        if (
            isinstance(node, BoundCatalogNode)
            and node.catalog_ref == "relation_destination_entry"
            and node.outputs
            and node.outputs[0].name == "entry_status"
        )
    )
    relation_ref = destination_node.inputs["relation_episodes"]
    relation_node = next(
        node
        for node in bound.nodes
        if isinstance(node, BoundCatalogNode) and node.node_id == relation_ref.source_node_id
    )
    relation_output = next(output for output in relation_node.outputs if output.name == relation_ref.output_name)
    source_result = {
        "result_id": "unknown_source_anchor",
        "match_id": "UNKNOWN_FIXTURE",
        "period": "firstHalf",
        "anchor_id": "fixture_anchor_100",
        "anchor_frame_id": 100,
        "replay_start_frame_id": 90,
        "replay_end_frame_id": 112,
        "classification": "FIXTURE_SOURCE",
    }
    episode = {
        "relation_id": "fixture_relation_missing_ball",
        "relation_version": "fixture",
        "relation_anchor_source": "fixture_anchor_source",
        "source_result": source_result,
        "open_frame_id": 100,
        "open_confirm_frame_id": 100,
        "close_frame_id": 102,
        "duration_seconds": 0.4,
        "target_player_id": "fixture_target",
        "minimum_clearance_m": 3.0,
        "limiting_defender_id": "fixture_defender",
        "destination_side": "left",
        "destination_lane": "half_space",
        "destination_region": "left_half_space",
        "destination_region_type": "side_lane_band",
        "destination_region_bounds": {"min_y_m": -24.0, "max_y_m": -8.0},
        "source_open_point": {"x_m": 20.0, "y_m": -18.0},
        "target_open_point": {"x_m": 35.0, "y_m": -14.0},
        "source_close_point": {"x_m": 20.0, "y_m": -18.0},
        "target_close_point": {"x_m": 35.0, "y_m": -14.0},
    }
    params = host_runtime_default_values()
    params["result_id_seed_hash"] = "unknown-fixture-seed"
    state = PeriodState(
        match_id="UNKNOWN_FIXTURE",
        period="firstHalf",
        params=RuntimeParameters(values=params),
        recipe_id=bound.recipe_id,
        recipe_version=bound.recipe_version,
        perspective_team_role="home",
        perspective_team_id="fixture_home",
        defending_team_role="away",
        defending_team_id="fixture_away",
        canonical_root=Path("."),
        raw_tracking=Path("."),
        positions=pd.DataFrame(columns=["entity_type", "frame_id", "x_m", "y_m"]),
        frame_ids=np.array([100, 101, 102], dtype=int),
        ball_y=np.array([], dtype=float),
        possession_role=np.array([], dtype=object),
        ball_alive=np.array([], dtype=bool),
        defender_count=pd.Series(dtype=float),
        defender_centroid_y=pd.Series(dtype=float),
        runtime_values={
            relation_ref.source_node_id: {
                relation_ref.output_name: RuntimeValue(
                    output=relation_output,
                    value=[episode],
                    records=[episode],
                )
            }
        },
    )
    primitive_relation_destination_entry_classification(state, destination_node)
    output_name = destination_node.outputs[0].name
    signal = state.signals[destination_node.node_id][output_name]
    record = state.accepted[0] if state.accepted else {}
    return {
        "node_id": destination_node.node_id,
        "output_name": output_name,
        "entry_status": record.get("entry_status"),
        "unknown_reason": record.get("unknown_reason"),
        "missing_ball_frame_count": record.get("missing_ball_frame_count"),
        "frame_ids": signal.frame_ids,
        "signal_values": signal.values,
        "unknown_mask": signal.unknown_mask,
        "record_count": len(state.accepted),
    }


def runtime_parameter_access_contract() -> dict[str, Any]:
    tree = ast.parse(EXECUTOR_PATH.read_text(encoding="utf-8"))
    accesses: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"number", "integer", "text"}
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            continue
        receiver = ast.unparse(node.func.value)
        accesses.append(
            {
                "name": node.args[0].value,
                "accessor": node.func.attr,
                "receiver": receiver,
                "line": node.lineno,
            }
        )
    recipe_parameters = checked_in_recipe_parameter_names()
    host_defaults = set(HOST_RUNTIME_PARAMETER_DEFAULTS)
    access_names = {item["name"] for item in accesses}
    declared = recipe_parameters | host_defaults
    undeclared = sorted(access_names - declared)
    return {
        "executor_path": str(EXECUTOR_PATH),
        "access_count": len(accesses),
        "access_names": sorted(access_names),
        "host_runtime_defaults": sorted(host_defaults),
        "checked_in_recipe_parameters": sorted(recipe_parameters),
        "undeclared_accesses": undeclared,
        "accesses": sorted(accesses, key=lambda item: (item["name"], item["line"], item["accessor"])),
    }


def checked_in_recipe_parameter_names() -> set[str]:
    names: set[str] = set()
    for path in sorted(QUERY_PLAN_DIR.glob("*.json")):
        data = read_json(path)
        for parameter in (data.get("recipe") or {}).get("parameters") or []:
            name = parameter.get("name")
            if isinstance(name, str):
                names.add(name)
    return names


def build_report() -> dict[str, Any]:
    N1B_ROOT.mkdir(parents=True, exist_ok=True)
    failed_validation = exact_failed_validation()
    corrected = submit_validate_execute_corrected()
    unknown_fixture = unknown_destination_entry_fixture()
    parameter_contract = runtime_parameter_access_contract()
    failed_codes = {issue.get("code") for issue in failed_validation.get("issues", [])}
    bound_parameters = corrected.get("bound_parameters", {})
    destination_output = corrected.get("bound_outputs", {}).get("destination_entry.entry_status", {})
    executed = corrected.get("executed", {})
    checks = [
        check(
            "n1b.failed_draft_fixture_present",
            FAILED_DRAFT_PATH.exists(),
            "Exact failed Hermes draft fixture is present.",
            {"path": str(FAILED_DRAFT_PATH), "draft_plan_id": FAILED_DRAFT_ID, "bound_plan_id": FAILED_BOUND_ID},
        ),
        check(
            "n1b.failed_draft_rejected_before_execution",
            failed_validation.get("ok") is False and "compare_value_not_allowed" in failed_codes,
            "The exact failed Hermes plan is rejected by validation before execution.",
            failed_validation,
        ),
        check(
            "n1b.output_domain_visible",
            destination_output.get("allowed_values") == ["PASS", "FAIL", "UNKNOWN"],
            "relation_destination_entry.entry_status declares the PASS/FAIL/UNKNOWN domain.",
            destination_output,
        ),
        check(
            "n1b.runtime_globals_host_injected",
            all(
                name in bound_parameters
                for name in (
                    "analysis_rate_hz",
                    "minimum_possession_seconds",
                    "maximum_analysis_gap_ms",
                    "minimum_outfield_players_per_team",
                )
            ),
            "Host runtime globals are present in the corrected bound plan.",
            {name: bound_parameters.get(name) for name in sorted(bound_parameters) if name in {
                "analysis_rate_hz",
                "minimum_possession_seconds",
                "maximum_analysis_gap_ms",
                "minimum_outfield_players_per_team",
            }},
        ),
        check(
            "n1b.model_visible_submit_validate_ok",
            corrected.get("submitted", {}).get("ok", True) is not False
            and corrected.get("validated", {}).get("ok") is True,
            "Corrected plan submits and validates through the model-visible dispatcher.",
            {"submitted": corrected.get("submitted"), "validated": corrected.get("validated")},
        ),
        check(
            "n1b.host_confirm_execute_ok",
            executed.get("ok") is True
            and executed.get("compatibility_profile") == "generic"
            and int(executed.get("total_result_count") or 0) > 0,
            "Host-confirmed corrected plan executes over real canonical data.",
            executed,
        ),
        check(
            "n1b.execution_does_not_require_hermes_execution_tool",
            bool(corrected.get("confirmed", {}).get("execution_authorization_id"))
            and executed.get("ok") is True,
            "Execution remains host-confirmed, not model-authorized.",
            {"confirmed": corrected.get("confirmed"), "executed": executed},
        ),
        check(
            "n1b.unknown_destination_entry_preserved",
            unknown_fixture.get("entry_status") == "UNKNOWN"
            and unknown_fixture.get("signal_values") == [None]
            and unknown_fixture.get("unknown_mask") == [True]
            and "missing_ball_frames" in str(unknown_fixture.get("unknown_reason")),
            "Missing ball evidence propagates as UNKNOWN through the generic destination-entry primitive.",
            unknown_fixture,
        ),
        check(
            "n1b.executor_runtime_parameters_declared",
            not parameter_contract["undeclared_accesses"],
            "Every executor RuntimeParameters access is declared by host defaults or a checked-in recipe.",
            parameter_contract,
        ),
    ]
    summary = {
        "pass": sum(1 for item in checks if item["status"] == "pass"),
        "fail": sum(1 for item in checks if item["status"] == "fail"),
    }
    failed_bound = bindable_failed_summary()
    report = {
        "schema_version": "n1b.verification.v1",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 else "fail",
        "summary": summary,
        "failed_hermes_session": {
            "session_id": "20260622_131836_38c3fb",
            "draft_plan_id": FAILED_DRAFT_ID,
            "bound_plan_id": FAILED_BOUND_ID,
            "draft_path": str(FAILED_DRAFT_PATH),
            "failed_validation": failed_validation,
            "bind_summary": failed_bound,
        },
        "corrected_path": str(CORRECTED_PLAN_PATH),
        "corrected_flow": corrected,
        "unknown_fixture": unknown_fixture,
        "runtime_parameter_contract": parameter_contract,
        "checks": checks,
    }
    write_json(output_path(REPORT_PATH), report)
    return report


def bindable_failed_summary() -> dict[str, Any]:
    try:
        bind_document(TacticalQueryDocument.model_validate(failed_document()))
    except Exception as exc:
        return {
            "bind_ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    return {"bind_ok": True}


def main() -> None:
    report = build_report()
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
