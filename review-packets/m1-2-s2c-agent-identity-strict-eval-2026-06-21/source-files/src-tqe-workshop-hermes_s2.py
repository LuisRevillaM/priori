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
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_HERMES_MODEL = "gpt-4o-mini"
COMPILER_IDENTITY = "ModelBackedTacticalQueryCompiler"
COMPILER_IDENTITY_DECISION = (
    "S2C uses an agent-neutral model-backed tactical query compiler. It is not "
    "a completed Hermes runtime integration; Hermes remains a future client "
    "adapter over the same bounded tool surface."
)
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

Use select_recipe only when the request explicitly asks for the approved
ball-side block-shift recipe/detector. Use draft_corridor for requests about a
progressive or forward corridor/lane/passing lane from possession anchors.
Explicit thresholds are optional: when the analyst asks for corridor/lane
availability without numeric constraints, draft the corridor plan with no
parameter overrides and let the runtime defaults apply.
Never return capability_gap merely because a corridor/lane request lacks numeric
thresholds; default thresholds are valid and intentionally supported.
Treat progressive lane, forward lane, passing lane, forward route, geometric
progressive option, and open corridor as aliases for the experimental
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
  from defenders" set corridor_minimum_clearance_m=N. Do not put defender
  clearance values into progression.
- "within N seconds" sets corridor_max_window_seconds=N.
- Include only parameters materially requested by the analyst. Do not restate
  defaults as explicit parameter overrides.

Unsupported concepts include body orientation, body shape, facial cues, scanning,
intent, communication, video, pass probability, causality, deception, coach
instructions, and optimal actions.
If any unsupported concept appears, choose capability_gap rather than clarify.
The gap must name every material unsupported concept in the request.

Important ambiguity rule: if the request uses support/help/second runner/overload
or line-break support language without explicitly saying corridor, passing lane,
progressive lane, or a clarification answer that maps support to a progressive
corridor, you must choose action="clarify". Do not draft and do not capability-gap
those support requests. Ask what support should mean and what time window should
apply.
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


class HermesCompileResponse(StrictModel):
    ok: bool
    status: HermesCompileStatus
    trace_id: str
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
    interpretation: dict[str, Any]
    selected_recipe: dict[str, Any] | None = None
    draft_plan_id: str | None = None
    draft_plan_hash: str | None = None
    bound_plan_id: str | None = None
    bound_plan_hash: str | None = None
    validation_result: dict[str, Any] | None = None
    clarification_questions: list[str] = Field(default_factory=list)
    capability_gaps: list[dict[str, str]] = Field(default_factory=list)
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
    requested_evidence: list[Literal["relation_count", "witness_relation_id"]] = Field(default_factory=list, max_length=2)


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
            }
        except ValidationError as repair_exc:
            model_payload = {
                **repair_payload,
                "invalid_first_output": model_payload["json"],
                "first_output_schema_errors": exc.errors(),
            }
            exc = repair_exc
        else:
            exc = None
    if isinstance(locals().get("exc"), ValidationError):
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
        }
        response = HermesCompileResponse(
            ok=False,
            status=HermesCompileStatus.MODEL_OUTPUT_INVALID,
            trace_id=trace_id_for(request, "model_output_invalid", model_payload["json"]),
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
            model_payload = {
                **repair_payload,
                "invalid_first_output": model_payload["json"],
                "first_output_semantic_errors": semantic_errors,
            }
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
            }
            response = HermesCompileResponse(
                ok=False,
                status=HermesCompileStatus.MODEL_OUTPUT_INVALID,
                trace_id=trace_id_for(request, "model_output_invalid_after_semantic_repair", model_payload["json"]),
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
        semantic_errors_after_repair = semantic_decision_errors(request, decision)
        model_payload = {
            **repair_payload,
            "invalid_first_output": model_payload["json"],
            "first_output_semantic_errors": semantic_errors,
        }
        if semantic_errors_after_repair:
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
                "model_output_errors": [{"type": "semantic_validation", "message": item} for item in semantic_errors_after_repair],
            }
            response = HermesCompileResponse(
                ok=False,
                status=HermesCompileStatus.MODEL_OUTPUT_INVALID,
                trace_id=trace_id_for(request, "model_semantic_invalid", model_payload["json"]),
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
    }

    if decision["action"] == "capability_gap":
        response = HermesCompileResponse(
            ok=False,
            status=HermesCompileStatus.CAPABILITY_GAP,
            trace_id=trace_id_for(request, "model_capability_gap", decision),
            original_language=request.original_language,
            clarifications=request.clarifications,
            interpretation={
                "intent": "unsupported_tactical_request",
                "summary": decision["interpretation"],
                "automatic_execution": False,
            },
            capability_gaps=dedupe_gaps(decision["capability_gaps"]),
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
            original_language=request.original_language,
            clarifications=request.clarifications,
            interpretation={
                "intent": "clarify_tactical_request",
                "summary": decision["interpretation"],
                "automatic_execution": False,
            },
            clarification_questions=decision["clarification_questions"],
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
            original_language=request.original_language,
            clarifications=request.clarifications,
            interpretation={
                "intent": "unsupported_tactical_request",
                "reason": "The request asks for concepts outside the exposed capability context.",
                "available_tool_count": len(capabilities.get("tools", [])),
            },
            capability_gaps=gaps,
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
            original_language=request.original_language,
            clarifications=request.clarifications,
            interpretation={
                "intent": "ambiguous_support_request",
                "reason": "The current vocabulary can measure possession anchors and progressive corridors, but support has multiple tactical meanings.",
                "automatic_execution": False,
            },
            clarification_questions=questions,
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
    semantic_errors: list[str] | None = None,
) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for model-backed Hermes S2B verification")
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
    requested_evidence: list[str] = []
    recipe_id: str | None = None
    if isinstance(decision, SelectRecipeDecision):
        action = decision.action
        recipe_id = decision.recipe_id
    elif isinstance(decision, DraftCorridorDecision):
        action = decision.action
        recipe_id = decision.recipe_id
        params = decision.corridor_parameters.model_dump()
        requested_evidence = list(decision.requested_evidence)
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
        "requested_evidence": requested_evidence,
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
                "requested_evidence_allowed_values": ["relation_count", "witness_relation_id"],
            },
        },
        "trusted_recipe_summaries": recipe_summaries,
    }


