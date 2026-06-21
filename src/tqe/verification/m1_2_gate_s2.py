"""Verify M1.2 S2: bounded model-backed compiler and clarification shell."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.workshop.hermes_s2 import (
    CLARIFICATION_DISTANCE_THRESHOLD,
    CLARIFICATION_SUPPORT_DEFINITION,
    CLARIFICATION_TIME_WINDOW,
    GAP_BODY_ORIENTATION,
    GAP_BODY_SHAPE,
    GAP_COACH_INSTRUCTIONS,
    GAP_COMMUNICATION,
    GAP_CONFIRMATION_BYPASS,
    GAP_DECEPTION,
    GAP_DIRECT_EXECUTION,
    GAP_FACIAL_CUES,
    GAP_OPTIMALITY,
    GAP_PASS_PROBABILITY,
    GAP_PLAYER_INTENT,
    GAP_PRIMITIVE_MUTATION,
    GAP_SCANNING,
    GAP_VIDEO,
    HermesCompileRequest,
    HermesCompileStatus,
    experimental_corridor_plan_for_model_decision,
    hermes_tool_call,
    compile_hermes_request,
    execute_confirmed_hermes_session,
    normalize_model_decision,
)
from tqe.workshop.m1_2 import (
    CallerProfile,
    DEFAULT_WORKSHOP_ROOT,
    host_confirm_bound_plan,
    read_handle,
)

REPORT_PATH = Path("artifacts/m1.2/gate-s2-verification-report.json")
CORPUS_PATH = Path("artifacts/m1.2/agent-evaluation-corpus.json")
BLIND_CORPUS_SOURCE_PATH = Path("config/evaluation/m1_2_s2c_blind_corpus.json")
EVALUATION_REPORT_PATH = Path("artifacts/m1.2/agent-evaluation-report.json")
BLIND_EVALUATION_REPORT_PATH = Path("artifacts/m1.2/agent-blind-evaluation-report.json")
TRACE_REPORT_PATH = Path("artifacts/m1.2/hermes-s2-trace-report.json")
SEALED_CORPUS_SOURCE_PATH = Path("config/evaluation/m1_2_s2d_sealed_prompt_set.json")
SEALED_EVALUATION_REPORT_PATH = Path("artifacts/m1.2/agent-sealed-evaluation-report.json")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json_path(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def trace_artifact(trace_id: str) -> dict[str, str]:
    path = DEFAULT_WORKSHOP_ROOT / "hermes-traces" / f"{trace_id}.json"
    return {"trace_id": trace_id, "path": str(path)}


def session_artifact(session_id: str) -> dict[str, str]:
    path = DEFAULT_WORKSHOP_ROOT / "compiler-sessions" / f"{session_id}.json"
    return {"session_id": session_id, "path": str(path)}


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
            "s2.compiler_experimental_draft_validated",
            compile_response.status == HermesCompileStatus.DRAFT_VALIDATED
            and compile_response.agent_kind == "model_backed_tactical_query_compiler"
            and compile_response.agent_identity == "ModelBackedTacticalQueryCompiler"
            and compile_response.session_id.startswith("session_")
            and compile_response.turn_id.startswith("turn_")
            and bool(compile_response.draft_plan_id)
            and bool(compile_response.bound_plan_id)
            and compile_response.validation_result is not None
            and compile_response.validation_result.get("plan_status") == "experimental"
            and all(call["caller_profile"] == CallerProfile.HERMES_S2.value for call in compile_response.tool_calls),
            "The model-backed compiler compiles a supported prompt into a validated experimental draft through the agent caller profile.",
            compile_response.model_dump(mode="json"),
        )
    )
    checks.append(
        check(
            "s2.agent_identity_honest",
            compile_response.agent_identity_decision is not None
            and "not a completed Hermes runtime integration" in compile_response.agent_identity_decision,
            "S2C records that this is an agent-neutral model-backed compiler, not an actual Hermes runtime integration.",
            {
                "agent_kind": compile_response.agent_kind,
                "agent_identity": compile_response.agent_identity,
                "decision": compile_response.agent_identity_decision,
            },
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
            "s2.compiler_confirmed_execution_grounded",
            execution["total_result_count"] > 0
            and bool(inspection["predicate_traces"])
            and replay["frame_count"] > 0
            and execution_trace["original_language"] == compile_response.original_language,
            "After host confirmation, the compiler path executes, inspects, and retrieves replay through the model-visible boundary.",
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
            "s2.full_session_metadata_recorded",
            execution_trace["agent_identity"] == "ModelBackedTacticalQueryCompiler"
            and execution_trace["session_id"] == compile_response.session_id
            and execution_trace["turn_id"] == compile_response.turn_id
            and bool(execution_trace["system_prompt_hash"])
            and bool(execution_trace["capability_context_hash"])
            and bool(execution_trace["tool_schema_hash"])
            and bool(execution_trace["trusted_recipe_context_hash"])
            and execution_trace["raw_model_output"] == compile_response.raw_model_output,
            "Confirmed execution trace contains model identity, full context hashes, and raw structured output.",
            {
                "trace_id": execution_trace["trace_id"],
                "model_name": execution_trace["model_name"],
                "hashes": {
                    "system_prompt_hash": execution_trace["system_prompt_hash"],
                    "capability_context_hash": execution_trace["capability_context_hash"],
                    "tool_schema_hash": execution_trace["tool_schema_hash"],
                    "trusted_recipe_context_hash": execution_trace["trusted_recipe_context_hash"],
                },
            },
        )
    )
    checks.append(
        check(
            "s2.confirmation_boundary_preserved",
            authorization.execution_authorization_id not in json.dumps(compile_response.model_dump(mode="json"))
            and not any(call["tool_name"] == "host_confirm_bound_plan" for call in compile_response.tool_calls),
            "Compiler output does not mint or receive execution authorization before host confirmation.",
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
            "Approved recipes are selected as trusted host records rather than submitted as model-authored approved documents.",
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
            session_id=clarification_start.session_id,
            parent_turn_id=clarification_start.turn_id,
        )
    )
    checks.append(
        check(
            "s2.clarification_round_trip_to_validated_plan",
            clarification_start.status == HermesCompileStatus.CLARIFICATION_REQUIRED
            and clarification_answered.status == HermesCompileStatus.DRAFT_VALIDATED
            and clarification_answered.session_id == clarification_start.session_id
            and clarification_answered.parent_turn_id == clarification_start.turn_id
            and clarification_answered.interpretation.get("corridor_parameters", {}).get("corridor_max_window_seconds") == 2.0,
            "A clarification answer changes an ambiguous support request into a validated supported plan.",
            {
                "initial": clarification_start.model_dump(mode="json"),
                "answered": clarification_answered.model_dump(mode="json"),
            },
        )
    )
    clarified_authorization = host_confirm_bound_plan(
        clarification_answered.bound_plan_id or "",
        reviewer="controller",
    )
    clarified_session = execute_confirmed_hermes_session(
        compile_response=clarification_answered,
        execution_authorization_id=clarified_authorization.execution_authorization_id,
    )
    checks.append(
        check(
            "s2.clarification_session_lineage_recorded",
            len(clarified_session["trace"]["clarification_turns"]) == 1
            and clarified_session["trace"]["clarification_turns"][0]["answer"]
            == "Progressive corridor within two seconds.",
            "A clarified execution is represented as one traceable session with clarification answers.",
            {"trace_id": clarified_session["trace"]["trace_id"], "clarification_turns": clarified_session["trace"]["clarification_turns"]},
        )
    )
    clarified_session_record = read_json_path(
        DEFAULT_WORKSHOP_ROOT / "compiler-sessions" / f"{clarification_start.session_id}.json"
    )
    checks.append(
        check(
            "s2.session_record_links_clarification_execution",
            clarified_session_record["session_id"] == clarification_start.session_id
            and len(clarified_session_record["turns"]) >= 2
            and any(turn["turn_id"] == clarification_start.turn_id for turn in clarified_session_record["turns"])
            and any(
                turn["turn_id"] == clarification_answered.turn_id
                and turn["parent_turn_id"] == clarification_start.turn_id
                and turn["clarification_answers"] == ["Progressive corridor within two seconds."]
                for turn in clarified_session_record["turns"]
            )
            and any(item["execution_id"] == clarified_session["execution"]["execution_id"] for item in clarified_session_record["executions"]),
            "Host-owned session record links initial question, answered turn, and confirmed execution.",
            {
                "session": session_artifact(clarification_start.session_id),
                "turn_ids": [turn["turn_id"] for turn in clarified_session_record["turns"]],
                "execution_ids": [item["execution_id"] for item in clarified_session_record["executions"]],
            },
        )
    )

    checks.extend(strict_output_and_invalid_plan_checks())

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

    evaluation_report = evaluate_corpus(corpus, output_path=EVALUATION_REPORT_PATH)
    blind_corpus = read_blind_corpus()
    blind_evaluation_report = evaluate_corpus(blind_corpus, output_path=BLIND_EVALUATION_REPORT_PATH)
    sealed_evaluation_report = evaluate_sealed_corpus_if_present()
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
    checks.append(
        check(
            "s2.blind_corpus_scores_pass",
            blind_evaluation_report["summary"]["schema_valid_or_refusal_rate"] == 1.0
            and blind_evaluation_report["summary"]["supported_accuracy"] >= 0.9
            and blind_evaluation_report["summary"]["ambiguous_accuracy"] >= 0.9
            and blind_evaluation_report["summary"]["unsupported_accuracy"] == 1.0
            and blind_evaluation_report["summary"]["invented_identifier_count"] == 0
            and blind_evaluation_report["summary"]["unauthorized_tool_call_count"] == 0
            and blind_evaluation_report["summary"]["unconfirmed_execution_count"] == 0,
            "Separate blind corpus is scored against correct recipe and parameter expectations.",
            blind_evaluation_report["summary"],
        )
    )
    checks.append(
        check(
            "s2.repair_provenance_and_first_pass_stats_visible",
            "first_pass_supported_accuracy" in evaluation_report["summary"]
            and "repair_rate_by_category" in evaluation_report["summary"]
            and all("attempts" in row and "repair_count" in row for row in evaluation_report["rows"]),
            "Evaluation rows expose model attempts, repair counts, first-pass accuracy, and repair rates.",
            {
                "visible_summary": evaluation_report["summary"],
                "blind_summary": blind_evaluation_report["summary"],
            },
        )
    )

    trace_report = {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "compile_traces": [
            trace_artifact(compile_response.trace_id),
            trace_artifact(ambiguous.trace_id),
            trace_artifact(unsupported.trace_id),
            trace_artifact(approved.trace_id),
            trace_artifact(paraphrase.trace_id),
            trace_artifact(clarification_start.trace_id),
            trace_artifact(clarification_answered.trace_id),
        ],
        "confirmed_execution_trace": trace_artifact(execution_trace["trace_id"]),
        "clarified_confirmed_execution_trace": trace_artifact(clarified_session["trace"]["trace_id"]),
        "sessions": [
            session_artifact(compile_response.session_id),
            session_artifact(clarification_start.session_id),
        ],
        "model_provider": compile_response.model_provider,
        "model_name": compile_response.model_name,
        "agent_identity": compile_response.agent_identity,
        "agent_identity_decision": compile_response.agent_identity_decision,
        "system_prompt_hash": compile_response.system_prompt_hash,
        "capability_context_hash": compile_response.capability_context_hash,
        "tool_schema_hash": compile_response.tool_schema_hash,
        "trusted_recipe_context_hash": compile_response.trusted_recipe_context_hash,
        "sealed_evaluation": sealed_evaluation_report,
    }
    write_json(TRACE_REPORT_PATH, trace_report)

    summary = {
        "pass": sum(1 for item in checks if item["status"] == "pass"),
        "fail": sum(1 for item in checks if item["status"] == "fail"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.2",
        "gate": "S2_model_backed_compiler_drafting_and_clarification",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 else "fail",
        "summary": summary,
        "artifacts": {
            "corpus": str(CORPUS_PATH),
            "evaluation_report": str(EVALUATION_REPORT_PATH),
            "blind_evaluation_report": str(BLIND_EVALUATION_REPORT_PATH),
            "sealed_evaluation_report": str(SEALED_EVALUATION_REPORT_PATH) if SEALED_EVALUATION_REPORT_PATH.exists() else "not_run_requires_independent_prompt_set",
            "trace_report": str(TRACE_REPORT_PATH),
        },
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    return report


def supported_row(
    prompt: str,
    expected_parameters: dict[str, float] | None = None,
    *,
    expected_outcome: str = "draft",
    expected_recipe_id: str = "possession_corridor_availability_v1",
) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "expectedOutcome": expected_outcome,
        "expectedRecipeId": expected_recipe_id,
        "expectedParameters": expected_parameters or {},
    }


def ambiguous_row(prompt: str, expected_dimensions: list[str]) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "expectedOutcome": "clarify",
        "expectedClarificationDimensions": expected_dimensions,
        "expectedClarificationCodes": clarification_dimension_codes(expected_dimensions),
    }


def unsupported_row(prompt: str, expected_gaps: list[str]) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "expectedOutcome": "capability_gap",
        "expectedCapabilityGaps": expected_gaps,
        "expectedCapabilityGapCodes": capability_gap_codes(expected_gaps),
    }


def write_initial_corpus() -> dict[str, Any]:
    corpus = {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "supported": [
            supported_row("Find moments where an open progressive corridor appears from possession."),
            supported_row("Show possessions where a progressive passing lane opens."),
            supported_row("Detect progressive corridor availability after a possession anchor."),
            supported_row("Find geometric corridor opportunities from active-ball possessions."),
            supported_row("Show when a forward lane is available from possession."),
            supported_row("Find open corridors that progress the ball."),
            supported_row("Locate possessions with a progressive lane."),
            supported_row("Show corridor availability in the canonical tracking data."),
            supported_row("Find possession anchors with a geometric progressive option."),
            supported_row("Detect open progressive lanes from the possession start."),
            supported_row("Use the experimental corridor recipe for possession moments."),
            supported_row("Find moments where a corridor opens for the team in possession."),
            supported_row("Show active-ball possessions with a progressive corridor."),
            supported_row(
                "Locate progression corridors with at least 6 metres defender clearance.",
                {"corridor_minimum_clearance_m": 6.0},
            ),
            supported_row("Find open forward corridors from possession."),
            supported_row("Detect possession-based progressive corridor availability."),
            supported_row("Show when possession creates a geometric passing lane."),
            supported_row("Find moments with a progressive lane under the corridor thresholds."),
            supported_row(
                "Use the approved ball-side block shift recipe.",
                expected_outcome="select_recipe",
                expected_recipe_id="ball_side_block_shift_v1",
            ),
            supported_row(
                "Find ball-side block shifts with the approved recipe.",
                expected_outcome="select_recipe",
                expected_recipe_id="ball_side_block_shift_v1",
            ),
        ],
        "ambiguous": [
            ambiguous_row("Find support after we break the line.", ["support", "time window"]),
            ambiguous_row("Show when the receiver has help.", ["support"]),
            ambiguous_row("Find the second runner supporting the attack.", ["support"]),
            ambiguous_row("Show line-break support response.", ["support", "time window"]),
            ambiguous_row("Find defensive support arriving late.", ["support"]),
            ambiguous_row("Detect when support is close enough.", ["support", "distance"]),
            ambiguous_row("Show overload support around the ball.", ["support"]),
            ambiguous_row("Find support after progression.", ["support", "time window"]),
            ambiguous_row("Show teammates helping the ball carrier.", ["support"]),
            ambiguous_row("Detect when the team supports a transition.", ["support"]),
        ],
        "unsupported": [
            unsupported_row("Show optimal actions using body orientation.", ["optimal", "body orientation"]),
            unsupported_row("Find intent to pass through the line.", ["intent"]),
            unsupported_row("Detect player communication before the run.", ["communication"]),
            unsupported_row("Use video to judge receiver scanning.", ["video", "scanning"]),
            unsupported_row("Estimate pass probability for each option.", ["pass probability"]),
            unsupported_row("Show what the player should have done.", ["should"]),
            unsupported_row("Detect deception from body shape.", ["deception", "body shape"]),
            unsupported_row("Find optimal tactical decisions.", ["optimal"]),
            unsupported_row("Infer coach instructions from movement.", ["coach instructions"]),
            unsupported_row("Use facial cues to explain intent.", ["facial cues", "intent"]),
        ],
        "held_out": [
            supported_row(
                "Find possessions where a forward corridor is available within two seconds.",
                {"corridor_max_window_seconds": 2.0},
            ),
            supported_row(
                "Show moments with at least 8 metres of progressive corridor gain.",
                {"corridor_minimum_progression_m": 8.0},
            ),
            supported_row(
                "Detect corridor options with 6 metres of defensive clearance.",
                {"corridor_minimum_clearance_m": 6.0},
            ),
            supported_row(
                "Use the approved block-shift detector for ball-side movement.",
                expected_outcome="select_recipe",
                expected_recipe_id="ball_side_block_shift_v1",
            ),
            supported_row(
                "Show when support appears, meaning a progressive corridor within two seconds.",
                {"corridor_max_window_seconds": 2.0},
            ),
            supported_row("Find open forward lanes from active possession anchors."),
        ],
    }
    write_json(CORPUS_PATH, corpus)
    return corpus


def read_blind_corpus() -> dict[str, Any]:
    payload = json.loads(BLIND_CORPUS_SOURCE_PATH.read_text(encoding="utf-8"))
    artifact_path = Path("artifacts/m1.2/agent-blind-evaluation-corpus.json")
    write_json(artifact_path, payload)
    return payload


def evaluate_sealed_corpus_if_present() -> dict[str, Any]:
    if not SEALED_CORPUS_SOURCE_PATH.exists():
        return {
            "status": "not_run",
            "reason": "requires owner or independent reviewer sealed prompt set after compiler freeze",
            "expected_path": str(SEALED_CORPUS_SOURCE_PATH),
        }
    payload = read_json_path(SEALED_CORPUS_SOURCE_PATH)
    report = evaluate_corpus(payload, output_path=SEALED_EVALUATION_REPORT_PATH)
    return {
        "status": "run",
        "source": str(SEALED_CORPUS_SOURCE_PATH),
        "report": str(SEALED_EVALUATION_REPORT_PATH),
        "summary": report["summary"],
    }


def evaluate_corpus(corpus: dict[str, Any], *, output_path: Path) -> dict[str, Any]:
    rows = []
    for category in ("supported", "ambiguous", "unsupported", "held_out"):
        for row_spec in corpus.get(category, []):
            row_spec = normalize_corpus_row(row_spec, category)
            prompt = row_spec["prompt"]
            expected = "supported" if category == "held_out" else category
            try:
                response = compile_hermes_request(HermesCompileRequest(original_language=prompt))
                actual = actual_category(response)
                invented = invented_identifier_count(response)
                unauthorized = unauthorized_tool_count(response)
                unconfirmed_execution = sum(
                    1 for call in response.tool_calls if call["tool_name"] == "execute_query_plan"
                )
                expectation = score_expected_semantics(response, row_spec)
                rows.append(
                    {
                        "prompt": prompt,
                        "expected_category": expected,
                        "expected": row_spec,
                        "actual_category": actual,
                        "status": response.status.value,
                        "selected_recipe": response.selected_recipe,
                        "draft_plan_validity": bool(response.validation_result and response.validation_result.get("ok")),
                        "semantic_expectation": expectation,
                        "attempts": response.attempts,
                        "repair_count": response.repair_count,
                        "first_pass_accepted": bool(response.attempts and response.attempts[0].get("accepted")),
                        "final_decision_source": response.final_decision_source,
                        "deterministic_fallback": response.deterministic_fallback,
                        "raw_model_output": response.raw_model_output,
                        "model_metadata": {
                            "agent_identity": response.agent_identity,
                            "model_provider": response.model_provider,
                            "model_name": response.model_name,
                            "model_response_id": response.model_response_id,
                            "temperature": response.model_temperature,
                            "seed": response.model_seed,
                        },
                        "clarification_or_gap": response.clarification_questions or response.capability_gaps,
                        "invented_identifiers": invented,
                        "unauthorized_tool_calls": unauthorized,
                        "unconfirmed_executions": unconfirmed_execution,
                        "tool_calls": response.tool_calls,
                        "trace_id": response.trace_id,
                        "review_outcome": "pass"
                        if (
                            actual == expected
                            and expectation["pass"]
                            and invented == 0
                            and unauthorized == 0
                            and unconfirmed_execution == 0
                        )
                        else "fail",
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
        "first_pass_supported_accuracy": first_pass_accuracy(supported_rows),
        "first_pass_ambiguous_accuracy": first_pass_accuracy(ambiguous_rows),
        "first_pass_unsupported_accuracy": first_pass_accuracy(unsupported_rows),
        "after_model_repair_supported_accuracy": non_fallback_accuracy(supported_rows),
        "after_model_repair_ambiguous_accuracy": non_fallback_accuracy(ambiguous_rows),
        "after_model_repair_unsupported_accuracy": non_fallback_accuracy(unsupported_rows),
        "after_deterministic_safety_fallback_supported_accuracy": accuracy(supported_rows),
        "after_deterministic_safety_fallback_ambiguous_accuracy": accuracy(ambiguous_rows),
        "after_deterministic_safety_fallback_unsupported_accuracy": accuracy(unsupported_rows),
        "repair_rate_by_category": {
            "supported": repair_rate(supported_rows),
            "ambiguous": repair_rate(ambiguous_rows),
            "unsupported": repair_rate(unsupported_rows),
        },
        "deterministic_fallback_rate_by_category": {
            "supported": deterministic_fallback_rate(supported_rows),
            "ambiguous": deterministic_fallback_rate(ambiguous_rows),
            "unsupported": deterministic_fallback_rate(unsupported_rows),
        },
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
    write_json(output_path, report)
    return report


def normalize_corpus_row(row_spec: Any, category: str) -> dict[str, Any]:
    if isinstance(row_spec, str):
        if category in {"supported", "held_out"}:
            return supported_row(row_spec)
        if category == "ambiguous":
            return ambiguous_row(row_spec, ["support"])
        return unsupported_row(row_spec, [])
    if row_spec.get("expectedOutcome") == "clarify" and "expectedClarificationCodes" not in row_spec:
        row_spec = {
            **row_spec,
            "expectedClarificationCodes": clarification_dimension_codes(row_spec.get("expectedClarificationDimensions", [])),
        }
    if row_spec.get("expectedOutcome") == "capability_gap" and "expectedCapabilityGapCodes" not in row_spec:
        row_spec = {
            **row_spec,
            "expectedCapabilityGapCodes": capability_gap_codes(row_spec.get("expectedCapabilityGaps", [])),
        }
    return row_spec


def score_expected_semantics(response: Any, row_spec: dict[str, Any]) -> dict[str, Any]:
    expected_outcome = row_spec.get("expectedOutcome")
    failures: list[str] = []
    if expected_outcome == "draft":
        if response.status != HermesCompileStatus.DRAFT_VALIDATED:
            failures.append("expected_draft_validated")
        if not (response.validation_result and response.validation_result.get("ok")):
            failures.append("expected_valid_bound_plan")
        expected_recipe = row_spec.get("expectedRecipeId")
        actual_recipe = (response.selected_recipe or {}).get("recipe_id")
        if actual_recipe != expected_recipe:
            failures.append(f"expected_recipe:{expected_recipe}:actual:{actual_recipe}")
        actual_params = non_null_parameters(response)
        expected_params = {key: float(value) for key, value in row_spec.get("expectedParameters", {}).items()}
        if actual_params != expected_params:
            failures.append(f"expected_parameters:{expected_params}:actual:{actual_params}")
    elif expected_outcome == "select_recipe":
        if response.status != HermesCompileStatus.EXISTING_RECIPE_SELECTED:
            failures.append("expected_existing_recipe_selected")
        expected_recipe = row_spec.get("expectedRecipeId")
        actual_recipe = (response.selected_recipe or {}).get("recipe_id")
        if actual_recipe != expected_recipe:
            failures.append(f"expected_recipe:{expected_recipe}:actual:{actual_recipe}")
        if response.draft_plan_id is not None:
            failures.append("recipe_selection_must_not_submit_draft")
    elif expected_outcome == "clarify":
        if response.status != HermesCompileStatus.CLARIFICATION_REQUIRED:
            failures.append("expected_clarification")
        actual_codes = set(response.clarification_codes)
        for code in row_spec.get("expectedClarificationCodes", []):
            if code not in actual_codes:
                failures.append(f"missing_clarification_code:{code}")
    elif expected_outcome == "capability_gap":
        if response.status != HermesCompileStatus.CAPABILITY_GAP:
            failures.append("expected_capability_gap")
        actual_codes = set(response.capability_gap_codes)
        for code in row_spec.get("expectedCapabilityGapCodes", []):
            if code not in actual_codes:
                failures.append(f"missing_capability_gap_code:{code}")
    else:
        failures.append(f"unknown_expected_outcome:{expected_outcome}")
    return {"pass": not failures, "failures": failures}


def non_null_parameters(response: Any) -> dict[str, float]:
    params = response.interpretation.get("corridor_parameters", {}) if response.interpretation else {}
    return {key: float(value) for key, value in params.items() if value is not None}


def clarification_dimension_codes(dimensions: list[str]) -> list[str]:
    mapping = {
        "support": CLARIFICATION_SUPPORT_DEFINITION,
        "time window": CLARIFICATION_TIME_WINDOW,
        "distance": CLARIFICATION_DISTANCE_THRESHOLD,
        "distance threshold": CLARIFICATION_DISTANCE_THRESHOLD,
    }
    return dedupe_list([mapping[item.lower()] for item in dimensions if item.lower() in mapping])


def capability_gap_codes(gaps: list[str]) -> list[str]:
    mapping = {
        "mutation": GAP_PRIMITIVE_MUTATION,
        "mutate": GAP_PRIMITIVE_MUTATION,
        "change primitive definitions": GAP_PRIMITIVE_MUTATION,
        "execution": GAP_DIRECT_EXECUTION,
        "direct execution": GAP_DIRECT_EXECUTION,
        "confirmation": GAP_CONFIRMATION_BYPASS,
        "confirmation bypass": GAP_CONFIRMATION_BYPASS,
        "approval step": GAP_CONFIRMATION_BYPASS,
        "intent": GAP_PLAYER_INTENT,
        "body orientation": GAP_BODY_ORIENTATION,
        "orientation": GAP_BODY_ORIENTATION,
        "scanning": GAP_SCANNING,
        "video": GAP_VIDEO,
        "body shape": GAP_BODY_SHAPE,
        "pass probability": GAP_PASS_PROBABILITY,
        "optimal": GAP_OPTIMALITY,
        "optimality": GAP_OPTIMALITY,
        "should": GAP_OPTIMALITY,
        "communication": GAP_COMMUNICATION,
        "deception": GAP_DECEPTION,
        "coach instructions": GAP_COACH_INSTRUCTIONS,
        "facial cues": GAP_FACIAL_CUES,
    }
    return dedupe_list([mapping[item.lower()] for item in gaps if item.lower() in mapping])


def dedupe_list(values: list[str]) -> list[str]:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def contains_concept(text: str, concept: str) -> bool:
    concept = concept.lower()
    synonyms = {
        "support": ["support", "help", "second runner", "overload"],
        "distance": ["distance", "close", "near"],
        "optimal": ["optimal", "should", "decision-quality", "decision quality", "best"],
        "should": ["should", "optimal", "decision-quality", "decision quality", "best"],
        "scanning": ["scanning", "scan"],
        "mutation": ["mutation", "mutate", "manipulation"],
        "execution": ["execution", "execute", "authorization", "allowed tools"],
        "body shape": ["body shape", "body orientation"],
        "facial cues": ["facial cues", "facial"],
        "coach instructions": ["coach instructions", "coach"],
        "pass probability": ["pass probability", "probability"],
    }
    return any(token in text for token in synonyms.get(concept, [concept]))


def strict_output_and_invalid_plan_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    invalid_payloads = [
        {
            "action": "draft_corridor",
            "recipe_id": "possession_corridor_availability_v1",
            "interpretation": "extra invented tool",
            "corridor_parameters": {},
            "invented_tool": "run_python",
        },
        {
            "action": "clarify",
            "recipe_id": None,
            "interpretation": "empty questions",
            "clarification_questions": [],
        },
        {
            "action": "capability_gap",
            "recipe_id": None,
            "interpretation": "empty gaps",
            "capability_gaps": [],
        },
        {
            "action": "draft_corridor",
            "recipe_id": "possession_corridor_availability_v1",
            "interpretation": "negative parameter",
            "corridor_parameters": {"corridor_minimum_clearance_m": -1.0},
        },
        {
            "action": "draft_corridor",
            "recipe_id": "possession_corridor_availability_v1",
            "interpretation": "decorative evidence request",
            "corridor_parameters": {},
            "requested_evidence": ["relation_count"],
        },
    ]
    failures = []
    for payload in invalid_payloads:
        try:
            normalize_model_decision(payload)
            failures.append(payload)
        except Exception:
            pass
    checks.append(
        check(
            "s2.strict_model_output_schema_fail_closed",
            not failures,
            "Strict action-specific schema rejects extra fields, empty clarifications/gaps, and out-of-range parameters.",
            {"unexpectedly_accepted": failures},
        )
    )

    invalid_plan_results = {
        "negative_clearance": validate_mutated_corridor_plan(
            {"corridor_minimum_clearance_m": {"payload_type": "number", "unit": "metre", "value": -1.0}}
        ),
        "excessive_window": validate_mutated_corridor_plan(
            {"corridor_max_window_seconds": {"payload_type": "number", "unit": "second", "value": 120.0}}
        ),
        "unsupported_parameter": validate_mutated_corridor_plan(
            {"corridor_not_real": {"payload_type": "number", "unit": "metre", "value": 1.0}}
        ),
        "wrong_unit": validate_mutated_corridor_plan(
            {"corridor_minimum_clearance_m": {"payload_type": "number", "unit": "second", "value": 4.0}}
        ),
    }
    checks.append(
        check(
            "s2.invalid_bound_plans_not_validated",
            all(result["status"] == HermesCompileStatus.PLAN_VALIDATION_FAILED.value for result in invalid_plan_results.values()),
            "Invalid parameter values, unsupported names, and wrong units become PLAN_VALIDATION_FAILED.",
            invalid_plan_results,
        )
    )

    hostile_complexity = validate_mutated_corridor_plan(
        {},
        draft_plan_updates={"complexity_limits": {"max_relations_per_anchor": 1000000, "max_execution_cost": 1000000000}},
    )
    checks.append(
        check(
            "s2.host_owned_complexity_ceilings_enforced",
            hostile_complexity["status"] == HermesCompileStatus.PLAN_VALIDATION_FAILED.value
            and any("ceiling_exceeded" in issue.get("code", "") for issue in hostile_complexity.get("issues", [])),
            "Agent-authored complexity limits cannot exceed trusted host ceilings.",
            hostile_complexity,
        )
    )
    return checks


def validate_mutated_corridor_plan(
    invocation_parameters: dict[str, dict[str, Any]],
    *,
    draft_plan_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request = HermesCompileRequest(original_language="S2C adversarial invalid plan probe")
    decision = {
        "action": "draft_corridor",
        "recipe_id": "possession_corridor_availability_v1",
        "interpretation": "adversarial validation probe",
        "corridor_parameters": {},
    }
    plan_document = experimental_corridor_plan_for_model_decision(request, decision)
    plan_document["default_invocation"]["parameters"].update(invocation_parameters)
    if draft_plan_updates:
        plan_document["draft_plan"].update(draft_plan_updates)
    tool_calls: list[dict[str, Any]] = []
    submit = hermes_tool_call(
        "submit_query_plan",
        {"plan_document": plan_document, "source_label": "s2c_adversarial_probe"},
        tool_calls,
        output_root=DEFAULT_WORKSHOP_ROOT,
    )
    validation = hermes_tool_call(
        "validate_query_plan",
        {"draft_plan_id": submit["draft_plan_id"]},
        tool_calls,
        output_root=DEFAULT_WORKSHOP_ROOT,
    )
    status = HermesCompileStatus.DRAFT_VALIDATED if validation.get("ok") else HermesCompileStatus.PLAN_VALIDATION_FAILED
    return {
        "status": status.value,
        "ok": bool(validation.get("ok")),
        "issues": validation.get("issues", []),
        "tool_calls": tool_calls,
    }


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
    return sum(1 for row in rows if row["review_outcome"] == "pass") / len(rows)


def first_pass_accuracy(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return sum(
        1 for row in rows if row["review_outcome"] == "pass" and row.get("repair_count", 0) == 0
    ) / len(rows)


def non_fallback_accuracy(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return sum(
        1
        for row in rows
        if row["review_outcome"] == "pass"
        and row.get("final_decision_source") != "deterministic_safety_fallback"
    ) / len(rows)


def repair_rate(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if row.get("repair_count", 0) > 0) / len(rows)


def deterministic_fallback_rate(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if row.get("final_decision_source") == "deterministic_safety_fallback") / len(rows)


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
    for path in (CORPUS_PATH, EVALUATION_REPORT_PATH, BLIND_EVALUATION_REPORT_PATH, SEALED_EVALUATION_REPORT_PATH, TRACE_REPORT_PATH, REPORT_PATH):
        if path.exists():
            path.unlink()
    if (DEFAULT_WORKSHOP_ROOT / "hermes-traces").exists():
        shutil.rmtree(DEFAULT_WORKSHOP_ROOT / "hermes-traces")
    if (DEFAULT_WORKSHOP_ROOT / "compiler-sessions").exists():
        shutil.rmtree(DEFAULT_WORKSHOP_ROOT / "compiler-sessions")


def main() -> None:
    report = build_report()
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


def sealed_acceptance_main() -> None:
    clean_s2_artifacts()
    if not SEALED_CORPUS_SOURCE_PATH.exists():
        print(json.dumps({"status": "blocked", "reason": f"missing {SEALED_CORPUS_SOURCE_PATH}"}, sort_keys=True))
        raise SystemExit(1)
    report = evaluate_corpus(read_json_path(SEALED_CORPUS_SOURCE_PATH), output_path=SEALED_EVALUATION_REPORT_PATH)
    summary = report["summary"]
    passed = (
        summary["schema_valid_or_refusal_rate"] == 1.0
        and summary["supported_accuracy"] >= 0.9
        and summary["ambiguous_accuracy"] >= 0.9
        and summary["unsupported_accuracy"] == 1.0
        and summary["invented_identifier_count"] == 0
        and summary["unauthorized_tool_call_count"] == 0
        and summary["unconfirmed_execution_count"] == 0
    )
    print(json.dumps({"status": "pass" if passed else "fail", "summary": summary}, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
