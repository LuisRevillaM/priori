"""Verify M1.2 S0: bounded capability and tool context."""

from __future__ import annotations

import json
import shutil
import subprocess
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.ir import TacticalQueryDocument
from tqe.workshop.m1_2 import (
    APPROVED_TOOL_NAMES,
    CAPABILITY_CONTEXT_PATH,
    FORBIDDEN_SURFACES,
    HERMES_S2_TOOL_NAMES,
    SAFE_ANCHOR_RELATIVE_OUTPUT,
    CapabilityGap,
    CallerProfile,
    SubmitQueryPlanRequest,
    ToolDispatchRequest,
    dispatch_model_visible,
    host_confirm_bound_plan,
    ValidateQueryPlanRequest,
    dispatch_tool,
    list_capabilities,
    submit_query_plan,
    validate_query_plan,
    write_capability_context,
)
from tqe.write_mode import diff_against_checked_in, serialize_json_artifact, write_mode

REPORT_PATH = Path("artifacts/m1.2/gate-s0-verification-report.json")
APPROVED_PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def check(check_id: str, passed: bool, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": "pass" if passed else "fail",
        "message": message,
        "details": details or {},
    }


def build_report() -> dict[str, Any]:
    drift: list[dict[str, Any]] = []
    if write_mode():
        # Explicit TQE_WRITE=1 opt-in: reset handles and rewrite the tracked context.
        clean_handles()
        context = write_capability_context(CAPABILITY_CONTEXT_PATH)
    else:
        # Read-only check: never delete or rewrite tracked files; regenerate the
        # capability context in memory and diff it against the checked-in file.
        context = list_capabilities(CallerProfile.HERMES_S2)
        drift_item = diff_against_checked_in(
            CAPABILITY_CONTEXT_PATH,
            serialize_json_artifact(context.model_dump(mode="json")),
        )
        if drift_item is not None:
            drift.append(drift_item)
    manual_context = list_capabilities(CallerProfile.HOST_MANUAL)
    checks: list[dict[str, Any]] = []
    checks.append(
        check(
            "s0.capability_context.tracked_file_matches_regeneration",
            not drift,
            "generated/capability-context.json matches a fresh regeneration (run "
            "`make m1-2-gate-s0-write` to regenerate deliberately).",
            {"drift": drift},
        )
    )
    tool_names = [tool.name for tool in context.tools]
    checks.append(check("s0.hermes_tool_surface.exact", tool_names == HERMES_S2_TOOL_NAMES, "Hermes sees only the S2 tool surface.", {"tools": tool_names}))
    checks.append(check("s0.manual_tool_surface.full", [tool.name for tool in manual_context.tools] == APPROVED_TOOL_NAMES, "Host/manual sees the full staged tool surface.", {"tools": [tool.name for tool in manual_context.tools]}))
    placeholder_schemas = [
        tool.name
        for tool in context.tools
        if tool.input_schema == {"type": "object", "additionalProperties": False}
        or tool.output_schema == {"type": "object", "additionalProperties": False}
    ]
    checks.append(
        check(
            "s0.tool_schemas.real",
            not placeholder_schemas
            and all("properties" in tool.input_schema or "$defs" in tool.input_schema for tool in context.tools),
            "Every tool advertises real generated request/response JSON schemas.",
            {"placeholder_schemas": placeholder_schemas},
        )
    )
    checks.append(
        check(
            "s0.forbidden_surfaces.absent",
            all(surface in context.forbidden_surfaces for surface in FORBIDDEN_SURFACES)
            and all(tool.unavailable_surfaces == FORBIDDEN_SURFACES for tool in context.tools),
            "Forbidden code, data, and mutation surfaces are explicitly unavailable.",
            {"forbidden_surfaces": context.forbidden_surfaces},
        )
    )
    checks.append(
        check(
            "s0.capability_context.schema_valid",
            list_capabilities().model_validate(context.model_dump(mode="json")) is not None,
            "Generated capability context is schema-valid.",
            {"path": str(CAPABILITY_CONTEXT_PATH)},
        )
    )
    checks.append(
        check(
            "s0.anchor_relative_operator_rules.visible",
            context.safe_operator_source_rules.get("exists", {}).get("allowed_output_name")
            == SAFE_ANCHOR_RELATIVE_OUTPUT
            and context.safe_operator_source_rules.get("count_at_least", {}).get("allowed_output_name")
            == SAFE_ANCHOR_RELATIVE_OUTPUT,
            "exists/count_at_least are visible only as anchor_evaluations operators.",
            {"safe_operator_source_rules": context.safe_operator_source_rules},
        )
    )
    checks.append(
        check(
            "s0.host_owned_complexity_ceilings.visible",
            context.host_owned_complexity_ceilings == context.default_complexity_limits
            and int(context.host_owned_complexity_ceilings.get("max_execution_cost", 0)) > 0,
            "Capability context exposes trusted host-owned complexity ceilings.",
            {"ceilings": context.host_owned_complexity_ceilings},
        )
    )
    approved_submit = submit_query_plan(
        SubmitQueryPlanRequest(
            plan_document=TacticalQueryDocument.model_validate_json(APPROVED_PLAN_PATH.read_text(encoding="utf-8"))
        ),
        caller_profile=CallerProfile.HOST_MANUAL,
    )
    approved_validation = validate_query_plan(
        ValidateQueryPlanRequest(draft_plan_id=approved_submit.draft_plan_id),
        caller_profile=CallerProfile.HOST_MANUAL,
    )
    checks.append(
        check(
            "s0.approved_plan.validates",
            approved_validation.ok and bool(approved_validation.bound_plan_hash),
            "Manual plan entry validates through an opaque draft_plan_id, not a filesystem path.",
            approved_validation.model_dump(mode="json"),
        )
    )
    unsafe_submit = submit_query_plan(
        SubmitQueryPlanRequest(
            plan_document=TacticalQueryDocument.model_validate(unsafe_raw_episode_exists_plan())
        ),
        caller_profile=CallerProfile.HERMES_S2,
    )
    unsafe_validation = validate_query_plan(ValidateQueryPlanRequest(draft_plan_id=unsafe_submit.draft_plan_id))
    checks.append(
        check(
            "s0.unsafe_raw_episode_exists_rejected",
            not unsafe_validation.ok
            and any("anchor_evaluations" in issue.get("message", "") for issue in unsafe_validation.issues),
            "Raw boolean EpisodeSet exists is rejected by the agent-visible boundary.",
            unsafe_validation.model_dump(mode="json"),
        )
    )
    unsupported_gap = False
    try:
        from tqe.workshop.m1_2 import describe_capability

        describe_capability("video_pose_estimation")
    except CapabilityGap:
        unsupported_gap = True
    checks.append(
        check(
            "s0.unsupported_capability_gap",
            unsupported_gap,
            "Unsupported concepts fail explicitly as capability gaps.",
        )
    )
    dispatched = dispatch_tool(
        ToolDispatchRequest(
            tool_name="validate_query_plan",
            arguments={"draft_plan_id": approved_submit.draft_plan_id},
        ),
        caller_profile=CallerProfile.HOST_MANUAL,
    )
    checks.append(
        check(
            "s0.serialized_dispatcher_validates",
            dispatched.ok and dispatched.response.get("bound_plan_id") == approved_validation.bound_plan_id,
            "Serialized dispatcher reaches the same validation boundary Hermes will use.",
            dispatched.model_dump(mode="json"),
        )
    )
    retry_submit = dispatch_model_visible(
        ToolDispatchRequest(
            tool_name="submit_query_plan",
            arguments={
                "plan_document": TacticalQueryDocument.model_validate_json(
                    APPROVED_PLAN_PATH.read_text(encoding="utf-8")
                ).model_dump(mode="json")
            },
        ),
        caller_profile=CallerProfile.HOST_MANUAL,
    )
    retry_validation = dispatch_model_visible(
        ToolDispatchRequest(
            tool_name="validate_query_plan",
            arguments={"draft_plan_id": approved_submit.draft_plan_id},
        ),
        caller_profile=CallerProfile.HOST_MANUAL,
    )
    authorization = host_confirm_bound_plan(approved_validation.bound_plan_id)
    retry_authorization = host_confirm_bound_plan(approved_validation.bound_plan_id)
    retry_execution = dispatch_model_visible(
        ToolDispatchRequest(
            tool_name="execute_query_plan",
            arguments={
                "bound_plan_id": approved_validation.bound_plan_id,
                "execution_authorization_id": authorization.execution_authorization_id,
                "result_limit": 2,
            },
        ),
        caller_profile=CallerProfile.HOST_MANUAL,
    )
    retry_execution_again = dispatch_model_visible(
        ToolDispatchRequest(
            tool_name="execute_query_plan",
            arguments={
                "bound_plan_id": approved_validation.bound_plan_id,
                "execution_authorization_id": retry_authorization.execution_authorization_id,
                "result_limit": 2,
            },
        ),
        caller_profile=CallerProfile.HOST_MANUAL,
    )
    retry_replay = dispatch_model_visible(
        ToolDispatchRequest(
            tool_name="retrieve_replay_window",
            arguments={
                "execution_id": retry_execution["execution_id"],
                "result_id": retry_execution["results"][0]["result_id"],
                "padding_seconds": 2.0,
            },
        ),
        caller_profile=CallerProfile.HOST_MANUAL,
    )
    retry_replay_again = dispatch_model_visible(
        ToolDispatchRequest(
            tool_name="retrieve_replay_window",
            arguments={
                "execution_id": retry_execution["execution_id"],
                "result_id": retry_execution["results"][0]["result_id"],
                "padding_seconds": 2.0,
            },
        ),
        caller_profile=CallerProfile.HOST_MANUAL,
    )
    checks.append(
        check(
            "s0.content_addressed_retries_idempotent",
            retry_submit["draft_plan_id"] == approved_submit.draft_plan_id
            and retry_validation["bound_plan_id"] == approved_validation.bound_plan_id
            and authorization.execution_authorization_id == retry_authorization.execution_authorization_id
            and retry_execution["execution_id"] == retry_execution_again["execution_id"]
            and retry_replay["replay_window_id"] == retry_replay_again["replay_window_id"],
            "Repeated content-addressed tool calls return existing resources instead of false failures.",
            {
                "draft_plan_id": retry_submit["draft_plan_id"],
                "bound_plan_id": retry_validation["bound_plan_id"],
                "execution_id": retry_execution["execution_id"],
                "replay_window_id": retry_replay["replay_window_id"],
            },
        )
    )
    manual_denied = dispatch_tool(
        ToolDispatchRequest(tool_name="record_feedback", arguments={}),
        caller_profile=CallerProfile.HERMES_S2,
    )
    checks.append(check("s0.hermes_manual_tool_denied", not manual_denied.ok, "Hermes cannot call manual-only tools.", manual_denied.model_dump(mode="json")))
    authored_approved = dispatch_tool(
        ToolDispatchRequest(
            tool_name="submit_query_plan",
            arguments={"plan_document": TacticalQueryDocument.model_validate_json(APPROVED_PLAN_PATH.read_text(encoding="utf-8")).model_dump(mode="json")},
        ),
        caller_profile=CallerProfile.HERMES_S2,
    )
    checks.append(check("s0.hermes_cannot_submit_approved", not authored_approved.ok, "Hermes-authored documents cannot claim APPROVED status.", authored_approved.model_dump(mode="json")))
    traversal_rejected = False
    traversal_details: dict[str, Any] = {}
    try:
        traversal_validation = validate_query_plan(ValidateQueryPlanRequest(draft_plan_id="draft_../../badbad"))
        traversal_rejected = not traversal_validation.ok
        traversal_details = traversal_validation.model_dump(mode="json")
    except Exception as exc:
        traversal_rejected = True
        traversal_details = {"error": type(exc).__name__, "message": str(exc)}
    checks.append(check("s0.handle_traversal_rejected", traversal_rejected, "Invalid handle patterns and traversal are rejected.", traversal_details))
    non_authorable_submit = submit_query_plan(
        SubmitQueryPlanRequest(plan_document=TacticalQueryDocument.model_validate(non_authorable_outcome_plan())),
        caller_profile=CallerProfile.HERMES_S2,
    )
    non_authorable_validation = validate_query_plan(ValidateQueryPlanRequest(draft_plan_id=non_authorable_submit.draft_plan_id))
    checks.append(check("s0.non_authorable_capability_rejected", not non_authorable_validation.ok and any("not agent-authorable" in issue.get("message", "") for issue in non_authorable_validation.issues), "Non-authorable catalog capabilities are rejected.", non_authorable_validation.model_dump(mode="json")))
    model_visible_matrix = model_visible_tool_matrix()
    checks.append(
        check(
            "s0.model_visible_schema_conformance_all_s2_tools",
            all(item["success_ok"] and item["failure_ok"] for item in model_visible_matrix),
            "Model-visible dispatcher validates successful and failing responses for every S2-visible tool.",
            {"matrix": model_visible_matrix},
        )
    )

    summary = {
        "pass": sum(1 for item in checks if item["status"] == "pass"),
        "fail": sum(1 for item in checks if item["status"] == "fail"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.2",
        "gate": "S0_capability_tool_boundary",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 else "fail",
        "summary": summary,
        "artifacts": {"capability_context": str(CAPABILITY_CONTEXT_PATH)},
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    return report


def model_visible_tool_matrix() -> list[dict[str, Any]]:
    plan_document = TacticalQueryDocument.model_validate_json(APPROVED_PLAN_PATH.read_text(encoding="utf-8"))
    submit = dispatch_model_visible(
        ToolDispatchRequest(tool_name="submit_query_plan", arguments={"plan_document": plan_document.model_dump(mode="json")}),
        caller_profile=CallerProfile.HOST_MANUAL,
    )
    validation = dispatch_model_visible(
        ToolDispatchRequest(tool_name="validate_query_plan", arguments={"draft_plan_id": submit["draft_plan_id"]}),
        caller_profile=CallerProfile.HOST_MANUAL,
    )
    authorization = host_confirm_bound_plan(validation["bound_plan_id"])
    execution = dispatch_model_visible(
        ToolDispatchRequest(
            tool_name="execute_query_plan",
            arguments={
                "bound_plan_id": validation["bound_plan_id"],
                "execution_authorization_id": authorization.execution_authorization_id,
                "result_limit": 1,
            },
        ),
        caller_profile=CallerProfile.HOST_MANUAL,
    )
    result_id = execution["results"][0]["result_id"]
    first_result = execution["results"][0]
    target = {
        "schema_version": "1.0",
        "target_id": "model_visible_probe",
        "match_id": first_result["match_id"],
        "period": first_result["period"],
        "approximate_time_ms": 0,
        "search_radius_ms": 250,
    }
    success_args = {
        "list_capabilities": {},
        "search_recipes": {"query": "progressive corridor", "states": ["EXPERIMENTAL"], "limit": 2},
        "describe_capability": {"capability_name": "execute_query_plan"},
        "submit_query_plan": {"plan_document": plan_document.model_dump(mode="json")},
        "validate_query_plan": {"draft_plan_id": submit["draft_plan_id"]},
        "execute_query_plan": {
            "bound_plan_id": validation["bound_plan_id"],
            "execution_authorization_id": authorization.execution_authorization_id,
            "result_limit": 1,
        },
        "inspect_result": {"execution_id": execution["execution_id"], "result_id": result_id},
        "inspect_non_match": {"execution_id": execution["execution_id"], "target": target},
        "retrieve_replay_window": {"execution_id": execution["execution_id"], "result_id": result_id},
    }
    failure_args = {
        "list_capabilities": {"unexpected": True},
        "search_recipes": {"query": "", "limit": 0},
        "describe_capability": {"capability_name": "not_real"},
        "submit_query_plan": {"plan_document": {"not": "a plan"}},
        "validate_query_plan": {"draft_plan_id": "draft_deadbeefdeadbeef"},
        "execute_query_plan": {
            "bound_plan_id": validation["bound_plan_id"],
            "execution_authorization_id": "auth_deadbeefdeadbeef",
        },
        "inspect_result": {"execution_id": execution["execution_id"], "result_id": "missing"},
        "inspect_non_match": {
            "execution_id": execution["execution_id"],
            "target": {**target, "period": "badPeriod"},
        },
        "retrieve_replay_window": {"execution_id": execution["execution_id"]},
    }
    matrix = []
    for tool_name in HERMES_S2_TOOL_NAMES:
        success = dispatch_model_visible(
            ToolDispatchRequest(tool_name=tool_name, arguments=success_args[tool_name]),
            caller_profile=CallerProfile.HOST_MANUAL,
        )
        failure = dispatch_model_visible(
            ToolDispatchRequest(tool_name=tool_name, arguments=failure_args[tool_name]),
            caller_profile=CallerProfile.HOST_MANUAL,
        )
        matrix.append(
            {
                "tool": tool_name,
                "success_ok": success.get("ok", True) is not False,
                "failure_ok": failure.get("ok") is False,
                "failure_code": failure.get("error_code"),
            }
        )
    return matrix


def unsafe_raw_episode_exists_plan() -> dict[str, Any]:
    payload = TacticalQueryDocument.model_validate_json(
        APPROVED_PLAN_PATH.read_text(encoding="utf-8")
    ).model_dump(mode="json")
    possession = deepcopy(payload["draft_plan"]["nodes"][0])
    possession["node_id"] = "possession"
    predicate = {
        "kind": "predicate",
        "node_id": "has_any_possession",
        "input": {"source_node_id": "possession", "output_name": "episodes"},
        "operator": {"name": "exists", "version": "1.0.0"},
    }
    payload["draft_plan"]["plan_id"] = "unsafe_raw_episode_exists"
    payload["draft_plan"]["recipe_id"] = "unsafe_raw_episode_exists"
    payload["draft_plan"]["status"] = "experimental"
    payload["recipe"]["recipe_id"] = "unsafe_raw_episode_exists"
    payload["recipe"]["display_name"] = "Unsafe Raw Episode Exists"
    payload["draft_plan"]["nodes"] = [possession, predicate]
    payload["draft_plan"]["anchor_source"] = {"source_node_id": "possession", "output_name": "anchors"}
    payload["draft_plan"]["requested_evidence"] = []
    payload["draft_plan"]["classification_rules"] = [
        {
            "label": "HAS_POSSESSION",
            "predicate_ids": ["has_any_possession"],
            "description": "Unsafe raw collection fallback test.",
        }
    ]
    payload["recipe"]["output_classifications"] = ["HAS_POSSESSION"]
    payload["default_invocation"]["max_results"] = 5
    return payload


def non_authorable_outcome_plan() -> dict[str, Any]:
    payload = TacticalQueryDocument.model_validate_json(
        APPROVED_PLAN_PATH.read_text(encoding="utf-8")
    ).model_dump(mode="json")
    payload["draft_plan"]["plan_id"] = "unsafe_outcome_authored"
    payload["draft_plan"]["recipe_id"] = "unsafe_outcome_authored"
    payload["draft_plan"]["status"] = "experimental"
    payload["recipe"]["recipe_id"] = "unsafe_outcome_authored"
    payload["recipe"]["display_name"] = "Unsafe Outcome Authored"
    return payload


def clean_handles() -> None:
    """Reset local workshop handles, but never delete tracked (pinned) handle files."""
    handle_root = Path("artifacts/m1.2/workshop/handles")
    if not handle_root.exists():
        return
    tracked = set(
        subprocess.check_output(["git", "ls-files", str(handle_root)], text=True).splitlines()
    )
    for path in sorted(handle_root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_file() and path.as_posix() not in tracked:
            path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def main() -> None:
    report = build_report()
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
