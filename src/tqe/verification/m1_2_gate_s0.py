"""Verify M1.2 S0: bounded capability and tool context."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.ir import TacticalQueryDocument
from tqe.workshop.m1_2 import (
    APPROVED_TOOL_NAMES,
    CAPABILITY_CONTEXT_PATH,
    FORBIDDEN_SURFACES,
    SAFE_ANCHOR_RELATIVE_OUTPUT,
    CapabilityGap,
    ValidateQueryPlanRequest,
    list_capabilities,
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
    context = write_capability_context(CAPABILITY_CONTEXT_PATH)
    checks: list[dict[str, Any]] = []
    tool_names = [tool.name for tool in context.tools]
    checks.append(
        check(
            "s0.tool_surface.exact",
            tool_names == APPROVED_TOOL_NAMES,
            "Hermes-visible tools are exactly the approved S0 surface.",
            {"tools": tool_names},
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
    approved_validation = validate_query_plan(ValidateQueryPlanRequest(plan_path=str(APPROVED_PLAN_PATH)))
    checks.append(
        check(
            "s0.approved_plan.validates",
            approved_validation.ok and bool(approved_validation.bound_plan_hash),
            "Manual plan entry can validate the frozen approved recipe without Hermes.",
            approved_validation.model_dump(mode="json"),
        )
    )
    unsafe_path = Path("artifacts/m1.2/unsafe-raw-episode-exists.plan.json")
    write_json(unsafe_path, unsafe_raw_episode_exists_plan())
    unsafe_validation = validate_query_plan(ValidateQueryPlanRequest(plan_path=str(unsafe_path)))
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


def main() -> None:
    report = build_report()
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
