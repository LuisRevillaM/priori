"""Verify N1B capability output domains and runtime parameter contract."""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.ir import TacticalQueryDocument
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
    write_json(CORRECTED_PLAN_PATH, document)
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


def build_report() -> dict[str, Any]:
    N1B_ROOT.mkdir(parents=True, exist_ok=True)
    failed_validation = exact_failed_validation()
    corrected = submit_validate_execute_corrected()
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
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
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
