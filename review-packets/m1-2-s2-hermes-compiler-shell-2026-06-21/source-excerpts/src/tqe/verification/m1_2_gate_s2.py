"""Verify M1.2 S2: bounded Hermes drafting and clarification shell."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.workshop.hermes_s2 import (
    HermesCompileRequest,
    HermesCompileStatus,
    compile_hermes_request,
    record_confirmed_execution_trace,
)
from tqe.workshop.m1_2 import (
    CallerProfile,
    DEFAULT_WORKSHOP_ROOT,
    ToolDispatchRequest,
    dispatch_model_visible,
    host_confirm_bound_plan,
    read_handle,
)

REPORT_PATH = Path("artifacts/m1.2/gate-s2-verification-report.json")
CORPUS_PATH = Path("artifacts/m1.2/agent-evaluation-corpus.json")
TRACE_REPORT_PATH = Path("artifacts/m1.2/hermes-s2-trace-report.json")


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
    clean_s2_artifacts()
    checks: list[dict[str, Any]] = []

    compile_response = compile_hermes_request(
        HermesCompileRequest(
            original_language="Find moments where an open progressive corridor appears from possession.",
            requester="controller",
        )
    )
    checks.append(
        check(
            "s2.hermes_experimental_draft_validated",
            compile_response.status == HermesCompileStatus.DRAFT_VALIDATED
            and bool(compile_response.draft_plan_id)
            and bool(compile_response.bound_plan_id)
            and compile_response.validation_result is not None
            and compile_response.validation_result.get("plan_status") == "experimental"
            and all(call["caller_profile"] == CallerProfile.HERMES_S2.value for call in compile_response.tool_calls),
            "Hermes compiles a supported prompt into a validated experimental draft through the Hermes caller profile.",
            compile_response.model_dump(mode="json"),
        )
    )

    authorization = host_confirm_bound_plan(
        compile_response.bound_plan_id or "",
        reviewer="controller",
    )
    execution = dispatch_model_visible(
        ToolDispatchRequest(
            tool_name="execute_query_plan",
            arguments={
                "bound_plan_id": compile_response.bound_plan_id,
                "execution_authorization_id": authorization.execution_authorization_id,
                "result_limit": 3,
            },
        ),
        caller_profile=CallerProfile.HERMES_S2,
    )
    first_result_id = execution["results"][0]["result_id"]
    inspection = dispatch_model_visible(
        ToolDispatchRequest(
            tool_name="inspect_result",
            arguments={"execution_id": execution["execution_id"], "result_id": first_result_id},
        ),
        caller_profile=CallerProfile.HERMES_S2,
    )
    replay = dispatch_model_visible(
        ToolDispatchRequest(
            tool_name="retrieve_replay_window",
            arguments={"execution_id": execution["execution_id"], "result_id": first_result_id},
        ),
        caller_profile=CallerProfile.HERMES_S2,
    )
    execution_trace = record_confirmed_execution_trace(
        compile_response=compile_response,
        execution_authorization_id=authorization.execution_authorization_id,
        execution=execution,
        inspection=inspection,
        replay=replay,
    )
    checks.append(
        check(
            "s2.hermes_confirmed_execution_grounded",
            execution["total_result_count"] > 0
            and bool(inspection["predicate_traces"])
            and replay["frame_count"] > 0
            and execution_trace["original_language"] == compile_response.original_language,
            "After host confirmation, Hermes executes, inspects, and retrieves replay through the model-visible boundary.",
            {
                "execution_id": execution["execution_id"],
                "result_count": execution["total_result_count"],
                "trace_id": execution_trace["trace_id"],
                "replay_window_id": replay["replay_window_id"],
            },
        )
    )
    checks.append(
        check(
            "s2.confirmation_boundary_preserved",
            authorization.execution_authorization_id not in json.dumps(compile_response.model_dump(mode="json"))
            and not any(call["tool_name"] == "host_confirm_bound_plan" for call in compile_response.tool_calls),
            "Hermes compile output does not mint or receive execution authorization before host confirmation.",
            {"compile_trace_id": compile_response.trace_id},
        )
    )

    ambiguous = compile_hermes_request(
        HermesCompileRequest(original_language="Find when the receiver has support after we break the line.")
    )
    checks.append(
        check(
            "s2.ambiguous_prompt_requests_clarification",
            ambiguous.status == HermesCompileStatus.CLARIFICATION_REQUIRED
            and bool(ambiguous.clarification_questions)
            and ambiguous.draft_plan_id is None,
            "Ambiguous support language asks clarification instead of silently approximating.",
            ambiguous.model_dump(mode="json"),
        )
    )

    unsupported = compile_hermes_request(
        HermesCompileRequest(original_language="Show optimal actions using body orientation, intent, and communication.")
    )
    checks.append(
        check(
            "s2.unsupported_prompt_capability_gap",
            unsupported.status == HermesCompileStatus.CAPABILITY_GAP
            and len(unsupported.capability_gaps) >= 3
            and unsupported.draft_plan_id is None,
            "Unsupported concepts return explicit capability gaps.",
            unsupported.model_dump(mode="json"),
        )
    )

    approved = compile_hermes_request(
        HermesCompileRequest(original_language="Use the approved ball-side block shift recipe.")
    )
    checks.append(
        check(
            "s2.approved_recipe_selected_not_authored",
            approved.status == HermesCompileStatus.EXISTING_RECIPE_SELECTED
            and approved.selected_recipe is not None
            and approved.selected_recipe["state"] == "APPROVED"
            and approved.draft_plan_id is None
            and not any(call["tool_name"] == "submit_query_plan" for call in approved.tool_calls),
            "Approved recipes are selected as trusted host records rather than submitted as Hermes-authored approved documents.",
            approved.model_dump(mode="json"),
        )
    )

    paraphrase = compile_hermes_request(
        HermesCompileRequest(
            original_language="Show possessions where a progressive passing lane opens.",
            requester="controller",
        )
    )
    first_draft_record = read_handle("draft-plans", compile_response.draft_plan_id or "")
    second_draft_record = read_handle("draft-plans", paraphrase.draft_plan_id or "")
    checks.append(
        check(
            "s2.language_trace_survives_shared_plan_handles",
            compile_response.bound_plan_id == paraphrase.bound_plan_id
            and compile_response.trace_id != paraphrase.trace_id
            and compile_response.original_language != paraphrase.original_language
            and first_draft_record["draft_plan_id"] == second_draft_record["draft_plan_id"],
            "Semantically identical drafts can share content handles while each language request keeps its own trace.",
            {
                "first_trace_id": compile_response.trace_id,
                "second_trace_id": paraphrase.trace_id,
                "shared_bound_plan_id": compile_response.bound_plan_id,
                "shared_draft_plan_id": first_draft_record["draft_plan_id"],
            },
        )
    )

    corpus = write_initial_corpus()
    checks.append(
        check(
            "s2.initial_evaluation_corpus_frozen",
            len(corpus["supported"]) == 20
            and len(corpus["ambiguous"]) == 10
            and len(corpus["unsupported"]) == 10,
            "Initial S2 evaluation corpus exists with supported, ambiguous, and unsupported prompts.",
            {"path": str(CORPUS_PATH)},
        )
    )

    trace_report = {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "compile_traces": [
            compile_response.trace_id,
            ambiguous.trace_id,
            unsupported.trace_id,
            approved.trace_id,
            paraphrase.trace_id,
        ],
        "confirmed_execution_trace": execution_trace["trace_id"],
    }
    write_json(TRACE_REPORT_PATH, trace_report)

    summary = {
        "pass": sum(1 for item in checks if item["status"] == "pass"),
        "fail": sum(1 for item in checks if item["status"] == "fail"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.2",
        "gate": "S2_hermes_drafting_and_clarification",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 else "fail",
        "summary": summary,
        "artifacts": {
            "corpus": str(CORPUS_PATH),
            "trace_report": str(TRACE_REPORT_PATH),
        },
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    return report


def write_initial_corpus() -> dict[str, Any]:
    corpus = {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "supported": [
            "Find moments where an open progressive corridor appears from possession.",
            "Show possessions where a progressive passing lane opens.",
            "Detect progressive corridor availability after a possession anchor.",
            "Find geometric corridor opportunities from active-ball possessions.",
            "Show when a forward lane is available from possession.",
            "Find open corridors that progress the ball.",
            "Locate possessions with a progressive lane.",
            "Show corridor availability in the canonical tracking data.",
            "Find possession anchors with a geometric progressive option.",
            "Detect open progressive lanes from the possession start.",
            "Use the experimental corridor recipe for possession moments.",
            "Find moments where a corridor opens for the team in possession.",
            "Show active-ball possessions with a progressive corridor.",
            "Locate progression corridors with enough defender clearance.",
            "Find open forward corridors from possession.",
            "Detect possession-based progressive corridor availability.",
            "Show when possession creates a geometric passing lane.",
            "Find moments with a progressive lane under the corridor thresholds.",
            "Use the approved ball-side block shift recipe.",
            "Find ball-side block shifts with the approved recipe.",
        ],
        "ambiguous": [
            "Find support after we break the line.",
            "Show when the receiver has help.",
            "Find the second runner supporting the attack.",
            "Show line-break support response.",
            "Find defensive support arriving late.",
            "Detect when support is close enough.",
            "Show overload support around the ball.",
            "Find support after progression.",
            "Show teammates helping the ball carrier.",
            "Detect when the team supports a transition.",
        ],
        "unsupported": [
            "Show optimal actions using body orientation.",
            "Find intent to pass through the line.",
            "Detect player communication before the run.",
            "Use video to judge receiver scanning.",
            "Estimate pass probability for each option.",
            "Show what the player should have done.",
            "Detect deception from body shape.",
            "Find optimal tactical decisions.",
            "Infer coach instructions from movement.",
            "Use facial cues to explain intent.",
        ],
    }
    write_json(CORPUS_PATH, corpus)
    return corpus


def clean_s2_artifacts() -> None:
    for path in (CORPUS_PATH, TRACE_REPORT_PATH, REPORT_PATH):
        if path.exists():
            path.unlink()
    if (DEFAULT_WORKSHOP_ROOT / "hermes-traces").exists():
        shutil.rmtree(DEFAULT_WORKSHOP_ROOT / "hermes-traces")


def main() -> None:
    report = build_report()
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
