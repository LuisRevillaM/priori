"""M1.2 S2 bounded Hermes compiler shell.

This module is deterministic test scaffolding for the Hermes client contract. It
does not call a model and does not widen the tool boundary. It records the
language-to-plan trace that a future model-backed Hermes instance must preserve.
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
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

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
HERMES_SYSTEM_PROMPT = """You are Hermes, a bounded tactical-query compiler.

You may return only JSON. You may choose exactly one action:
- select_recipe: choose the trusted approved ball-side block-shift recipe.
- draft_corridor: draft an EXPERIMENTAL progressive-corridor plan using existing capabilities.
- clarify: ask concise clarification questions.
- capability_gap: refuse unsupported concepts explicitly.

Never invent primitive, relation, operator, recipe, or tool identifiers.
Never request raw tracking dumps, code execution, filesystem paths, SQL, video,
primitive mutation, threshold auto-tuning, or execution confirmation.

Available experimental draft family:
- possession_corridor_availability_v1 using possession anchors and
  geometric_progressive_corridor_from_anchor_set.
Allowed draft parameters:
- corridor_minimum_progression_m: number of metres, default 5.0
- corridor_minimum_clearance_m: number of metres, default 4.0
- corridor_max_window_seconds: seconds, default 5.0
- corridor_minimum_duration_seconds: seconds, default 0.4

Supported wording for draft_corridor includes corridor availability, open
corridor, forward corridor, forward lane, progressive lane, progressive passing
lane, geometric progressive option, active-ball possessions with a progressive
corridor, and possession anchors with a corridor option.

Parameter extraction rules:
- "at least N metres progression", "advance N metres", and "N metres of gain"
  set corridor_minimum_progression_m=N.
- "N metres defender clearance", "N metres defensive clearance", and "clearance
  from defenders" set corridor_minimum_clearance_m=N. Do not put defender
  clearance values into progression.
- "within N seconds" sets corridor_max_window_seconds=N.

Unsupported concepts include body orientation, body shape, facial cues, scanning,
intent, communication, video, pass probability, causality, deception, coach
instructions, and optimal actions.

Important ambiguity rule: if the request uses support/help/second runner/overload
or line-break support language without explicitly saying corridor, passing lane,
progressive lane, or a clarification answer that maps support to a progressive
corridor, you must choose action="clarify". Do not draft and do not capability-gap
those support requests. Ask what support should mean and what time window should
apply.

Clarification rule: the clarifications array contains authoritative user answers
to your prior questions. If the original request was ambiguous support language
and the clarification history says "progressive corridor within two seconds" or
an equivalent answer, you must choose action="draft_corridor" and set
corridor_max_window_seconds=2.0. Do not ask the same clarification again once
the clarifications array answers it.

Return JSON with this shape:
{
  "action": "select_recipe|draft_corridor|clarify|capability_gap",
  "recipe_id": "ball_side_block_shift_v1|possession_corridor_availability_v1|null",
  "interpretation": "short analyst-facing interpretation",
  "clarification_questions": ["..."],
  "capability_gaps": [{"concept": "...", "reason": "..."}],
  "corridor_parameters": {
    "corridor_minimum_progression_m": number|null,
    "corridor_minimum_clearance_m": number|null,
    "corridor_max_window_seconds": number|null,
    "corridor_minimum_duration_seconds": number|null
  },
  "requested_evidence": ["relation_count", "witness_relation_id"]
}

Examples:
- "Show when a forward lane is available from possession." -> draft_corridor.
- "Find open forward lanes from active possession anchors." -> draft_corridor.
- "Find progressive corridors with at least 6 metres defender clearance." ->
  draft_corridor with corridor_minimum_clearance_m=6.0.
