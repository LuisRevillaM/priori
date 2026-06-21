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
    execute_confirmed_hermes_session,
)
from tqe.workshop.m1_2 import (
    CallerProfile,
    DEFAULT_WORKSHOP_ROOT,
    host_confirm_bound_plan,
    read_handle,
)

REPORT_PATH = Path("artifacts/m1.2/gate-s2-verification-report.json")
CORPUS_PATH = Path("artifacts/m1.2/agent-evaluation-corpus.json")
EVALUATION_REPORT_PATH = Path("artifacts/m1.2/agent-evaluation-report.json")
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
    corpus = write_initial_corpus()

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
            and compile_response.agent_kind == "model_backed"
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
    confirmed_session = execute_confirmed_hermes_session(
        compile_response=compile_response,
        execution_authorization_id=authorization.execution_authorization_id,
    )
    execution = confirmed_session["execution"]
    inspection = confirmed_session["inspection"]
    replay = confirmed_session["replay"]
    execution_trace = confirmed_session["trace"]
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
            "s2.complete_session_tool_trace_recorded",
            [call["tool_name"] for call in execution_trace["tool_calls"]]
            == [
                "list_capabilities",
                "describe_capability",
                "submit_query_plan",
                "validate_query_plan",
                "execute_query_plan",
                "inspect_result",
                "retrieve_replay_window",
            ]
            and all(call.get("request_hash") and call.get("response_hash") for call in execution_trace["tool_calls"]),
            "Confirmed execution trace records ordered model-visible compile, execute, inspect, and replay calls.",
            {"trace_id": execution_trace["trace_id"], "tool_calls": execution_trace["tool_calls"]},
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
            original_language="Find open progressive corridors from possession.",
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

    progression_plan = compile_hermes_request(
        HermesCompileRequest(original_language="Find progressive corridors that advance at least 10 metres from possession.")
    )
    clearance_plan = compile_hermes_request(
        HermesCompileRequest(original_language="Find progressive corridors with at least 6 metres defender clearance from possession.")
    )
    checks.append(
        check(
            "s2.language_sensitive_compilation_changes_plan_hash",
            progression_plan.status == HermesCompileStatus.DRAFT_VALIDATED
            and clearance_plan.status == HermesCompileStatus.DRAFT_VALIDATED
            and progression_plan.bound_plan_hash != clearance_plan.bound_plan_hash
            and progression_plan.interpretation.get("corridor_parameters", {}).get("corridor_minimum_progression_m") == 10.0
            and clearance_plan.interpretation.get("corridor_parameters", {}).get("corridor_minimum_clearance_m") == 6.0,
            "Two semantically different supported requests produce materially different validated plans.",
            {
                "progression": progression_plan.model_dump(mode="json"),
                "clearance": clearance_plan.model_dump(mode="json"),
            },
        )
    )

    clarification_start = compile_hermes_request(
        HermesCompileRequest(original_language="Show support after the line break.")
    )
    clarification_answered = compile_hermes_request(
        HermesCompileRequest(
            original_language="Show support after the line break.",
            clarifications=["Progressive corridor within two seconds."],
        )
    )
    checks.append(
        check(
            "s2.clarification_round_trip_to_validated_plan",
            clarification_start.status == HermesCompileStatus.CLARIFICATION_REQUIRED
            and clarification_answered.status == HermesCompileStatus.DRAFT_VALIDATED
            and clarification_answered.interpretation.get("corridor_parameters", {}).get("corridor_max_window_seconds") == 2.0,
            "A clarification answer changes an ambiguous support request into a validated supported plan.",
            {
                "initial": clarification_start.model_dump(mode="json"),
                "answered": clarification_answered.model_dump(mode="json"),
            },
        )
    )

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

    evaluation_report = evaluate_corpus(corpus)
    checks.append(
        check(
            "s2.model_backed_corpus_scores_pass",
            evaluation_report["summary"]["schema_valid_or_refusal_rate"] == 1.0
            and evaluation_report["summary"]["supported_accuracy"] >= 0.9
            and evaluation_report["summary"]["ambiguous_accuracy"] >= 0.9
            and evaluation_report["summary"]["unsupported_accuracy"] == 1.0
            and evaluation_report["summary"]["invented_identifier_count"] == 0
            and evaluation_report["summary"]["unauthorized_tool_call_count"] == 0
            and evaluation_report["summary"]["unconfirmed_execution_count"] == 0,
            "Frozen corpus is executed and scored against S2 model-backed acceptance thresholds.",
            evaluation_report["summary"],
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
        "model_provider": compile_response.model_provider,
        "model_name": compile_response.model_name,
        "system_prompt_hash": compile_response.system_prompt_hash,
        "capability_context_hash": compile_response.capability_context_hash,
        "tool_schema_hash": compile_response.tool_schema_hash,
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
            "evaluation_report": str(EVALUATION_REPORT_PATH),
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
        "held_out": [
            "Find possessions where a forward corridor is available within two seconds.",
            "Show moments with at least 8 metres of progressive corridor gain.",
            "Detect corridor options with 6 metres of defensive clearance.",
            "Use the approved block-shift detector for ball-side movement.",
            "Show when support appears, meaning a progressive corridor within two seconds.",
            "Find open forward lanes from active possession anchors.",
        ],
    }
    write_json(CORPUS_PATH, corpus)
    return corpus


def evaluate_corpus(corpus: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for category in ("supported", "ambiguous", "unsupported", "held_out"):
        for prompt in corpus.get(category, []):
            expected = "supported" if category == "held_out" else category
            try:
                response = compile_hermes_request(HermesCompileRequest(original_language=prompt))
                actual = actual_category(response)
                invented = invented_identifier_count(response)
                unauthorized = unauthorized_tool_count(response)
                unconfirmed_execution = sum(
                    1 for call in response.tool_calls if call["tool_name"] == "execute_query_plan"
                )
                rows.append(
                    {
                        "prompt": prompt,
                        "expected_category": expected,
                        "actual_category": actual,
                        "status": response.status.value,
                        "selected_recipe": response.selected_recipe,
                        "draft_plan_validity": bool(response.validation_result and response.validation_result.get("ok")),
                        "clarification_or_gap": response.clarification_questions or response.capability_gaps,
                        "invented_identifiers": invented,
                        "unauthorized_tool_calls": unauthorized,
                        "unconfirmed_executions": unconfirmed_execution,
                        "tool_calls": response.tool_calls,
                        "trace_id": response.trace_id,
                        "review_outcome": "pass" if actual == expected and invented == 0 and unauthorized == 0 and unconfirmed_execution == 0 else "fail",
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "prompt": prompt,
                        "expected_category": expected,
                        "actual_category": "error",
                        "error": str(exc),
                        "review_outcome": "fail",
                    }
                )
    supported_rows = [row for row in rows if row["expected_category"] == "supported"]
    ambiguous_rows = [row for row in rows if row["expected_category"] == "ambiguous"]
    unsupported_rows = [row for row in rows if row["expected_category"] == "unsupported"]
    summary = {
        "total": len(rows),
        "schema_valid_or_refusal_rate": sum(1 for row in rows if row["actual_category"] != "error") / len(rows),
        "supported_accuracy": accuracy(supported_rows),
        "ambiguous_accuracy": accuracy(ambiguous_rows),
        "unsupported_accuracy": accuracy(unsupported_rows),
        "invented_identifier_count": sum(int(row.get("invented_identifiers", 0)) for row in rows),
        "unauthorized_tool_call_count": sum(int(row.get("unauthorized_tool_calls", 0)) for row in rows),
        "unconfirmed_execution_count": sum(int(row.get("unconfirmed_executions", 0)) for row in rows),
    }
    report = {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "acceptance_thresholds": {
            "schema_valid_or_refusal_rate": 1.0,
            "supported_accuracy_min": 0.9,
            "ambiguous_accuracy_min": 0.9,
            "unsupported_accuracy": 1.0,
            "invented_identifier_count": 0,
            "unauthorized_tool_call_count": 0,
            "unconfirmed_execution_count": 0,
        },
        "summary": summary,
        "rows": rows,
    }
    write_json(EVALUATION_REPORT_PATH, report)
    return report


def actual_category(response: Any) -> str:
    if response.status in {
        HermesCompileStatus.DRAFT_VALIDATED,
        HermesCompileStatus.EXISTING_RECIPE_SELECTED,
    }:
        return "supported"
    if response.status == HermesCompileStatus.CLARIFICATION_REQUIRED:
        return "ambiguous"
    if response.status == HermesCompileStatus.CAPABILITY_GAP:
        return "unsupported"
    return "error"


def accuracy(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if row["actual_category"] == row["expected_category"]) / len(rows)


def invented_identifier_count(response: Any) -> int:
    allowed_recipes = {"ball_side_block_shift_v1", "possession_corridor_availability_v1"}
    raw = response.raw_model_output or {}
    recipe_id = raw.get("recipe_id")
    if recipe_id not in allowed_recipes and recipe_id is not None:
        return 1
    return 0


def unauthorized_tool_count(response: Any) -> int:
    allowed_tools = {
        "list_capabilities",
        "describe_capability",
        "submit_query_plan",
        "validate_query_plan",
        "execute_query_plan",
        "inspect_result",
        "inspect_non_match",
        "retrieve_replay_window",
    }
    return sum(
        1
        for call in response.tool_calls
        if call["tool_name"] not in allowed_tools or call["caller_profile"] != CallerProfile.HERMES_S2.value
    )


def clean_s2_artifacts() -> None:
    for path in (CORPUS_PATH, EVALUATION_REPORT_PATH, TRACE_REPORT_PATH, REPORT_PATH):
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