def compiler_classification_rules() -> dict[str, Any]:
    return {
        "draft_corridor_when_request_contains": [
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
        ],
        "draft_corridor_requires_context_any_of": [
            "possession",
            "possession anchor",
            "active-ball",
            "ball carrier",
            "team in possession",
        ],
        "clarify_not_gap_when_request_contains_without_corridor_alias": [
            "support",
            "help",
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
            "body shape",
            "facial cue",
            "scanning",
            "scanned",
            "intent",
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


def semantic_decision_errors(request: HermesCompileRequest, decision: dict[str, Any]) -> list[str]:
    text = normalize_text(resolved_request_for_model(request))
    rules = compiler_classification_rules()
    errors: list[str] = []
    has_unsupported = [term for term in rules["capability_gap_when_request_contains"] if term in text]
    if has_unsupported:
        if decision["action"] != "capability_gap":
            errors.append(
                "Requests containing unsupported concepts must use action=capability_gap: "
                + ", ".join(has_unsupported)
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
                elif term == "scanned":
                    expected_terms = ["scan", "scanning", "scanned"]
                elif term == "should have done":
                    expected_terms = ["should", "optimal", "decision"]
                elif term == "mutate primitive":
                    expected_terms = ["mutate", "mutation", "primitive"]
                else:
                    expected_terms = [term]
                if not any(expected in gap_text for expected in expected_terms):
                    errors.append(f"Capability gap must name unsupported concept: {term}")
        return errors

    corridor_aliases = rules["draft_corridor_when_request_contains"]
    corridor_context = rules["draft_corridor_requires_context_any_of"]
    has_corridor_alias = any(alias in text for alias in corridor_aliases)
    matched_corridor_aliases = [alias for alias in corridor_aliases if alias in text]
    has_corridor_context = any(context in text for context in corridor_context) or bool(request.clarifications)
    if has_corridor_alias and has_corridor_context and decision["action"] != "draft_corridor":
        errors.append(
            "The request contains supported corridor aliases "
            f"{matched_corridor_aliases} with possession context. Correct output must be "
            "action=draft_corridor, recipe_id=possession_corridor_availability_v1, and no "
            "capability_gaps for these aliases."
        )

    clarification_text = normalize_text(" ".join(request.clarifications))
    if request.clarifications and any(alias in clarification_text for alias in rules["draft_corridor_when_clarification_contains"]):
        if decision["action"] != "draft_corridor":
            errors.append("Clarification answer maps support to a corridor alias; action must be draft_corridor.")

    ambiguous_terms = rules["clarify_not_gap_when_request_contains_without_corridor_alias"]
    if any(term in text for term in ambiguous_terms) and not has_corridor_alias and not request.clarifications:
        if decision["action"] != "clarify":
            errors.append("Ambiguous support/help/second-runner language must clarify instead of draft or gap.")
        elif any(term in text for term in rules["clarify_distance_when_request_contains"]):
            question_text = normalize_text(" ".join(decision["clarification_questions"]))
            if not any(token in question_text for token in ("distance", "close", "near", "proximity")):
                errors.append("Close/near support clarification must ask for a distance or proximity threshold.")
    return errors


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
        "original_language": compile_response.original_language,
        "clarification_turns": [
            {
                "turn_index": index + 1,
                "answer": answer,
            }
            for index, answer in enumerate(compile_response.clarifications)
        ],
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