- "Find intent to pass through the line." -> capability_gap.
- "Use video to judge receiver scanning." -> capability_gap.
- "Infer coach instructions from movement." -> capability_gap.
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
    agent_kind: Literal["model_backed", "deterministic_reference"] = "deterministic_reference"
    model_provider: str | None = None
    model_name: str | None = None
    model_response_id: str | None = None
    system_prompt_hash: str | None = None
    capability_context_hash: str | None = None
    tool_schema_hash: str | None = None
    raw_model_output: dict[str, Any] | None = None
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
    model_payload = call_hermes_model(
        request=request,
        capability_context=capability_payload,
        recipe_summaries=recipe_summaries,
    )
    decision = normalize_model_decision(model_payload["json"])
    metadata = {
        "agent_kind": "model_backed",
        "model_provider": "openai",
        "model_name": model_payload["model"],
        "model_response_id": model_payload.get("id"),
        "system_prompt_hash": stable_hash(HERMES_SYSTEM_PROMPT),
        "capability_context_hash": stable_hash(capability_payload),
        "tool_schema_hash": stable_hash([tool.get("name") for tool in capabilities.get("tools", [])]),
        "raw_model_output": model_payload["json"],
    }

    if decision["action"] == "capability_gap":
        response = HermesCompileResponse(
            ok=False,
            status=HermesCompileStatus.CAPABILITY_GAP,
            trace_id=trace_id_for(request, "model_capability_gap", decision),
            original_language=request.original_language,
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
    response = HermesCompileResponse(
        ok=bool(validation.get("ok")),
        status=HermesCompileStatus.DRAFT_VALIDATED,
        trace_id=trace_id_for(request, "model_draft_validated", decision),
        original_language=request.original_language,
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
        response = HermesCompileResponse(
            ok=bool(validation.get("ok")),
            status=HermesCompileStatus.DRAFT_VALIDATED,
            trace_id=trace_id_for(request, "draft_validated", validation),
            original_language=request.original_language,
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
                        "trusted_recipes": recipe_summaries,
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
    }


def normalize_model_decision(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action", "")).strip()
    if action not in {"select_recipe", "draft_corridor", "clarify", "capability_gap"}:
        raise RuntimeError(f"Model returned unsupported action: {action}")
    recipe_id = payload.get("recipe_id")
    if recipe_id == "null":
        recipe_id = None
    if recipe_id not in {None, "ball_side_block_shift_v1", "possession_corridor_availability_v1"}:
        raise RuntimeError(f"Model returned unsupported recipe_id: {recipe_id}")
    if action == "select_recipe" and recipe_id != "ball_side_block_shift_v1":
        raise RuntimeError("select_recipe may only choose ball_side_block_shift_v1")
    if action == "draft_corridor" and recipe_id not in {None, "possession_corridor_availability_v1"}:
        raise RuntimeError("draft_corridor may only use possession_corridor_availability_v1")
    params = payload.get("corridor_parameters") if isinstance(payload.get("corridor_parameters"), dict) else {}
    allowed_params = {
        "corridor_minimum_progression_m",
        "corridor_minimum_clearance_m",
        "corridor_max_window_seconds",
        "corridor_minimum_duration_seconds",
    }
    normalized_params = {}
    for key in allowed_params:
        value = params.get(key)
        if value is None:
            normalized_params[key] = None
        elif isinstance(value, int | float) and not isinstance(value, bool):
            normalized_params[key] = float(value)
        else:
            raise RuntimeError(f"Invalid corridor parameter {key}: {value!r}")
    gaps = payload.get("capability_gaps")
    if not isinstance(gaps, list):
        gaps = []
    normalized_gaps = [
        {
            "concept": str(item.get("concept", "unsupported")),
            "reason": str(item.get("reason", "Unsupported by current capability context.")),
        }
        for item in gaps
        if isinstance(item, dict)
    ]
    questions = payload.get("clarification_questions")
    if not isinstance(questions, list):
        questions = []
    return {
        "action": action,
        "recipe_id": recipe_id,
        "interpretation": str(payload.get("interpretation", "")).strip() or action,
        "clarification_questions": [str(item) for item in questions][:4],
        "capability_gaps": normalized_gaps,
        "corridor_parameters": normalized_params,
        "requested_evidence": payload.get("requested_evidence", []),
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
    return {
        "recipe_id": recipe["recipe_id"],
        "recipe_version": recipe["recipe_version"],
        "display_name": recipe["display_name"],
        "state": state,
        "output_classifications": recipe.get("output_classifications", []),
        "allowed_claims": recipe.get("allowed_claims", []),
        "limitations": recipe.get("limitations", []),
    }


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
        "clarification_turns": [],
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
