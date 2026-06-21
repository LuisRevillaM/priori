"""M1.2 S2 bounded model-backed tactical query compiler.

The historical function names keep the existing M1.2 verifier wiring stable, but
this is not a concrete Hermes runtime integration. It is an agent-neutral,
model-backed compiler client operating through the same bounded caller profile
that a future Hermes adapter must use.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from copy import deepcopy
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from tqe.workshop.m1_2 import (
    CallerProfile,
    DEFAULT_WORKSHOP_ROOT,
    ToolDispatchRequest,
    dispatch_model_visible,
    stable_hash,
    utc_now_iso,
    write_json,
)

APPROVED_M1_PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")
EXPERIMENTAL_CORRIDOR_PLAN_PATH = Path("config/query-plans/possession_corridor_availability.experimental.v1.json")
TRACE_DIR = DEFAULT_WORKSHOP_ROOT / "hermes-traces"
SESSION_DIR = DEFAULT_WORKSHOP_ROOT / "compiler-sessions"
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_HERMES_MODEL = "gpt-4o-mini"
COMPILER_IDENTITY = "ModelBackedTacticalQueryCompiler"
COMPILER_IDENTITY_DECISION = (
    "S2C uses an agent-neutral model-backed tactical query compiler. It is not "
    "a completed Hermes runtime integration; Hermes remains a future client "
    "adapter over the same bounded tool surface."
)
CLARIFICATION_SUPPORT_DEFINITION = "SUPPORT_DEFINITION"
CLARIFICATION_TIME_WINDOW = "TIME_WINDOW"
CLARIFICATION_DISTANCE_THRESHOLD = "DISTANCE_THRESHOLD"
GAP_PRIMITIVE_MUTATION = "PRIMITIVE_MUTATION"
GAP_CONFIRMATION_BYPASS = "CONFIRMATION_BYPASS"
GAP_DIRECT_EXECUTION = "DIRECT_EXECUTION"
GAP_PLAYER_INTENT = "PLAYER_INTENT"
GAP_BODY_ORIENTATION = "BODY_ORIENTATION"
GAP_SCANNING = "SCANNING"
GAP_PASS_PROBABILITY = "PASS_PROBABILITY"
GAP_OPTIMALITY = "OPTIMALITY"
GAP_COMMUNICATION = "COMMUNICATION"
GAP_VIDEO = "VIDEO"
GAP_BODY_SHAPE = "BODY_SHAPE"
GAP_DECEPTION = "DECEPTION"
GAP_COACH_INSTRUCTIONS = "COACH_INSTRUCTIONS"
GAP_FACIAL_CUES = "FACIAL_CUES"
HERMES_SYSTEM_PROMPT = """You are ModelBackedTacticalQueryCompiler, a bounded tactical-query compiler.

You may return only JSON matching one action-specific schema. Choose exactly one
action:
- select_recipe: choose the trusted approved ball-side block-shift recipe.
- draft_corridor: draft an EXPERIMENTAL progressive-corridor plan using existing capabilities.
- clarify: ask concise clarification questions.
- capability_gap: refuse unsupported concepts explicitly.

Never invent primitive, relation, operator, recipe, or tool identifiers.
Never request raw tracking dumps, code execution, filesystem paths, SQL, video,
primitive mutation, threshold auto-tuning, or execution confirmation.

Use select_recipe when the request explicitly asks for the approved/trusted/
reviewed/sanctioned/club-vetted/validated/established ball-side block-shift recipe/detector or clear
synonyms such as defence sliding toward the ball side, defensive displacement
toward the side occupied by the ball, the defending block shifting toward the
ball, defending unit drifting toward the ball-side flank, or the opposition
block collapsing toward the ball side. Use draft_corridor for requests about a
progressive or forward corridor/lane/passing lane from possession anchors.
Explicit thresholds are optional: when the analyst asks for corridor/lane
availability without numeric constraints, draft the corridor plan with no
parameter overrides and let the runtime defaults apply.
Never return capability_gap merely because a corridor/lane request lacks numeric
thresholds; default thresholds are valid and intentionally supported.
Treat progressive connection, progressive lane, forward lane, passing lane,
forward route, vertical route, access path, attacking route, forward connection,
penetrative channel, channel ahead of the ball, geometric progressive option,
and open corridor as aliases for the experimental
progressive-corridor family. Do not ask what those terms mean unless the request
also asks for unsupported evidence.
These corridor aliases MUST use action="draft_corridor" when attached to
possession, possession anchors, ball carrier, or active-ball possessions:
progressive lane, progressive passing lane, geometric passing lane, forward
lane, forward route, open forward lane, and geometric progressive option.

Parameter extraction rules:
- "at least N metres progression", "advance N metres", and "N metres of gain"
  set corridor_minimum_progression_m=N.
- "N metres defender clearance", "N metres defensive clearance", and "clearance
  from defenders" set corridor_minimum_clearance_m=N. "Narrowest buffer from a
  defender is at least N metres" also sets corridor_minimum_clearance_m=N. Do
  not put defender clearance, defender-gap, or defender-buffer values into
  progression.
- "within N seconds" sets corridor_max_window_seconds=N.
- Include only parameters materially requested by the analyst. Do not restate
  defaults as explicit parameter overrides.

Unsupported concepts include body orientation, body shape, facial cues, scanning,
intent, communication, video, pass probability, causality, deception, coach
instructions, and optimal actions.
If any unsupported concept appears, choose capability_gap rather than clarify.
The gap must name every material unsupported concept in the request.

Important ambiguity rule: if the request uses support/help/cover underneath/
receiver isolated/another option/extra runner/reinforcements/late-arriving attacker/useful reach/second runner/overload or
line-break support language without explicitly saying corridor, passing lane,
progressive lane, or a clarification answer that maps support to a progressive
corridor, you must choose action="clarify". Do not draft and do not
capability-gap those support requests. Ask what support should mean and what
time window should apply when the wording implies arrival timing.
Second runner language is ambiguous support language, not a capability gap,
unless it also asks for unsupported evidence such as intent, video, body shape,
or optimal decisions.
If the request asks whether support is close enough or near enough, clarification
must ask for a distance or proximity threshold.

Clarification rule: the clarifications array contains authoritative user answers
to your prior questions. If the original request was ambiguous support language
and the clarification history says "progressive corridor within two seconds" or
an equivalent answer, you must choose action="draft_corridor" and set
corridor_max_window_seconds=2.0. Do not ask the same clarification again once
the clarifications array answers it.
When clarifications contain any corridor alias, the clarified request is no
longer ambiguous support language. Draft the corridor family and extract any
numeric values from the clarification answer.

Schema constraints:
- select_recipe requires recipe_id="ball_side_block_shift_v1" and no draft parameters.
- draft_corridor requires recipe_id="possession_corridor_availability_v1" and may
  include only valid corridor parameter overrides.
