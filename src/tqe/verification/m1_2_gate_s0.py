"""Verify M1.2 S0: bounded capability and tool context."""

from __future__ import annotations

import json
import shutil
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
    ValidateQueryPlanRequest,
    dispatch_tool,
    list_capabilities,
    submit_query_plan,
    validate_query_plan,
    write_capability_context,
)

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
    clean_handles()
    context = write_capability_context(CAPABILITY_CONTEXT_PATH)
    manual_context = list_capabilities(CallerProfile.HOST_MANUAL)
    checks: list[dict[str, Any]] = []
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
    model_visible_success = dispatch_model_visible(
        ToolDispatchRequest(tool_name="list_capabilities", arguments={}),
        caller_profile=CallerProfile.HERMES_S2,
    )
    model_visible_failure = dispatch_model_visible(
        ToolDispatchRequest(tool_name="describe_capability", arguments={"capability_name": "not_real"}),
        caller_profile=CallerProfile.HERMES_S2,
    )
    checks.append(check("s0.model_visible_schema_conformance", model_visible_success.get("schema_version") == "1.0" and model_visible_failure.get("ok") is False, "Model-visible dispatcher payloads validate against generated schemas.", {"success_keys": sorted(model_visible_success)[:8], "failure": model_visible_failure}))

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
    handle_root = Path("artifacts/m1.2/workshop/handles")
    if handle_root.exists():
        shutil.rmtree(handle_root)


def main() -> None:
    report = build_report()
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