- clarify requires one or more clarification questions and no draft parameters.
- capability_gap requires one or more explicit gaps and no draft parameters.
"""

UNSUPPORTED_CONCEPTS = {
    "body orientation": "No body-orientation primitive is exposed.",
    "orientation": "No body-orientation primitive is exposed.",
    "intent": "Intent is not observable in the current deterministic vocabulary.",
    "optimal": "Optimal-action claims are outside the approved claims.",
    "should": "Normative decision-quality claims are outside the approved claims.",
    "communication": "Communication is not represented in the tracking data.",
    "pass probability": "Pass-probability modelling is not available.",
    "video": "Video is outside the current dataset/tool boundary.",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HermesCompileStatus(StrEnum):
    DRAFT_VALIDATED = "DRAFT_VALIDATED"
    PLAN_VALIDATION_FAILED = "PLAN_VALIDATION_FAILED"
    MODEL_OUTPUT_INVALID = "MODEL_OUTPUT_INVALID"
    EXISTING_RECIPE_SELECTED = "EXISTING_RECIPE_SELECTED"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    CAPABILITY_GAP = "CAPABILITY_GAP"


class HermesCompileRequest(StrictModel):
    original_language: str = Field(min_length=1, max_length=1000)
    clarifications: list[str] = Field(default_factory=list)
    requester: str = Field(default="analyst", min_length=1, max_length=80)
    session_id: str | None = Field(default=None, min_length=1, max_length=80)
    parent_turn_id: str | None = Field(default=None, min_length=1, max_length=80)


class HermesCompileResponse(StrictModel):
    ok: bool
    status: HermesCompileStatus
    trace_id: str
    session_id: str
    turn_id: str
    parent_turn_id: str | None = None
    original_language: str
    clarifications: list[str] = Field(default_factory=list)
    agent_kind: Literal["model_backed_tactical_query_compiler", "deterministic_reference"] = "deterministic_reference"
    agent_identity: str = "deterministic_reference"
    agent_identity_decision: str | None = None
    model_provider: str | None = None
    model_name: str | None = None
    model_response_id: str | None = None
    model_temperature: float | None = None
    model_seed: int | None = None
    system_prompt_hash: str | None = None
    capability_context_hash: str | None = None
    tool_schema_hash: str | None = None
    trusted_recipe_context_hash: str | None = None
    raw_model_output: dict[str, Any] | None = None
    model_output_errors: list[dict[str, Any]] = Field(default_factory=list)
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    repair_count: int = 0
    final_accepted_output: dict[str, Any] | None = None
    final_decision_source: Literal["model", "model_repair", "deterministic_safety_fallback"] = "model"
    deterministic_fallback: dict[str, Any] | None = None
    interpretation: dict[str, Any]
    selected_recipe: dict[str, Any] | None = None
    draft_plan_id: str | None = None
    draft_plan_hash: str | None = None
    bound_plan_id: str | None = None
    bound_plan_hash: str | None = None
    validation_result: dict[str, Any] | None = None
    clarification_questions: list[str] = Field(default_factory=list)
    clarification_codes: list[str] = Field(default_factory=list)
    capability_gaps: list[dict[str, str]] = Field(default_factory=list)
    capability_gap_codes: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class CapabilityGapItem(StrictModel):
    concept: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=500)


class CorridorParameters(StrictModel):
    corridor_minimum_progression_m: float | None = Field(default=None, ge=0.0, le=80.0)
    corridor_minimum_clearance_m: float | None = Field(default=None, ge=0.0, le=40.0)
    corridor_max_window_seconds: float | None = Field(default=None, ge=0.2, le=15.0)
    corridor_minimum_duration_seconds: float | None = Field(default=None, ge=0.2, le=15.0)


class SelectRecipeDecision(StrictModel):
    action: Literal["select_recipe"]
    recipe_id: Literal["ball_side_block_shift_v1"]
    interpretation: str = Field(min_length=1, max_length=500)


class DraftCorridorDecision(StrictModel):
    action: Literal["draft_corridor"]
    recipe_id: Literal["possession_corridor_availability_v1"]
    interpretation: str = Field(min_length=1, max_length=500)
    corridor_parameters: CorridorParameters = Field(default_factory=CorridorParameters)


class ClarificationDecision(StrictModel):
    action: Literal["clarify"]
    recipe_id: None = None
    interpretation: str = Field(min_length=1, max_length=500)
    clarification_questions: list[str] = Field(min_length=1, max_length=4)


class CapabilityGapDecision(StrictModel):
    action: Literal["capability_gap"]
    recipe_id: None = None
    interpretation: str = Field(min_length=1, max_length=500)
    capability_gaps: list[CapabilityGapItem] = Field(min_length=1, max_length=8)


ModelDecision = Annotated[
    SelectRecipeDecision | DraftCorridorDecision | ClarificationDecision | CapabilityGapDecision,
    Field(discriminator="action"),
]
MODEL_DECISION_ADAPTER = TypeAdapter(ModelDecision)


def compile_hermes_request(
    request: HermesCompileRequest,
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> HermesCompileResponse:
    if os.environ.get("HERMES_S2_USE_REFERENCE") == "1":
        return compile_hermes_reference_request(request, output_root=output_root)
    return compile_hermes_model_request(request, output_root=output_root)


def compile_hermes_model_request(
    request: HermesCompileRequest,
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> HermesCompileResponse:
    tool_calls: list[dict[str, Any]] = []
    capabilities = hermes_tool_call("list_capabilities", {}, tool_calls, output_root=output_root)
    capability_payload = compact_capability_context(capabilities)
    recipe_summaries = [
        trusted_recipe_summary(APPROVED_M1_PLAN_PATH, state="APPROVED"),
        trusted_recipe_summary(EXPERIMENTAL_CORRIDOR_PLAN_PATH, state="EXPERIMENTAL"),
    ]
    tool_schemas = model_visible_tool_schemas(capabilities)
    model_parameter_context = model_visible_parameter_context(capabilities, recipe_summaries)
    model_payload = call_hermes_model(
        request=request,
        capability_context=capability_payload,
        recipe_summaries=recipe_summaries,
        tool_schemas=tool_schemas,
        parameter_context=model_parameter_context,
    )
    final_decision_source_override: Literal["model", "model_repair", "deterministic_safety_fallback"] | None = None
    final_accepted_output_override: dict[str, Any] | None = None
    deterministic_fallback_override: dict[str, Any] | None = None
    try:
        decision = normalize_model_decision(model_payload["json"])
    except ValidationError as exc:
        repair_payload = call_hermes_model(
            request=request,
            capability_context=capability_payload,
            recipe_summaries=recipe_summaries,
            tool_schemas=tool_schemas,
            parameter_context=model_parameter_context,
            previous_invalid_output=model_payload["json"],
            schema_errors=exc.errors(),
        )
        try:
            decision = normalize_model_decision(repair_payload["json"])
            model_payload = {
                **repair_payload,
                "invalid_first_output": model_payload["json"],
                "first_output_schema_errors": exc.errors(),
                "repair_reason": "schema_validation",
            }
        except ValidationError as repair_exc:
            model_payload = {
                **repair_payload,
                "invalid_first_output": model_payload["json"],
                "first_output_schema_errors": exc.errors(),
                "repair_reason": "schema_validation",
            }
            exc = repair_exc
        else:
            exc = None
    if isinstance(locals().get("exc"), ValidationError):
        attempts = model_attempts_from_payload(
            model_payload,
            final_schema_errors=exc.errors(),
        )
        metadata = {
            "agent_kind": "model_backed_tactical_query_compiler",
            "agent_identity": COMPILER_IDENTITY,
            "agent_identity_decision": COMPILER_IDENTITY_DECISION,
            "model_provider": "openai",
            "model_name": model_payload["model"],
            "model_response_id": model_payload.get("id"),
            "model_temperature": model_payload.get("temperature"),
            "model_seed": model_payload.get("seed"),
            "system_prompt_hash": stable_hash(HERMES_SYSTEM_PROMPT),
            "capability_context_hash": stable_hash(capability_payload),
            "tool_schema_hash": stable_hash(tool_schemas),
            "trusted_recipe_context_hash": stable_hash(recipe_summaries),
            "raw_model_output": model_payload["json"],
            "model_output_errors": exc.errors(),
            "attempts": attempts,
            "repair_count": repair_count_for_attempts(attempts),
            "final_accepted_output": None,
        }
        response = HermesCompileResponse(
            ok=False,
            status=HermesCompileStatus.MODEL_OUTPUT_INVALID,
            trace_id=trace_id_for(request, "model_output_invalid", model_payload["json"]),
            **compile_lineage_fields(request),
            original_language=request.original_language,
            clarifications=request.clarifications,
            interpretation={
                "intent": "invalid_model_output",
                "summary": "Model output failed the strict action-specific schema.",
                "automatic_execution": False,
            },
            tool_calls=tool_calls,
            **metadata,
        )
        persist_compile_trace(response, output_root=output_root)
        return response
    semantic_errors = semantic_decision_errors(request, decision)
    if semantic_errors:
        repair_payload = call_hermes_model(
            request=request,
            capability_context=capability_payload,
            recipe_summaries=recipe_summaries,
            tool_schemas=tool_schemas,
            parameter_context=model_parameter_context,
            previous_invalid_output=model_payload["json"],
            semantic_errors=semantic_errors,
        )
        try:
            decision = normalize_model_decision(repair_payload["json"])
        except ValidationError as exc:
            fallback_decision = deterministic_supported_fallback_decision(request, semantic_errors, repair_payload["json"])
            if fallback_decision is None:
                model_payload = {
                    **repair_payload,
                    "invalid_first_output": model_payload["json"],
                    "first_output_semantic_errors": semantic_errors,
                    "repair_reason": "semantic_validation",
                }
                attempts = model_attempts_from_payload(
                    model_payload,
                    final_schema_errors=exc.errors(),
                )
                metadata = {
                    "agent_kind": "model_backed_tactical_query_compiler",
                    "agent_identity": COMPILER_IDENTITY,
                    "agent_identity_decision": COMPILER_IDENTITY_DECISION,
                    "model_provider": "openai",
                    "model_name": model_payload["model"],
                    "model_response_id": model_payload.get("id"),
                    "model_temperature": model_payload.get("temperature"),
                    "model_seed": model_payload.get("seed"),
                    "system_prompt_hash": stable_hash(HERMES_SYSTEM_PROMPT),
                    "capability_context_hash": stable_hash(capability_payload),
                    "tool_schema_hash": stable_hash(tool_schemas),
                    "trusted_recipe_context_hash": stable_hash(recipe_summaries),
                    "raw_model_output": model_payload["json"],
                    "model_output_errors": exc.errors(),
                    "attempts": attempts,
                    "repair_count": repair_count_for_attempts(attempts),
                    "final_accepted_output": None,
                }
                response = HermesCompileResponse(
                    ok=False,
                    status=HermesCompileStatus.MODEL_OUTPUT_INVALID,
                    trace_id=trace_id_for(request, "model_output_invalid_after_semantic_repair", model_payload["json"]),
                    **compile_lineage_fields(request),
                    original_language=request.original_language,
                    clarifications=request.clarifications,
                    interpretation={
                        "intent": "invalid_model_output",
                        "summary": "Model semantic repair failed the strict action-specific schema.",
                        "automatic_execution": False,
                    },
                    tool_calls=tool_calls,
                    **metadata,
                )
                persist_compile_trace(response, output_root=output_root)
                return response
            model_payload = {
                **repair_payload,
                "invalid_first_output": model_payload["json"],
                "first_output_semantic_errors": semantic_errors,
                "repair_reason": "semantic_validation",
                "model_repair_output": repair_payload["json"],
                "json": fallback_decision,
            }
            decision = normalize_model_decision(fallback_decision)
            final_decision_source_override = "deterministic_safety_fallback"
            final_accepted_output_override = fallback_decision
            deterministic_fallback_override = {
                "reason": "semantic_repair_schema_failure",
                "trigger_codes": [item["code"] for item in semantic_errors],
                "model_repair_output": repair_payload["json"],
                "schema_errors": exc.errors(),
            }
        semantic_errors_after_repair = semantic_decision_errors(request, decision)
        model_payload = {
            **repair_payload,
            "invalid_first_output": model_payload["json"],
            "first_output_semantic_errors": semantic_errors,
            "repair_reason": "semantic_validation",
        }
        if semantic_errors_after_repair:
            supported_fallback_decision = deterministic_supported_fallback_decision(
                request,
                semantic_errors_after_repair,
                model_payload["json"],
            )
            if supported_fallback_decision is not None and supported_fallback_decision["action"] != "clarify":
                model_payload = {
                    **model_payload,
                    "model_repair_output": model_payload["json"],
                    "json": supported_fallback_decision,
                }
                decision = normalize_model_decision(supported_fallback_decision)
                final_decision_source_override = "deterministic_safety_fallback"
                final_accepted_output_override = supported_fallback_decision
                deterministic_fallback_override = {
                    "reason": "semantic_repair_still_invalid",
                    "trigger_codes": [item["code"] for item in semantic_errors_after_repair],
                    "model_repair_output": model_payload["model_repair_output"],
                }
                semantic_errors_after_repair = []
        if semantic_errors_after_repair:
            fallback_decision = deterministic_clarification_fallback_decision(request, semantic_errors_after_repair)
            if fallback_decision is not None:
                attempts = model_attempts_from_payload(
                    model_payload,
                    final_decision=None,
                    final_semantic_errors=semantic_errors_after_repair,
                )
                fallback_metadata = compiler_metadata(
                    model_payload=model_payload,
                    capability_payload=capability_payload,
                    tool_schemas=tool_schemas,
                    recipe_summaries=recipe_summaries,
                    attempts=attempts,
                    final_accepted_output=fallback_decision,
                    final_decision_source="deterministic_safety_fallback",
                    deterministic_fallback={
                        "reason": "semantic_validation",
                        "trigger_codes": [item["code"] for item in semantic_errors_after_repair],
                        "model_repair_output": model_payload["json"],
                    },
                )
                response = HermesCompileResponse(
                    ok=False,
                    status=HermesCompileStatus.CLARIFICATION_REQUIRED,
                    trace_id=trace_id_for(request, "deterministic_clarification_fallback", fallback_decision),
                    **compile_lineage_fields(request),
                    original_language=request.original_language,
                    clarifications=request.clarifications,
                    interpretation={
                        "intent": "clarify_tactical_request",
                        "summary": fallback_decision["interpretation"],
                        "automatic_execution": False,
                    },
                    clarification_questions=fallback_decision["clarification_questions"],
                    clarification_codes=fallback_decision["clarification_codes"],
                    tool_calls=tool_calls,
                    **fallback_metadata,
                )
                persist_compile_trace(response, output_root=output_root)
                return response
            attempts = model_attempts_from_payload(
                model_payload,
                final_decision=decision,
                final_semantic_errors=semantic_errors_after_repair,
            )
            metadata = {
                "agent_kind": "model_backed_tactical_query_compiler",
                "agent_identity": COMPILER_IDENTITY,
                "agent_identity_decision": COMPILER_IDENTITY_DECISION,
                "model_provider": "openai",
                "model_name": model_payload["model"],
                "model_response_id": model_payload.get("id"),
                "model_temperature": model_payload.get("temperature"),
                "model_seed": model_payload.get("seed"),
                "system_prompt_hash": stable_hash(HERMES_SYSTEM_PROMPT),
                "capability_context_hash": stable_hash(capability_payload),
                "tool_schema_hash": stable_hash(tool_schemas),
                "trusted_recipe_context_hash": stable_hash(recipe_summaries),
                "raw_model_output": model_payload["json"],
                "model_output_errors": [
                    {
                        "type": "semantic_validation",
                        "code": item["code"],
                        "message": item["message"],
                    }
                    for item in semantic_errors_after_repair
                ],
                "attempts": attempts,
                "repair_count": repair_count_for_attempts(attempts),
                "final_accepted_output": None,
            }
            response = HermesCompileResponse(
                ok=False,
                status=HermesCompileStatus.MODEL_OUTPUT_INVALID,
                trace_id=trace_id_for(request, "model_semantic_invalid", model_payload["json"]),
                **compile_lineage_fields(request),
                original_language=request.original_language,
                clarifications=request.clarifications,
                interpretation={
                    "intent": "invalid_model_output",
                    "summary": "Model output failed compiler semantic validation.",
                    "automatic_execution": False,
                },
                tool_calls=tool_calls,
                **metadata,
            )
            persist_compile_trace(response, output_root=output_root)
            return response

    attempts = model_attempts_from_payload(model_payload, final_decision=decision)
    metadata = compiler_metadata(
        model_payload=model_payload,
        capability_payload=capability_payload,
        tool_schemas=tool_schemas,
        recipe_summaries=recipe_summaries,
        attempts=attempts,
        final_accepted_output=final_accepted_output_override or model_payload["json"],
        final_decision_source=final_decision_source_override
        or ("model_repair" if repair_count_for_attempts(attempts) else "model"),
        deterministic_fallback=deterministic_fallback_override,
    )

    if decision["action"] == "capability_gap":
        response = HermesCompileResponse(
            ok=False,
            status=HermesCompileStatus.CAPABILITY_GAP,
            trace_id=trace_id_for(request, "model_capability_gap", decision),
            **compile_lineage_fields(request),
            original_language=request.original_language,
            clarifications=request.clarifications,
            interpretation={
                "intent": "unsupported_tactical_request",
                "summary": decision["interpretation"],
                "automatic_execution": False,
            },
            capability_gaps=dedupe_gaps(decision["capability_gaps"]),
            capability_gap_codes=dedupe_codes(
                gap_codes_from_gaps(
                    decision["capability_gaps"],
                    decision["interpretation"] + " " + resolved_request_for_model(request),
                )
            ),
            tool_calls=tool_calls,
            **metadata,
        )
        persist_compile_trace(response, output_root=output_root)
        return response

    if decision["action"] == "clarify":
        response = HermesCompileResponse(
            ok=False,
            status=HermesCompileStatus.CLARIFICATION_REQUIRED,
            trace_id=trace_id_for(request, "model_clarification", decision),
            **compile_lineage_fields(request),
            original_language=request.original_language,
            clarifications=request.clarifications,
            interpretation={
                "intent": "clarify_tactical_request",
                "summary": decision["interpretation"],
                "automatic_execution": False,
            },
            clarification_questions=decision["clarification_questions"],
            clarification_codes=dedupe_codes(clarification_codes_from_questions(decision["clarification_questions"])),
            tool_calls=tool_calls,
            **metadata,
        )
        persist_compile_trace(response, output_root=output_root)
        return response

    if decision["action"] == "select_recipe":
        selected = trusted_recipe_summary(APPROVED_M1_PLAN_PATH, state="APPROVED")
        response = HermesCompileResponse(
            ok=True,
            status=HermesCompileStatus.EXISTING_RECIPE_SELECTED,
            trace_id=trace_id_for(request, "model_existing_recipe", decision),
            **compile_lineage_fields(request),
            original_language=request.original_language,
            clarifications=request.clarifications,
            interpretation={
                "intent": "reuse_trusted_recipe",
                "summary": decision["interpretation"],
                "requires_host_recipe_load": True,
                "automatic_execution": False,
            },
            selected_recipe=selected,
            tool_calls=tool_calls,
            **metadata,
        )
        persist_compile_trace(response, output_root=output_root)
        return response

    plan_document = experimental_corridor_plan_for_model_decision(request, decision)
    hermes_tool_call(
        "describe_capability",
        {"capability_name": "geometric_progressive_corridor_from_anchor_set"},
        tool_calls,
        output_root=output_root,
    )
    submit = hermes_tool_call(
        "submit_query_plan",
        {"plan_document": plan_document, "source_label": "hermes_s2_model"},
        tool_calls,
        output_root=output_root,
    )
    validation = hermes_tool_call(
        "validate_query_plan",
        {"draft_plan_id": submit["draft_plan_id"]},
        tool_calls,
        output_root=output_root,
    )
    validated = bool(validation.get("ok"))
    response = HermesCompileResponse(
        ok=validated,
        status=HermesCompileStatus.DRAFT_VALIDATED if validated else HermesCompileStatus.PLAN_VALIDATION_FAILED,
        trace_id=trace_id_for(request, "model_draft_validated" if validated else "model_plan_validation_failed", decision),
        **compile_lineage_fields(request),
        original_language=request.original_language,
        clarifications=request.clarifications,
        interpretation={
            "intent": "draft_experimental_progressive_corridor_query",
            "summary": decision["interpretation"],
            "recipe_state": "EXPERIMENTAL",
            "corridor_parameters": decision["corridor_parameters"],
            "automatic_execution": False,
            "allowed_claims": [
                "The team had an active-ball possession anchor.",
                "A geometric progressive corridor appeared under configured thresholds.",
                "Replay coordinates come from canonical tracking frames.",
            ],
            "disallowed_claims": [
                "Intent, optimality, pass probability, or video-backed claims.",
            ],
        },
        selected_recipe=trusted_recipe_summary(EXPERIMENTAL_CORRIDOR_PLAN_PATH, state="EXPERIMENTAL"),
        draft_plan_id=submit.get("draft_plan_id"),
        draft_plan_hash=submit.get("draft_plan_hash"),
        bound_plan_id=validation.get("bound_plan_id"),
        bound_plan_hash=validation.get("bound_plan_hash"),
        validation_result=validation,
        tool_calls=tool_calls,
        **metadata,
    )
    persist_compile_trace(response, output_root=output_root)
    return response


def compile_hermes_reference_request(
    request: HermesCompileRequest,
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> HermesCompileResponse:
    text = normalize_text(request.original_language)
    tool_calls: list[dict[str, Any]] = []
    capabilities = hermes_tool_call("list_capabilities", {}, tool_calls, output_root=output_root)

    gaps = unsupported_gaps(text)
    if gaps:
        response = HermesCompileResponse(
            ok=False,
            status=HermesCompileStatus.CAPABILITY_GAP,
            trace_id=trace_id_for(request, "capability_gap", gaps),
            **compile_lineage_fields(request),
            original_language=request.original_language,
            clarifications=request.clarifications,
            interpretation={
                "intent": "unsupported_tactical_request",
                "reason": "The request asks for concepts outside the exposed capability context.",
                "available_tool_count": len(capabilities.get("tools", [])),
            },
            capability_gaps=gaps,
            capability_gap_codes=dedupe_codes(gap_codes_from_gaps(gaps, resolved_request_for_model(request))),
            tool_calls=tool_calls,
        )
        persist_compile_trace(response, output_root=output_root)
        return response

    if asks_for_block_shift(text):
        selected = trusted_recipe_summary(APPROVED_M1_PLAN_PATH, state="APPROVED")
        response = HermesCompileResponse(
            ok=True,
            status=HermesCompileStatus.EXISTING_RECIPE_SELECTED,
            trace_id=trace_id_for(request, "existing_recipe", selected),
            **compile_lineage_fields(request),
            original_language=request.original_language,
            clarifications=request.clarifications,
            interpretation={
                "intent": "reuse_trusted_recipe",
                "summary": "Use the trusted approved ball-side block-shift recipe.",
                "requires_host_recipe_load": True,
                "automatic_execution": False,
            },
            selected_recipe=selected,
            tool_calls=tool_calls,
        )
        persist_compile_trace(response, output_root=output_root)
        return response

    if ambiguous_support_request(text):
        questions = [
            "Should support mean an open progressive corridor from possession?",
            "How long may the support option take to appear?",
            "Should the receiver have to be inside the corridor, or is geometric availability enough?",
        ]
        response = HermesCompileResponse(
            ok=False,
            status=HermesCompileStatus.CLARIFICATION_REQUIRED,
            trace_id=trace_id_for(request, "clarification", questions),
            **compile_lineage_fields(request),
            original_language=request.original_language,
            clarifications=request.clarifications,
            interpretation={
                "intent": "ambiguous_support_request",
                "reason": "The current vocabulary can measure possession anchors and progressive corridors, but support has multiple tactical meanings.",
                "automatic_execution": False,
            },
            clarification_questions=questions,
            clarification_codes=[CLARIFICATION_SUPPORT_DEFINITION, CLARIFICATION_TIME_WINDOW],
            tool_calls=tool_calls,
        )
        persist_compile_trace(response, output_root=output_root)
        return response

    if asks_for_progressive_corridor(text):
        hermes_tool_call(
            "describe_capability",
            {"capability_name": "geometric_progressive_corridor_from_anchor_set"},
            tool_calls,
            output_root=output_root,
        )
        plan_document = experimental_corridor_plan_for_request(request)
        submit = hermes_tool_call(
            "submit_query_plan",
            {"plan_document": plan_document, "source_label": "hermes_s2"},
            tool_calls,
            output_root=output_root,
        )
        validation = hermes_tool_call(
            "validate_query_plan",
            {"draft_plan_id": submit["draft_plan_id"]},
            tool_calls,
            output_root=output_root,
        )
        validated = bool(validation.get("ok"))
        response = HermesCompileResponse(
            ok=validated,
            status=HermesCompileStatus.DRAFT_VALIDATED if validated else HermesCompileStatus.PLAN_VALIDATION_FAILED,
            trace_id=trace_id_for(request, "draft_validated" if validated else "plan_validation_failed", validation),
            **compile_lineage_fields(request),
            original_language=request.original_language,
            clarifications=request.clarifications,
            interpretation={
                "intent": "draft_experimental_progressive_corridor_query",
                "summary": "Detect possession anchors where a geometric progressive corridor becomes available.",
                "recipe_state": "EXPERIMENTAL",
                "automatic_execution": False,
                "allowed_claims": [
                    "The team had an active-ball possession anchor.",
                    "A geometric progressive corridor appeared under configured thresholds.",
                    "Replay coordinates come from canonical tracking frames.",
                ],
                "disallowed_claims": [
                    "Intent, optimality, pass probability, or video-backed claims.",
                ],
            },
            selected_recipe=trusted_recipe_summary(EXPERIMENTAL_CORRIDOR_PLAN_PATH, state="EXPERIMENTAL"),
            draft_plan_id=submit.get("draft_plan_id"),
            draft_plan_hash=submit.get("draft_plan_hash"),
            bound_plan_id=validation.get("bound_plan_id"),
            bound_plan_hash=validation.get("bound_plan_hash"),
            validation_result=validation,
            tool_calls=tool_calls,
        )
        persist_compile_trace(response, output_root=output_root)
        return response

    response = HermesCompileResponse(
        ok=False,
        status=HermesCompileStatus.CLARIFICATION_REQUIRED,
        trace_id=trace_id_for(request, "unclassified", text),
        **compile_lineage_fields(request),
        original_language=request.original_language,
        clarifications=request.clarifications,
        interpretation={
            "intent": "unclassified_tactical_request",
            "reason": "The request did not clearly name a supported recipe or experimental corridor concept.",
            "automatic_execution": False,
        },
        clarification_questions=[
            "Do you want the approved ball-side block-shift recipe or the experimental progressive-corridor recipe?",
        ],
        clarification_codes=[],
        tool_calls=tool_calls,
    )
    persist_compile_trace(response, output_root=output_root)
    return response


def hermes_tool_call(
    tool_name: str,
    arguments: dict[str, Any],
    tool_calls: list[dict[str, Any]],
    *,
    output_root: Path,
) -> dict[str, Any]:
    request_hash = stable_hash({"tool_name": tool_name, "arguments": summarize_arguments(arguments)})
    payload = dispatch_model_visible(
        ToolDispatchRequest(tool_name=tool_name, arguments=arguments),
        output_root=output_root,
        caller_profile=CallerProfile.HERMES_S2,
    )
    tool_calls.append(
        {
            "index": len(tool_calls) + 1,
            "tool_name": tool_name,
            "caller_profile": CallerProfile.HERMES_S2.value,
            "arguments_summary": summarize_arguments(arguments),
            "request_hash": request_hash,
            "response_hash": stable_hash(payload),
            "ok": payload.get("ok", True) is not False,
            "response_keys": sorted(payload.keys()),
            "error_code": payload.get("error_code"),
        }
    )
    return payload


def experimental_corridor_plan_for_request(request: HermesCompileRequest) -> dict[str, Any]:
    payload = read_json(EXPERIMENTAL_CORRIDOR_PLAN_PATH)
    payload = deepcopy(payload)
    payload["draft_plan"]["plan_id"] = "hermes_s2_progressive_corridor_experimental"
    payload["default_invocation"]["invocation_id"] = "hermes_s2_progressive_corridor"
    return payload


def experimental_corridor_plan_for_model_decision(
    request: HermesCompileRequest,
    decision: dict[str, Any],
) -> dict[str, Any]:
    payload = experimental_corridor_plan_for_request(request)
    parameters = {
        key: value
        for key, value in decision["corridor_parameters"].items()
        if value is not None
    }
    unit_by_parameter = {
        "corridor_minimum_progression_m": "metre",
        "corridor_minimum_clearance_m": "metre",
        "corridor_max_window_seconds": "second",
        "corridor_minimum_duration_seconds": "second",
    }
    payload["default_invocation"]["parameters"] = {
        key: {"payload_type": "number", "unit": unit_by_parameter[key], "value": value}
        for key, value in sorted(parameters.items())
    }
    return payload


def call_hermes_model(
    *,
    request: HermesCompileRequest,
    capability_context: dict[str, Any],
    recipe_summaries: list[dict[str, Any]],
    tool_schemas: list[dict[str, Any]],
    parameter_context: dict[str, Any],
    previous_invalid_output: dict[str, Any] | None = None,
    schema_errors: list[dict[str, Any]] | None = None,
    semantic_errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for model-backed compiler S2 verification")
    model = os.environ.get("HERMES_S2_MODEL") or os.environ.get("OPENAI_MODEL") or DEFAULT_HERMES_MODEL
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": HERMES_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "user_request": request.original_language,
                        "clarifications": request.clarifications,
                        "clarification_history_is_authoritative": bool(request.clarifications),
                        "resolved_request": resolved_request_for_model(request),
                        "capability_context": capability_context,
                        "tool_schemas": tool_schemas,
                        "parameter_context": parameter_context,
                        "classification_rules": compiler_classification_rules(),
                        "strict_decision_schema": MODEL_DECISION_ADAPTER.json_schema(),
                        "trusted_recipes": recipe_summaries,
                        "repair_instruction": {
                            "active": previous_invalid_output is not None,
                            "previous_invalid_output": previous_invalid_output,
                            "schema_errors": schema_errors or [],
                            "semantic_errors": semantic_errors or [],
                            "requirement": "Return one corrected JSON object that satisfies the strict_decision_schema and fixes every schema or semantic error. Do not add fields outside the selected action variant.",
                        },
                    },
                    sort_keys=True,
                ),
            },
        ],
    }
    http_request = urllib.request.Request(
        OPENAI_CHAT_COMPLETIONS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(http_request, timeout=60) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI model call failed: HTTP {exc.code}: {body[:500]}") from exc
    content = response_payload["choices"][0]["message"]["content"]
    return {
        "id": response_payload.get("id"),
        "model": response_payload.get("model", model),
        "json": json.loads(content),
        "usage": response_payload.get("usage", {}),
        "temperature": payload["temperature"],
        "seed": payload.get("seed"),
    }


def normalize_model_decision(payload: dict[str, Any]) -> dict[str, Any]:
    decision = MODEL_DECISION_ADAPTER.validate_python(payload)
    params = CorridorParameters().model_dump()
    gaps: list[dict[str, str]] = []
    questions: list[str] = []
    recipe_id: str | None = None
    if isinstance(decision, SelectRecipeDecision):
        action = decision.action
        recipe_id = decision.recipe_id
    elif isinstance(decision, DraftCorridorDecision):
        action = decision.action
        recipe_id = decision.recipe_id
        params = decision.corridor_parameters.model_dump()
    elif isinstance(decision, ClarificationDecision):
        action = decision.action
        questions = decision.clarification_questions
    else:
        action = decision.action
        gaps = [item.model_dump() for item in decision.capability_gaps]
    return {
        "action": action,
        "recipe_id": recipe_id,
        "interpretation": decision.interpretation.strip(),
        "clarification_questions": questions,
        "capability_gaps": gaps,
        "corridor_parameters": params,
        "requested_evidence": [],
    }


def compact_capability_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "tools": [tool["name"] for tool in context.get("tools", [])],
        "relations": [
            {
                "name": item.get("name"),
                "agent_authorable": item.get("agent_authorable"),
                "purpose": item.get("purpose"),
            }
            for item in context.get("relations", [])
        ],
        "primitives": [
            {
                "name": item.get("name"),
                "agent_authorable": item.get("agent_authorable"),
                "purpose": item.get("purpose"),
            }
            for item in context.get("primitives", [])
        ],
        "operators": [item.get("name") for item in context.get("operators", [])],
        "limitations": context.get("limitations", []),
        "forbidden_surfaces": context.get("forbidden_surfaces", []),
    }


def model_visible_tool_schemas(context: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "name": tool.get("name"),
            "input_schema": tool.get("input_schema"),
            "output_schema": tool.get("output_schema"),
            "exposure": tool.get("exposure"),
        }
        for tool in context.get("tools", [])
    ]


def model_visible_parameter_context(
    context: dict[str, Any],
    recipe_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    corridor_relation = next(
        (
            relation
            for relation in context.get("relations", [])
            if relation.get("name") == "geometric_progressive_corridor_from_anchor_set"
        ),
        {},
    )
    parameter_aliases = {
        "corridor_minimum_progression_m": {
            "runtime_parameter": "minimum_progression_m",
            "relation": "geometric_progressive_corridor_from_anchor_set",
        },
        "corridor_minimum_clearance_m": {
            "runtime_parameter": "minimum_clearance_m",
            "relation": "geometric_progressive_corridor_from_anchor_set",
        },
        "corridor_max_window_seconds": {
            "runtime_parameter": "max_window_seconds",
            "relation": "geometric_progressive_corridor_from_anchor_set",
        },
        "corridor_minimum_duration_seconds": {
            "runtime_parameter": "minimum_duration_seconds",
            "relation": "geometric_progressive_corridor_from_anchor_set",
        },
    }
    runtime_parameters = {
        parameter.get("name"): parameter
        for parameter in corridor_relation.get("parameters", [])
        if parameter.get("name")
    }
    exposed_parameters = {}
    for exposed_name, mapping in parameter_aliases.items():
        parameter = runtime_parameters.get(mapping["runtime_parameter"], {})
        exposed_parameters[exposed_name] = {
            "runtime_parameter": mapping["runtime_parameter"],
            "payload_type": parameter.get("payload_type"),
            "unit": parameter.get("unit"),
            "minimum": parameter.get("minimum"),
            "maximum": parameter.get("maximum"),
            "description": parameter.get("description"),
            "only_when_user_materially_specifies": True,
        }
    return {
        "schema_version": "1.0",
        "compiler_action_families": {
            "select_recipe": {
                "allowed_recipe_ids": ["ball_side_block_shift_v1"],
                "allowed_parameters": [],
            },
            "draft_corridor": {
                "allowed_recipe_ids": ["possession_corridor_availability_v1"],
                "allowed_parameters": exposed_parameters,
            },
        },
        "trusted_recipe_summaries": recipe_summaries,
    }


def compiler_classification_rules() -> dict[str, Any]:
    return {
        "draft_corridor_when_request_contains": [
            "progressive corridor",
            "open corridor",
            "penetrative channel",
            "channel ahead",
            "progressive connection",
            "progressive connections",
            "progressive lane",
            "progressive passing lane",
            "passing lane",
            "geometric passing lane",
            "forward lane",
            "open forward lane",
            "forward route",
            "vertical route",
            "vertical routes",
            "access path",
            "access paths",
            "forward connection",
            "forward connections",
            "attacking route",
            "attacking routes",
            "geometric progressive option",
        ],
        "draft_corridor_requires_context_any_of": [
            "possession",
            "possession anchor",
            "active-ball",
            "ball carrier",
            "team in possession",
        ],
        "select_block_shift_requires_request_any_of": [
            "approved",
            "trusted",
            "reviewed",
            "sanctioned",
            "club-vetted",
            "validated",
            "established",
        ],
        "select_block_shift_when_request_contains": [
            "ball-side block shift",
            "ball side block shift",
            "block-shift",
            "block shift",
            "team-shape",
            "defending shape",
            "ball-side defensive displacement",
            "ball side defensive displacement",
            "defensive displacement",
            "defence sliding",
            "defense sliding",
            "defending unit drifts",
            "defending unit drift",
            "defending block",
            "opposition block collapsing",
            "opposition unit travelling",
            "opposition unit traveling",
            "block collapsing",
            "flank carrying the ball",
            "ball-side flank",
            "side containing the ball",
            "side occupied by the ball",
            "toward the ball side",
        ],
        "clarify_not_gap_when_request_contains_without_corridor_alias": [
            "support",
            "help",
            "cover",
            "cover underneath",
            "receiver isolated",
            "left isolated",
            "extra runner",
            "joined at the right moment",
            "reinforcements",
            "teammate",
            "teammates",
            "teammates arrived",
            "line was broken",
            "another option",
            "combine with the carrier",
            "late-arriving attacker",
            "late arriving attacker",
            "got there in time",
            "useful reach",
            "second runner",
            "overload",
            "line-break support",
        ],
        "clarify_distance_when_request_contains": [
            "close enough",
            "near enough",
            "how close",
            "distance",
        ],
        "capability_gap_when_request_contains": [
            "body orientation",
            "hip angle",
            "body shape",
            "facial cue",
            "scanning",
            "scanned",
            "head checks",
            "intent",
            "intended",
            "communication",
            "video",
            "pass probability",
            "causality",
            "deception",
            "coach instruction",
            "optimal",
            "should have done",
            "mutate primitive",
            "ignore the allowed tools",
            "execute_query_plan immediately",
        ],
        "clarification_answers_are_authoritative": True,
        "draft_corridor_when_clarification_contains": [
            "progressive corridor",
            "open corridor",
            "progressive lane",
            "passing lane",
            "forward lane",
        ],
    }


def clarification_codes_for_text(text: str) -> list[str]:
    normalized = normalize_text(text)
    codes = []
    if any(
        term in normalized
        for term in (
            "support",
            "help",
            "cover underneath",
            "receiver isolated",
            "left isolated",
            "extra runner",
            "joined at the right moment",
            "reinforcements",
            "teammates arrived",
            "line was broken",
            "another option",
            "combine with the carrier",
            "late-arriving attacker",
            "late arriving attacker",
            "second runner",
            "overload",
            "arrived properly",
            "useful reach",
        )
    ):
        codes.append(CLARIFICATION_SUPPORT_DEFINITION)
    if any(
        term in normalized
        for term in (
            "support",
            "help",
            "second runner",
            "overload",
            "joined",
            "arrived",
            "late",
            "late-arriving",
            "late arriving",
            "soon enough",
            "in time",
            "right moment",
            "line was broken",
            "properly",
            "transition",
        )
    ):
        codes.append(CLARIFICATION_TIME_WINDOW)
    if any(term in normalized for term in ("close", "near", "nearby", "distance", "reach")):
        codes.append(CLARIFICATION_DISTANCE_THRESHOLD)
    return codes


def clarification_codes_from_questions(questions: list[str]) -> list[str]:
    text = " ".join(questions)
    return clarification_codes_for_text(text)


def gap_codes_for_text(text: str) -> list[str]:
    normalized = normalize_text(text)
    code_terms = [
        (
            GAP_CONFIRMATION_BYPASS,
            (
                "bypass confirmation",
                "confirmation bypass",
                "without confirmation",
                "without approval",
                "do not ask me to confirm",
                "confirm anything",
                "skip approval",
                "approval step",
                "without waiting for approval",
                "waiting for approval",
            ),
        ),
        (
            GAP_PRIMITIVE_MUTATION,
            (
                "mutation",
                "mutate",
                "redefine",
                "redefining",
                "modify the existing",
                "modify existing",
                "calculation method",
                "corridor-clearance calculation",
                "corridor clearance calculation",
                "alter primitive",
                "altering the corridor-clearance primitive",
                "altering the corridor clearance primitive",
                "altering corridor-clearance primitive",
                "altering corridor clearance primitive",
                "altering primitive",
                "altering primitives",
                "change primitive",
                "primitive definition",
                "changing primitive",
            ),
        ),
        (
            GAP_DIRECT_EXECUTION,
            (
                "direct execution",
                "execute directly",
                "execute the revised",
                "execute_query_plan",
                "execution of the detector",
                "execution of detector",
                "immediate execution",
                "fire the detector",
                "launch the detector",
                "launching the detector",
                "run this detector immediately",
                "running the detector immediately",
            ),
        ),
        (GAP_PLAYER_INTENT, ("intent", "intended")),
        (GAP_BODY_ORIENTATION, ("body orientation", "orientation", "body angle", "torso position", "hip angle")),
        (GAP_SCANNING, ("scanning", "scanned", "scan", "glance pattern", "head checks")),
        (GAP_PASS_PROBABILITY, ("pass probability", "completion probability", "probability")),
        (GAP_OPTIMALITY, ("optimal", "should have done", "best option")),
        (GAP_COMMUNICATION, ("communication", "communicating")),
        (GAP_VIDEO, ("video",)),
        (GAP_BODY_SHAPE, ("body shape",)),
        (GAP_DECEPTION, ("deception", "disguised")),
        (GAP_COACH_INSTRUCTIONS, ("coach instruction", "coach")),
        (GAP_FACIAL_CUES, ("facial cue", "facial")),
    ]
    codes = []
    for code, terms in code_terms:
        if any(term in normalized for term in terms):
            codes.append(code)
    return codes


def gap_codes_from_gaps(gaps: list[dict[str, str]], interpretation: str = "") -> list[str]:
    text = " ".join(f"{gap.get('concept', '')} {gap.get('reason', '')}" for gap in gaps) + " " + interpretation
    return gap_codes_for_text(text)


def dedupe_codes(codes: list[str]) -> list[str]:
    deduped = []
    for code in codes:
        if code not in deduped:
            deduped.append(code)
    return deduped


def requests_approved_block_shift(text: str, rules: dict[str, Any]) -> bool:
    has_trust_marker = any(marker in text for marker in rules["select_block_shift_requires_request_any_of"])
    has_block_shift_alias = any(alias in text for alias in rules["select_block_shift_when_request_contains"])
    return has_trust_marker and has_block_shift_alias


def has_corridor_parameter_context(text: str) -> bool:
    parameter_terms = (
        "metre",
        "meter",
        "gain",
        "advance",
        "gap",
        "route",
        "routes",
        "vertical",
        "access path",
        "access paths",
        "move possession",
        "up the pitch",
        "progression",
        "clearance",
        "buffer",
        "defender",
        "within",
        "seconds",
        "stay open",
        "remain open",
        "available within",
    )
    return any(term in text for term in parameter_terms)


def deterministic_supported_fallback_decision(
    request: HermesCompileRequest,
    semantic_errors: list[dict[str, str]],
    model_repair_output: dict[str, Any],
) -> dict[str, Any] | None:
    error_codes = {item["code"] for item in semantic_errors}
    clarification_fallback = deterministic_clarification_fallback_decision(request, semantic_errors)
    if clarification_fallback is not None:
        repair_questions = []
        if isinstance(model_repair_output, dict) and isinstance(model_repair_output.get("clarification_questions"), list):
            repair_questions = [
                str(question)
                for question in model_repair_output["clarification_questions"]
                if str(question).strip()
            ]
        return {
            "action": "clarify",
            "interpretation": clarification_fallback["interpretation"],
            "clarification_questions": repair_questions or clarification_fallback["clarification_questions"],
        }
    if "APPROVED_BLOCK_SHIFT_REQUIRES_RECIPE_SELECTION" in error_codes:
        return {
            "action": "select_recipe",
            "recipe_id": "ball_side_block_shift_v1",
            "interpretation": "Use the approved ball-side block-shift recipe for the trusted defensive-movement request.",
        }
    if "SUPPORTED_CORRIDOR_REQUIRES_DRAFT" not in error_codes:
        return None
    repair_parameters = {}
    if isinstance(model_repair_output, dict) and isinstance(model_repair_output.get("corridor_parameters"), dict):
        repair_parameters = {
            key: value
            for key, value in model_repair_output["corridor_parameters"].items()
            if key in CorridorParameters.model_fields and value is not None
        }
    parameters = {
        **deterministic_corridor_parameters_from_text(resolved_request_for_model(request)),
        **repair_parameters,
    }
    return {
        "action": "draft_corridor",
        "recipe_id": "possession_corridor_availability_v1",
        "interpretation": "Draft the experimental progressive-corridor recipe for the supported route/channel request.",
        "corridor_parameters": parameters,
    }


def deterministic_corridor_parameters_from_text(text: str) -> dict[str, float]:
    normalized = normalize_text(text)
    parameters: dict[str, float] = {}
    for match in re.finditer(r"(?P<number>\d+(?:\.\d+)?)\s*-?\s*(?:metre|metres|meter|meters|m)\b", normalized):
        value = float(match.group("number"))
        window_start = max(0, match.start() - 80)
        window_end = min(len(normalized), match.end() + 80)
        window = normalized[window_start:window_end]
        if any(term in window for term in ("clearance", "buffer", "defender", "gap")):
            parameters["corridor_minimum_clearance_m"] = value
        elif any(term in window for term in ("gain", "gains", "advance", "advances", "move play", "move possession", "up the pitch", "progression")):
            parameters["corridor_minimum_progression_m"] = value
    for match in re.finditer(r"(?P<number>\d+(?:\.\d+)?)\s*-?\s*seconds?\b", normalized):
        value = float(match.group("number"))
        window_start = max(0, match.start() - 80)
        window_end = min(len(normalized), match.end() + 80)
        window = normalized[window_start:window_end]
        if any(term in window for term in ("stay open", "stays open", "remain open", "remains open", "available for")):
            parameters["corridor_minimum_duration_seconds"] = value
        elif any(term in window for term in ("within", "appear", "appears", "emerge", "emerges", "available within")):
            parameters["corridor_max_window_seconds"] = value
    return parameters


def semantic_decision_errors(request: HermesCompileRequest, decision: dict[str, Any]) -> list[dict[str, str]]:
    text = normalize_text(resolved_request_for_model(request))
    rules = compiler_classification_rules()
    errors: list[dict[str, str]] = []

    if requests_approved_block_shift(text, rules) and decision["action"] != "select_recipe":
        errors.append(
            {
                "code": "APPROVED_BLOCK_SHIFT_REQUIRES_RECIPE_SELECTION",
                "message": "Trusted/reviewed/approved ball-side defensive movement requests must select "
                "recipe_id=ball_side_block_shift_v1 instead of drafting or capability-gapping.",
            }
        )

    has_unsupported = [term for term in rules["capability_gap_when_request_contains"] if term in text]
    if has_unsupported:
        if decision["action"] != "capability_gap":
            errors.append(
                {
                    "code": "UNSUPPORTED_REQUIRES_CAPABILITY_GAP",
                    "message": "Requests containing unsupported concepts must use action=capability_gap: "
                    + ", ".join(has_unsupported),
                }
            )
        else:
            gap_text = normalize_text(
                " ".join(f"{gap.get('concept', '')} {gap.get('reason', '')}" for gap in decision["capability_gaps"])
                + " "
                + decision["interpretation"]
            )
            for term in has_unsupported:
                if term in {"execute_query_plan immediately", "ignore the allowed tools"}:
                    expected_terms = ["execute", "allowed tools", "authorization"]
                elif term == "head checks":
                    expected_terms = ["head checks", "scanning", "scan", "body orientation"]
                elif term == "hip angle":
                    expected_terms = ["hip angle", "body orientation", "orientation"]
                elif term == "intended":
                    expected_terms = ["intended", "intent"]
                elif term == "scanned":
                    expected_terms = ["scan", "scanning", "scanned"]
                elif term == "should have done":
                    expected_terms = ["should", "optimal", "decision"]
                elif term == "mutate primitive":
                    expected_terms = ["mutate", "mutation", "primitive"]
                else:
                    expected_terms = [term]
                if not any(expected in gap_text for expected in expected_terms):
                    errors.append(
                        {
                            "code": "CAPABILITY_GAP_MISSING_CODE",
                            "message": f"Capability gap must name unsupported concept: {term}",
                        }
                    )
        return errors

    corridor_aliases = rules["draft_corridor_when_request_contains"]
    corridor_context = rules["draft_corridor_requires_context_any_of"]
    has_corridor_alias = any(alias in text for alias in corridor_aliases)
    matched_corridor_aliases = [alias for alias in corridor_aliases if alias in text]
    has_corridor_context = (
        any(context in text for context in corridor_context)
        or has_corridor_parameter_context(text)
        or bool(request.clarifications)
    )
    if has_corridor_alias and has_corridor_context and decision["action"] != "draft_corridor":
        errors.append(
            {
                "code": "SUPPORTED_CORRIDOR_REQUIRES_DRAFT",
                "message": "The request contains supported corridor aliases "
                f"{matched_corridor_aliases} with possession context. Correct output must be "
                "action=draft_corridor, recipe_id=possession_corridor_availability_v1, and no "
                "capability_gaps for these aliases.",
            }
        )

    clarification_text = normalize_text(" ".join(request.clarifications))
    if request.clarifications and any(alias in clarification_text for alias in rules["draft_corridor_when_clarification_contains"]):
        if decision["action"] != "draft_corridor":
            errors.append(
                {
                    "code": "ANSWERED_SUPPORT_REQUIRES_DRAFT",
                    "message": "Clarification answer maps support to a corridor alias; action must be draft_corridor.",
                }
            )

    ambiguous_terms = rules["clarify_not_gap_when_request_contains_without_corridor_alias"]
    if any(term in text for term in ambiguous_terms) and not has_corridor_alias and not request.clarifications:
        if decision["action"] != "clarify":
            errors.append(
                {
                    "code": "AMBIGUOUS_SUPPORT_REQUIRES_CLARIFICATION",
                    "message": "Ambiguous support/help/second-runner language must clarify instead of draft or gap.",
                }
            )
        elif any(term in text for term in rules["clarify_distance_when_request_contains"]):
            question_text = normalize_text(" ".join(decision["clarification_questions"]))
            if not any(token in question_text for token in ("distance", "close", "near", "proximity")):
                errors.append(
                    {
                        "code": "DISTANCE_SUPPORT_REQUIRES_DISTANCE_THRESHOLD",
                        "message": "Close/near support clarification must ask for a distance or proximity threshold.",
                    }
                )
    return errors


def model_attempts_from_payload(
    model_payload: dict[str, Any],
    *,
    final_decision: dict[str, Any] | None = None,
    final_schema_errors: list[dict[str, Any]] | None = None,
    final_semantic_errors: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    first_output = model_payload.get("invalid_first_output")
    if first_output is not None:
        first_schema_errors = model_payload.get("first_output_schema_errors") or []
        first_semantic_errors = model_payload.get("first_output_semantic_errors") or []
        attempts.append(
            {
                "attempt_index": 1,
                "raw_output": first_output,
                "schema_validation": {
                    "ok": not first_schema_errors,
                    "errors": first_schema_errors,
                },
                "semantic_validation": {
                    "ok": not first_semantic_errors,
                    "errors": first_semantic_errors,
                },
                "accepted": False,
            }
        )
    schema_errors = final_schema_errors or []
    semantic_errors = final_semantic_errors or []
    attempts.append(
        {
            "attempt_index": len(attempts) + 1,
            "raw_output": model_payload.get("json"),
            "schema_validation": {
                "ok": not schema_errors,
                "errors": schema_errors,
            },
            "semantic_validation": {
                "ok": not semantic_errors and final_decision is not None,
                "errors": semantic_errors,
            },
            "accepted": final_decision is not None and not schema_errors and not semantic_errors,
        }
    )
    return attempts


def deterministic_clarification_fallback_decision(
    request: HermesCompileRequest,
    semantic_errors: list[dict[str, str]],
) -> dict[str, Any] | None:
    error_codes = {item["code"] for item in semantic_errors}
    if "AMBIGUOUS_SUPPORT_REQUIRES_CLARIFICATION" not in error_codes:
        return None
    codes = dedupe_codes(clarification_codes_for_text(request.original_language))
    if CLARIFICATION_SUPPORT_DEFINITION not in codes:
        codes.append(CLARIFICATION_SUPPORT_DEFINITION)
    if CLARIFICATION_TIME_WINDOW not in codes:
        codes.append(CLARIFICATION_TIME_WINDOW)
    questions = [
        "What should count as support in this request?",
        "What time window should apply?",
    ]
    if CLARIFICATION_DISTANCE_THRESHOLD in codes:
        questions.append("What distance threshold should define nearby support?")
    return {
        "action": "clarify",
        "recipe_id": None,
        "interpretation": "Deterministic safety fallback: ambiguous support language requires clarification.",
        "clarification_questions": questions,
        "clarification_codes": codes,
    }


def compiler_metadata(
    *,
    model_payload: dict[str, Any],
    capability_payload: dict[str, Any],
    tool_schemas: list[dict[str, Any]],
    recipe_summaries: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    final_accepted_output: dict[str, Any] | None,
    final_decision_source: Literal["model", "model_repair", "deterministic_safety_fallback"],
    deterministic_fallback: dict[str, Any] | None = None,
    model_output_errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "agent_kind": "model_backed_tactical_query_compiler",
        "agent_identity": COMPILER_IDENTITY,
        "agent_identity_decision": COMPILER_IDENTITY_DECISION,
        "model_provider": "openai",
        "model_name": model_payload["model"],
        "model_response_id": model_payload.get("id"),
        "model_temperature": model_payload.get("temperature"),
        "model_seed": model_payload.get("seed"),
        "system_prompt_hash": stable_hash(HERMES_SYSTEM_PROMPT),
        "capability_context_hash": stable_hash(capability_payload),
        "tool_schema_hash": stable_hash(tool_schemas),
        "trusted_recipe_context_hash": stable_hash(recipe_summaries),
        "raw_model_output": model_payload["json"],
        "model_output_errors": model_output_errors or [],
        "attempts": attempts,
        "repair_count": repair_count_for_attempts(attempts),
        "final_accepted_output": final_accepted_output,
        "final_decision_source": final_decision_source,
        "deterministic_fallback": deterministic_fallback,
    }


def repair_count_for_attempts(attempts: list[dict[str, Any]]) -> int:
    return max(0, len(attempts) - 1)


def dedupe_gaps(gaps: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    deduped = []
    for gap in gaps:
        concept = gap["concept"].lower()
        if concept in seen:
            continue
        if concept == "orientation" and "body orientation" in seen:
            continue
        seen.add(concept)
        deduped.append(gap)
    return deduped


def resolved_request_for_model(request: HermesCompileRequest) -> str:
    if not request.clarifications:
        return request.original_language
    return request.original_language + "\nClarification answers: " + " ".join(request.clarifications)


def trusted_recipe_summary(path: Path, *, state: Literal["APPROVED", "EXPERIMENTAL"]) -> dict[str, Any]:
    payload = read_json(path)
    recipe = payload["recipe"]
    summary = {
        "recipe_id": recipe["recipe_id"],
        "recipe_version": recipe["recipe_version"],
        "display_name": recipe["display_name"],
        "state": state,
        "output_classifications": recipe.get("output_classifications", []),
        "allowed_claims": recipe.get("allowed_claims", []),
        "limitations": recipe.get("limitations", []),
    }
    if recipe["recipe_id"] == "possession_corridor_availability_v1":
        summary["model_visible_aliases"] = [
            "progressive corridor",
            "open corridor",
            "progressive lane",
            "progressive passing lane",
            "passing lane",
            "geometric passing lane",
            "forward lane",
            "open forward lane",
            "forward route",
            "geometric progressive option",
        ]
    return summary


def record_confirmed_execution_trace(
    *,
    compile_response: HermesCompileResponse,
    execution_authorization_id: str,
    execution: dict[str, Any],
    inspection: dict[str, Any],
    replay: dict[str, Any],
    post_compile_tool_calls: list[dict[str, Any]] | None = None,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> dict[str, Any]:
    all_tool_calls = compile_response.tool_calls + (post_compile_tool_calls or [])
    payload = {
        "schema_version": "1.0",
        "trace_kind": "hermes_confirmed_execution",
        "recorded_at": utc_now_iso(),
        "compile_trace_id": compile_response.trace_id,
        "session_id": compile_response.session_id,
        "turn_id": compile_response.turn_id,
        "parent_turn_id": compile_response.parent_turn_id,
        "original_language": compile_response.original_language,
        "clarification_turns": [
            {
                "turn_index": index + 1,
                "answer": answer,
            }
            for index, answer in enumerate(compile_response.clarifications)
        ],
        "clarification_questions": compile_response.clarification_questions,
        "agent_kind": compile_response.agent_kind,
        "agent_identity": compile_response.agent_identity,
        "agent_identity_decision": compile_response.agent_identity_decision,
        "model_provider": compile_response.model_provider,
        "model_name": compile_response.model_name,
        "model_response_id": compile_response.model_response_id,
        "model_temperature": compile_response.model_temperature,
        "model_seed": compile_response.model_seed,
        "system_prompt_hash": compile_response.system_prompt_hash,
        "capability_context_hash": compile_response.capability_context_hash,
        "tool_schema_hash": compile_response.tool_schema_hash,
        "trusted_recipe_context_hash": compile_response.trusted_recipe_context_hash,
        "raw_model_output": compile_response.raw_model_output,
        "attempts": compile_response.attempts,
        "repair_count": compile_response.repair_count,
        "final_accepted_output": compile_response.final_accepted_output,
        "final_decision_source": compile_response.final_decision_source,
        "deterministic_fallback": compile_response.deterministic_fallback,
        "clarification_codes": compile_response.clarification_codes,
        "capability_gap_codes": compile_response.capability_gap_codes,
        "selected_recipe": compile_response.selected_recipe,
        "draft_plan_id": compile_response.draft_plan_id,
        "draft_plan_hash": compile_response.draft_plan_hash,
        "bound_plan_id": compile_response.bound_plan_id,
        "bound_plan_hash": compile_response.bound_plan_hash,
        "validation_result": compile_response.validation_result,
        "human_confirmation_event": {
            "source": "host_manual",
            "execution_authorization_id": execution_authorization_id,
        },
        "execution_id": execution["execution_id"],
        "result_ids": [result["result_id"] for result in execution.get("results", [])],
        "tool_calls": all_tool_calls,
        "post_execution": {
            "inspection_keys": sorted(inspection.keys()),
            "replay_window_id": replay.get("replay_window_id"),
        },
    }
    trace_id = "hermes_exec_" + stable_hash(payload)[:16]
    path = output_root / "hermes-traces" / f"{trace_id}.json"
    write_json(path, {"trace_id": trace_id, **payload})
    record_session_execution(
        compile_response=compile_response,
        execution_authorization_id=execution_authorization_id,
        execution=execution,
        inspection=inspection,
        replay=replay,
        trace_id=trace_id,
        output_root=output_root,
    )
    return {"trace_id": trace_id, **payload}


def execute_confirmed_hermes_session(
    *,
    compile_response: HermesCompileResponse,
    execution_authorization_id: str,
    result_limit: int = 3,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> dict[str, Any]:
    post_tool_calls: list[dict[str, Any]] = []
    execution = hermes_tool_call(
        "execute_query_plan",
        {
            "bound_plan_id": compile_response.bound_plan_id,
            "execution_authorization_id": execution_authorization_id,
            "result_limit": result_limit,
        },
        post_tool_calls,
        output_root=output_root,
    )
    first_result_id = execution["results"][0]["result_id"]
    inspection = hermes_tool_call(
        "inspect_result",
        {"execution_id": execution["execution_id"], "result_id": first_result_id},
        post_tool_calls,
        output_root=output_root,
    )
    replay = hermes_tool_call(
        "retrieve_replay_window",
        {"execution_id": execution["execution_id"], "result_id": first_result_id},
        post_tool_calls,
        output_root=output_root,
    )
    trace = record_confirmed_execution_trace(
        compile_response=compile_response,
        execution_authorization_id=execution_authorization_id,
        execution=execution,
        inspection=inspection,
        replay=replay,
        post_compile_tool_calls=post_tool_calls,
        output_root=output_root,
    )
    return {
        "execution": execution,
        "inspection": inspection,
        "replay": replay,
        "post_compile_tool_calls": post_tool_calls,
        "trace": trace,
    }


def persist_compile_trace(response: HermesCompileResponse, *, output_root: Path) -> None:
    path = output_root / "hermes-traces" / f"{response.trace_id}.json"
    write_json(path, response.model_dump(mode="json"))
    record_session_turn(response, output_root=output_root)


def compile_lineage_fields(request: HermesCompileRequest) -> dict[str, Any]:
    return {
        "session_id": session_id_for(request),
        "turn_id": turn_id_for(request),
        "parent_turn_id": parent_turn_id_for(request),
    }


def session_id_for(request: HermesCompileRequest) -> str:
    if request.session_id:
        return request.session_id
    return "session_" + stable_hash(
        {
            "requester": request.requester,
            "original_language": request.original_language,
        }
    )[:16]


def turn_id_for(request: HermesCompileRequest) -> str:
    return "turn_" + stable_hash(
        {
            "session_id": session_id_for(request),
            "original_language": request.original_language,
            "clarifications": request.clarifications,
            "requester": request.requester,
        }
    )[:16]


def parent_turn_id_for(request: HermesCompileRequest) -> str | None:
    if request.parent_turn_id:
        return request.parent_turn_id
    if request.clarifications:
        parent_request = request.model_copy(update={"clarifications": [], "parent_turn_id": None})
        return turn_id_for(parent_request)
    return None


def record_session_turn(response: HermesCompileResponse, *, output_root: Path) -> None:
    path = output_root / "compiler-sessions" / f"{response.session_id}.json"
    if path.exists():
        session = read_json(path)
    else:
        session = {
            "schema_version": "1.0",
            "session_id": response.session_id,
            "created_at": utc_now_iso(),
            "original_language": response.original_language,
            "turns": [],
            "executions": [],
        }
    turns = [turn for turn in session.get("turns", []) if turn.get("turn_id") != response.turn_id]
    turns.append(
        {
            "turn_id": response.turn_id,
            "parent_turn_id": response.parent_turn_id,
            "trace_id": response.trace_id,
            "recorded_at": utc_now_iso(),
            "original_language": response.original_language,
            "clarification_questions": response.clarification_questions,
            "clarification_codes": response.clarification_codes,
            "clarification_answers": response.clarifications,
            "capability_gap_codes": response.capability_gap_codes,
            "status": response.status.value,
            "model_decision": response.raw_model_output,
            "attempts": response.attempts,
            "repair_count": response.repair_count,
            "final_decision_source": response.final_decision_source,
            "deterministic_fallback": response.deterministic_fallback,
            "draft_plan_hash": response.draft_plan_hash,
            "bound_plan_hash": response.bound_plan_hash,
        }
    )
    session["turns"] = sorted(turns, key=lambda item: item["recorded_at"])
    session["updated_at"] = utc_now_iso()
    write_json(path, session)


def record_session_execution(
    *,
    compile_response: HermesCompileResponse,
    execution_authorization_id: str,
    execution: dict[str, Any],
    inspection: dict[str, Any],
    replay: dict[str, Any],
    trace_id: str,
    output_root: Path,
) -> None:
    path = output_root / "compiler-sessions" / f"{compile_response.session_id}.json"
    if path.exists():
        session = read_json(path)
    else:
        session = {
            "schema_version": "1.0",
            "session_id": compile_response.session_id,
            "created_at": utc_now_iso(),
            "original_language": compile_response.original_language,
            "turns": [],
            "executions": [],
        }
    executions = [
        item
        for item in session.get("executions", [])
        if item.get("execution_id") != execution.get("execution_id")
    ]
    executions.append(
        {
            "trace_id": trace_id,
            "turn_id": compile_response.turn_id,
            "parent_turn_id": compile_response.parent_turn_id,
            "recorded_at": utc_now_iso(),
            "execution_authorization_id": execution_authorization_id,
            "execution_id": execution.get("execution_id"),
            "result_ids": [result["result_id"] for result in execution.get("results", [])],
            "inspection_result_id": inspection.get("result_id"),
            "replay_window_id": replay.get("replay_window_id"),
        }
    )
    session["executions"] = executions
    session["updated_at"] = utc_now_iso()
    write_json(path, session)


def trace_id_for(request: HermesCompileRequest, outcome: str, payload: Any) -> str:
    return "hermes_" + stable_hash(
        {
            "original_language": request.original_language,
            "clarifications": request.clarifications,
            "requester": request.requester,
            "outcome": outcome,
            "payload": payload,
            "recorded_at": utc_now_iso(),
        }
    )[:16]


def summarize_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key, value in arguments.items():
        if key == "plan_document":
            summary[key] = {
                "recipe_id": value.get("recipe", {}).get("recipe_id") if isinstance(value, dict) else None,
                "plan_id": value.get("draft_plan", {}).get("plan_id") if isinstance(value, dict) else None,
                "status": value.get("draft_plan", {}).get("status") if isinstance(value, dict) else None,
            }
        else:
            summary[key] = value
    return summary


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def unsupported_gaps(text: str) -> list[dict[str, str]]:
    gaps = []
    for token, reason in UNSUPPORTED_CONCEPTS.items():
        if token in text:
            gaps.append({"concept": token, "reason": reason})
    return gaps


def asks_for_block_shift(text: str) -> bool:
    return "block shift" in text or ("ball side" in text and "shift" in text)


def asks_for_progressive_corridor(text: str) -> bool:
    return "corridor" in text or "passing lane" in text or "progressive lane" in text


def ambiguous_support_request(text: str) -> bool:
    return "support" in text and not asks_for_progressive_corridor(text)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
