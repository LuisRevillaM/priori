"""SCP2-2 Hermes natural-language bridge to meaning expressions."""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from tqe.runtime.ir import stable_hash
from tqe.semantic_compiler.meaning_expression import (
    BridgeRefusal,
    BridgeRefusalKind,
    DEFAULT_KNOWLEDGE_PACK_PATH,
    MeaningExpressionV0,
    MissingGapCodeError,
    PackVocabulary,
    load_meaning_expression_result,
    load_pack_vocabulary,
    stable_expression_json,
)


DEFAULT_PROVIDER = "openai-codex"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_TOOLSET = "mcp-priori_tactical"
MAX_MODEL_REPAIR_ATTEMPTS = 2
DEFAULT_SCP2_2_MAX_OUTPUT_TOKENS = 32768
CERTIFIED_FEW_SHOT_PATHS = (
    Path("delivery/packets/scp2-1-roundtrip/meaning-expressions/fragile_possession_state_known.v0.json"),
    Path("delivery/packets/scp2-1-roundtrip/meaning-expressions/fragile_window_join_count_novel.v0.json"),
    Path("delivery/packets/r2-4-flagship/meaning-expressions/counterattack_initiation_sequence_rate.v0.json"),
)
NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HermesNLAccessError(RuntimeError):
    """Raised when the required real Hermes model path cannot produce output."""


class HermesNLModelOutputError(ValueError):
    """Raised when Hermes returns JSON that is not one of the four allowed shapes."""

    def __init__(
        self,
        message: str,
        *,
        raw_completion: str | None = None,
        rejected_attempts: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.raw_completion = raw_completion
        self.rejected_attempts = rejected_attempts or []


class HermesNLModelOutputTruncatedError(HermesNLModelOutputError):
    """Raised when Hermes appears to have been cut off before closing JSON."""


class HermesNLClarificationSelectionError(ValueError):
    """Raised when a local clarification answer selects no typed reading."""


class TranscriptEvidence(StrictModel):
    prompt_hash: str
    pack_sha256: str
    raw_completion: str
    completion_hash: str
    model_provider: str | None = None
    model_name: str | None = None
    invocation: dict[str, Any] = Field(default_factory=dict)


class ClarificationReading(StrictModel):
    reading_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1)
    answer_aliases: list[str] = Field(default_factory=list)
    expression: MeaningExpressionV0

    def matches(self, answer: str) -> bool:
        normalized = normalize_text(answer)
        candidates = clarification_reading_candidates(self)
        return any(normalize_text(candidate) in normalized for candidate in candidates if candidate)


class ClarificationState(StrictModel):
    state_id: str
    original_text: str
    dimension: str = Field(min_length=1)
    question: str = Field(min_length=1)
    readings: list[ClarificationReading] = Field(min_length=2)
    prompt_hash: str
    pack_sha256: str


class HermesNLContext(StrictModel):
    pending_clarification: ClarificationState | None = None
    answer: str | None = None


class ExpressionOutcome(StrictModel):
    outcome: Literal["expression"]
    expression: MeaningExpressionV0
    expression_json: dict[str, Any]
    document_hash: str
    transcript: TranscriptEvidence


class ClarificationRequiredOutcome(StrictModel):
    outcome: Literal["clarification_required"]
    dimension: str = Field(min_length=1)
    question: str = Field(min_length=1)
    readings: list[ClarificationReading] = Field(min_length=2)
    state: ClarificationState
    transcript: TranscriptEvidence


class UnderstoodButNotExpressibleOutcome(StrictModel):
    outcome: Literal["understood_but_not_expressible"]
    gap_code: str = Field(min_length=1)
    missing_capability: str = Field(min_length=1)
    message: str = Field(min_length=1)
    transcript: TranscriptEvidence
    refusal: BridgeRefusal | None = None


class UnsupportedModalityOutcome(StrictModel):
    outcome: Literal["unsupported_modality"]
    modality: str = Field(min_length=1)
    gap_code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    transcript: TranscriptEvidence


HermesOutcome = Annotated[
    ExpressionOutcome
    | ClarificationRequiredOutcome
    | UnderstoodButNotExpressibleOutcome
    | UnsupportedModalityOutcome,
    Field(discriminator="outcome"),
]
HERMES_OUTCOME_ADAPTER = TypeAdapter(HermesOutcome)


class PromptProjection(StrictModel):
    schema_version: Literal["scp2_2.prompt_projection.v0"] = "scp2_2.prompt_projection.v0"
    pack_path: str
    pack_sha256: str
    prompt: str
    prompt_hash: str
    sections: dict[str, Any]


class ModelExpressionOutput(StrictModel):
    outcome: Literal["expression"]
    expression: dict[str, Any]


class ModelClarificationReading(StrictModel):
    reading_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1)
    answer_aliases: list[str] = Field(default_factory=list)
    expression: dict[str, Any]


class ModelClarificationOutput(StrictModel):
    outcome: Literal["clarification_required"]
    dimension: str = Field(min_length=1)
    question: str = Field(min_length=1)
    readings: list[ModelClarificationReading] = Field(min_length=2)


class ModelUnderstoodOutput(StrictModel):
    outcome: Literal["understood_but_not_expressible"]
    gap_code: str = Field(min_length=1)
    missing_capability: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ModelUnsupportedModalityOutput(StrictModel):
    outcome: Literal["unsupported_modality"]
    modality: str = Field(min_length=1)
    gap_code: str = Field(min_length=1)
    message: str = Field(min_length=1)


ModelOutput = Annotated[
    ModelExpressionOutput
    | ModelClarificationOutput
    | ModelUnderstoodOutput
    | ModelUnsupportedModalityOutput,
    Field(discriminator="outcome"),
]
MODEL_OUTPUT_ADAPTER = TypeAdapter(ModelOutput)


class HermesCompletionInvoker(Protocol):
    provider: str
    model: str

    def invoke(self, prompt: str) -> str:
        """Return raw model completion text from the real configured model path."""


def scp2_2_max_output_tokens() -> int:
    raw = os.environ.get("HERMES_SCP2_2_MAX_OUTPUT_TOKENS")
    if raw is None:
        return DEFAULT_SCP2_2_MAX_OUTPUT_TOKENS
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_SCP2_2_MAX_OUTPUT_TOKENS
    return parsed if parsed > 0 else DEFAULT_SCP2_2_MAX_OUTPUT_TOKENS


@dataclass(frozen=True)
class WorkshopHermesInvoker:
    provider: str = DEFAULT_PROVIDER
    model: str = DEFAULT_MODEL
    toolset: str = DEFAULT_TOOLSET
    timeout_seconds: int = 180
    max_output_tokens: int = DEFAULT_SCP2_2_MAX_OUTPUT_TOKENS
    output_root: Path | None = None

    def invoke(self, prompt: str) -> str:
        hermes = shutil.which("hermes")
        if not hermes:
            raise HermesNLAccessError("Hermes executable was not found.")
        from tqe.workshop.app_service import parse_invocation_json, run_hermes_invocation

        completed = run_hermes_invocation(
            hermes,
            [
                "interpret",
                "--provider",
                self.provider,
                "--model",
                self.model,
                "--toolset",
                self.toolset,
                "--max-output-tokens",
                str(self.max_output_tokens),
                "--prompt",
                prompt,
            ],
            timeout=self.timeout_seconds,
            output_root=self.output_root,
        )
        payload = parse_invocation_json(completed.stdout)
        if completed.returncode != 0 or payload.get("ok") is not True:
            stderr = str(payload.get("stderr") or completed.stderr or "")[:500]
            raise HermesNLAccessError(f"Hermes model invocation failed: {stderr}")
        completion = str(payload.get("stdout") or "")
        if not completion.strip():
            raise HermesNLAccessError("Hermes produced no final response.")
        return completion


def compile_nl_request(
    text: str,
    context: HermesNLContext | None = None,
    *,
    invoker: HermesCompletionInvoker | None = None,
    pack_path: Path = DEFAULT_KNOWLEDGE_PACK_PATH,
) -> HermesOutcome:
    if not text.strip():
        raise ValueError("text must be non-empty")
    vocabulary = load_pack_vocabulary(pack_path)
    if context and context.pending_clarification and context.answer:
        return resume_from_clarification(context.pending_clarification, context.answer)
    projection = build_prompt_projection(pack_path)
    prompt = render_model_prompt(projection, text=text, context=context)
    active_invoker = invoker or WorkshopHermesInvoker(
        provider=os.environ.get("HERMES_SCP2_2_PROVIDER", DEFAULT_PROVIDER),
        model=os.environ.get("HERMES_SCP2_2_MODEL", DEFAULT_MODEL),
        max_output_tokens=scp2_2_max_output_tokens(),
    )
    raw_completion = active_invoker.invoke(prompt)
    rejected_attempts: list[dict[str, str]] = []
    for attempt_index in range(MAX_MODEL_REPAIR_ATTEMPTS + 1):
        transcript = transcript_for(
            projection=projection,
            raw_completion=raw_completion,
            provider=active_invoker.provider,
            model=active_invoker.model,
            invocation={
                "request_text": text,
                "repair_attempt_count": len(rejected_attempts),
                "rejected_attempts": list(rejected_attempts),
                "max_output_tokens": getattr(active_invoker, "max_output_tokens", None),
            },
        )
        try:
            outcome = parse_hermes_completion(raw_completion, transcript=transcript, vocabulary=vocabulary)
            return outcome
        except HermesNLModelOutputTruncatedError as exc:
            rejected_attempt = {
                "completion_hash": stable_hash({"completion": raw_completion}),
                "error_code": "MODEL_OUTPUT_TRUNCATED",
                "error": str(exc),
            }
            if attempt_index >= MAX_MODEL_REPAIR_ATTEMPTS:
                return model_output_truncated_refusal(
                    transcript=transcript_for(
                        projection=projection,
                        raw_completion=raw_completion,
                        provider=active_invoker.provider,
                        model=active_invoker.model,
                        invocation={
                            "request_text": text,
                            "repair_attempt_count": len(rejected_attempts),
                            "rejected_attempts": [*rejected_attempts, rejected_attempt],
                            "max_output_tokens": getattr(active_invoker, "max_output_tokens", None),
                        },
                    )
                )
            rejected_attempts.append(rejected_attempt)
            raw_completion = active_invoker.invoke(
                render_truncation_prompt(
                    projection,
                    text=text,
                    context=context,
                    rejected_completion=raw_completion,
                    validation_error=str(exc),
                    repair_attempt=len(rejected_attempts),
                )
            )
        except HermesNLModelOutputError as exc:
            if attempt_index >= MAX_MODEL_REPAIR_ATTEMPTS:
                raise HermesNLModelOutputError(
                    str(exc),
                    raw_completion=raw_completion,
                    rejected_attempts=list(rejected_attempts),
                ) from exc
            rejected_attempts.append(
                {
                    "completion_hash": stable_hash({"completion": raw_completion}),
                    "error": str(exc),
                }
            )
            raw_completion = active_invoker.invoke(
                render_repair_prompt(
                    projection,
                    text=text,
                    context=context,
                    rejected_completion=raw_completion,
                    validation_error=str(exc),
                    repair_attempt=len(rejected_attempts),
                )
            )
    raise AssertionError("unreachable model repair loop exit")


def build_prompt_projection(pack_path: Path = DEFAULT_KNOWLEDGE_PACK_PATH) -> PromptProjection:
    payload = json.loads(pack_path.read_text(encoding="utf-8"))
    sections = prompt_sections_from_pack(payload, pack_path=pack_path)
    section_json = json.dumps(sections, separators=(",", ":"), sort_keys=True)
    prompt = (
        "You are the SCP2-2 Hermes NL-to-meaning compiler.\n"
        "Your only valid output is one JSON object with outcome equal to exactly one of: "
        "expression, clarification_required, understood_but_not_expressible, unsupported_modality.\n"
        "The first byte of the final answer must be { and the last byte must be }. "
        "Never put a sentence, label, markdown fence, or tool summary outside that JSON object.\n"
        "For expression outcomes, output a complete MeaningExpressionV0 in the expression field. "
        "It must use only vocabulary present in the generated knowledge projection below.\n"
        "For clarification_required, name one ambiguity dimension and provide at least two concrete readings; "
        "each reading must include a full expressible MeaningExpressionV0.\n"
        "Use generated ambiguity dimension codes or labels, and use deterministic lower-snake IDs "
        "from the normalized meaning rather than the user's phrasing.\n"
        "For understood_but_not_expressible, cite the smallest missing capability and one generated gap_code.\n"
        "For unsupported_modality, cite the unsupported modality and generated gap_code.\n"
        "The final JSON must validate against model_output_schema exactly. Use key message, not explanation. "
        "Use key modality, not unsupported_modality. For clarification use dimension as a string, question as "
        "a string, and readings with reading_id, label, answer_aliases, expression. Do not use "
        "ambiguity_dimension, ambiguity, description, or reading_label.\n"
        "Vocabulary placement is strict: concept_refs may contain only generated concept names; composition "
        "operator names belong only in operator_applications.operator or composition_constraints.kind. "
        "All field names must come from generated field_names; do not invent required_evidence or status fields. "
        "The supported modalities are tracking, events, and tracking_event_synchronized. Do not refuse merely "
        "because a request relies on event data or tracking data. Use unsupported_modality only for unavailable "
        "source media such as video, audio, images, or external annotation. Use generated refusal_routing: only "
        "gap codes listed under unsupported_modality_gap_codes may use unsupported_modality; all other generated "
        "gap codes are understood_but_not_expressible.\n"
        "Target contracts are declarative compiler-search contracts, not prose summaries and not direct query "
        "plans. required_evidence and status_semantics.field must be concrete generated evidence/output fields, "
        "never the reporting concept name, recipe_id, display_name, or tactical phrase. For primitive asks, prefer "
        "the primitive's generated status/output fields plus predicate status_semantics. For composed asks, use "
        "composition_constraints.kind from generated constraint_kinds and only that kind's generated parameter "
        "names. Do not place unsupported join keys or field names in constraint parameters.\n"
        "Prefer the smallest generated primitive/relation/recipe that already covers the request. Do not add "
        "window, typed_join, aggregate, or rate composition for adjectives that are already covered by a generated "
        "concept purpose, output status field, parameter default, or recipe authoring guide.\n"
        "Population scope is strict: do not invent match_ids. Leave match_ids empty unless the user names a "
        "specific generated match id; empty match_ids means the configured corpus/default match set. Do not narrow "
        "periods or team roles unless the user asks for that scope. For home and away, both teams, or both team "
        "roles, use perspective_team_roles [\"home\", \"away\"].\n"
        "Use generated certified_few_shot_examples as examples of synthesizeable MeaningExpressionV0 shape. "
        "They are generated from committed certified fixtures. Do not copy fixture IDs unless the request truly "
        "matches; copy the contract discipline: minimal required_evidence, concrete status fields, and only needed "
        "composition constraints.\n"
        "Use generated recipe_authoring_guides for recipe-backed requests. If the request matches a generated "
        "recipe display name, description, output classification, or declared defaulted parameter set, return an "
        "expression rather than prose or clarification. Use generated default parameter values when the request "
        "does not override them; ask clarification only when no generated default or request phrase selects a "
        "supported value.\n"
        "Use generated compiler_classification_rules for lexical routing. Generic alias-only language from the "
        "clarify_not_gap lists must ask for a generated ambiguity dimension, not an expression. Qualified alias "
        "language that maps to a generated recipe/relation with parameter defaults should use those defaults "
        "instead of re-asking solely because an enum has multiple allowed values. If text matches generated distance-clarification aliases, use the generated distance "
        "ambiguity dimension rather than a generic definition dimension.\n"
        "You may use read-only priori_tactical MCP tools to inspect capabilities, recipes, or field contracts "
        "before the final answer. Never submit, validate, execute, inspect results, or retrieve replay. Tool "
        "observations are not an output surface; the final answer is still only the JSON object.\n"
        "Do not output Markdown, explanations, tool calls, plans, recipes, or any fifth outcome shape.\n"
        "The machine side will reject anything outside MeaningExpressionV0 plus the vocabulary gate.\n\n"
        "GENERATED_KNOWLEDGE_PROJECTION:\n"
        f"{section_json}\n"
    )
    return PromptProjection(
        pack_path=str(pack_path),
        pack_sha256=str(payload["knowledge_pack_sha256"]),
        prompt=prompt,
        prompt_hash=stable_hash({"prompt": prompt}),
        sections=sections,
    )


def prompt_sections_from_pack(pack: dict[str, Any], *, pack_path: Path) -> dict[str, Any]:
    primitives = pack.get("primitives") or []
    relations = pack.get("relations") or []
    predicate_operators = pack.get("operators") or []
    grammar = pack.get("composition_grammar") or {}
    operators = grammar.get("operators") or []
    constraint_kinds = grammar.get("constraint_kinds") or []
    return {
        "pack_sha256": pack.get("knowledge_pack_sha256"),
        "meaning_expression_schema": MeaningExpressionV0.model_json_schema(mode="validation"),
        "model_output_schema": MODEL_OUTPUT_ADAPTER.json_schema(),
        "required_outcome_values": [
            "expression",
            "clarification_required",
            "understood_but_not_expressible",
            "unsupported_modality",
        ],
        "concepts": [
            concept_projection(item, kind="primitive") for item in sorted(primitives, key=lambda item: item["name"])
        ]
        + [
            concept_projection(item, kind="relation") for item in sorted(relations, key=lambda item: item["name"])
        ],
        "field_names": field_name_projection(pack),
        "predicate_operators": [
            predicate_operator_projection(item)
            for item in sorted(predicate_operators, key=lambda item: item["name"])
        ],
        "compiler_classification_rules": pack.get("compiler_classification_rules") or {},
        "recipe_authoring_guides": [
            recipe_authoring_projection(item)
            for item in sorted(pack.get("recipes") or [], key=lambda item: item["recipe_id"])
        ],
        "composition_operators": [
            operator_projection(item) for item in sorted(operators, key=lambda item: item["name"])
        ],
        "constraint_kinds": [
            {
                "kind": str(item.get("kind")),
                "parameters": sorted(str(parameter) for parameter in item.get("parameters") or []),
            }
            for item in sorted(constraint_kinds, key=lambda item: item["kind"])
        ],
        "gap_codes": [
            {
                "code": str(item.get("code")),
                "label": str(item.get("label")),
                "description": str(item.get("description")),
            }
            for item in sorted(pack.get("capability_gap_codes") or [], key=lambda item: item["code"])
        ],
        "ambiguity_dimensions": [
            {
                "code": str(item.get("code")),
                "label": str(item.get("label")),
                "description": str(item.get("description")),
            }
            for item in sorted(pack.get("ambiguity_dimensions") or [], key=lambda item: item["code"])
        ],
        "refusal_routing": refusal_routing_projection(pack),
        "certified_few_shot_examples": certified_few_shot_examples(
            vocabulary=load_pack_vocabulary(pack_path),
        ),
        "claim_boundaries": claim_boundary_projection(pack),
    }


def concept_projection(item: dict[str, Any], *, kind: str) -> dict[str, Any]:
    outputs = item.get("outputs") or []
    return {
        "kind": kind,
        "name": str(item.get("name")),
        "agent_authorable": bool(item.get("agent_authorable")),
        "outputs": [
            {
                "name": str(output.get("name")),
                "payload_type": str(output.get("payload_type")),
                "temporal_type": str(output.get("temporal_type")),
            }
            for output in outputs
        ],
        "parameters": [
            {
                "name": str(parameter.get("name")),
                "unit": str(parameter.get("unit", "none")),
                "payload_type": str(parameter.get("payload_type")),
                "default": parameter_default_value(parameter),
                "allowed_values": list(parameter.get("allowed_values") or []),
            }
            for parameter in item.get("parameters") or []
        ],
        "purpose": str(item.get("purpose") or ""),
        "limitations": [str(value) for value in item.get("limitations") or []],
    }


def field_name_projection(pack: dict[str, Any]) -> list[str]:
    names: set[str] = set()
    for bucket, values in (pack.get("evidence_fields") or {}).items():
        names.add(str(bucket))
        names.update(str(value) for value in values)
    for item in [
        *(pack.get("primitives") or []),
        *(pack.get("relations") or []),
        *((pack.get("composition_grammar") or {}).get("operators") or []),
    ]:
        names.update(str(field) for field in item.get("evidence_fields") or [])
        for output in item.get("outputs") or []:
            names.add(str(output.get("name")))
            names.update(str(field) for field in output.get("evidence_fields") or [])
    return sorted(names)


def operator_projection(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(item.get("name")),
        "parameters": [
            {
                "name": str(parameter.get("name")),
                "unit": str(parameter.get("unit", "none")),
                "payload_type": str(parameter.get("payload_type")),
                "required": bool(parameter.get("required", False)),
            }
            for parameter in item.get("parameters") or []
        ],
        "outputs": [
            {
                "name": str(output.get("name")),
                "payload_type": str(output.get("payload_type")),
                "temporal_type": str(output.get("temporal_type")),
            }
            for output in item.get("outputs") or []
        ],
    }


def predicate_operator_projection(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(item.get("name")),
        "compare_required": bool(item.get("compare_required", False)),
        "duration_required": bool(item.get("duration_required", False)),
        "input_payload_types": [str(value) for value in item.get("input_payload_types") or []],
        "input_temporal_types": [str(value) for value in item.get("input_temporal_types") or []],
        "output_payload_type": str(item.get("output_payload_type")),
        "output_temporal_type": str(item.get("output_temporal_type")),
        "limitations": [str(value) for value in item.get("limitations") or []],
    }


def recipe_authoring_projection(item: dict[str, Any]) -> dict[str, Any]:
    contract = item.get("authoring_contract") or {}
    return {
        "recipe_id": str(item.get("recipe_id")),
        "display_name": str(item.get("display_name")),
        "description": str(item.get("description") or ""),
        "output_classifications": [str(value) for value in item.get("output_classifications") or []],
        "allowed_claims": [str(value) for value in item.get("allowed_claims") or []],
        "limitations": [str(value) for value in item.get("limitations") or []],
        "parameters": [
            {
                "name": str(parameter.get("name")),
                "payload_type": str(parameter.get("payload_type")),
                "unit": str(parameter.get("unit", "none")),
                "default": parameter_default_value(parameter),
                "allowed_values": list(parameter.get("allowed_values") or []),
            }
            for parameter in item.get("parameters") or []
        ],
        "authorable_catalog_refs": [
            {
                "kind": str(node.get("kind")),
                "catalog_ref": str(node.get("catalog_ref")),
                "required_inputs": sorted((node.get("required_inputs") or {}).keys()),
                "parameters": sorted((node.get("parameters") or {}).keys()),
            }
            for node in contract.get("authorable_nodes") or []
        ],
        "requested_evidence_fields": dedupe_strings(
            str(evidence.get("field"))
            for evidence in contract.get("requested_evidence") or []
        ),
        "required_status_semantics": [
            {
                "field": str((predicate.get("input") or {}).get("output_name")),
                "operator": str((predicate.get("operator") or {}).get("name")),
                "required_value": predicate_required_value(predicate),
            }
            for predicate in contract.get("required_predicates") or []
        ],
    }


def parameter_default_value(parameter: dict[str, Any]) -> Any:
    default = parameter.get("default")
    if isinstance(default, dict) and "value" in default:
        return default.get("value")
    return None


def predicate_required_value(predicate: dict[str, Any]) -> Any:
    compare = predicate.get("compare") or {}
    if "value" in compare:
        return compare.get("value")
    if "name" in compare:
        return {"parameter": compare.get("name")}
    return None


def dedupe_strings(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def refusal_routing_projection(pack: dict[str, Any]) -> dict[str, Any]:
    codes = sorted(str(item.get("code")) for item in pack.get("capability_gap_codes") or [])
    unsupported = [code for code in codes if code == "VIDEO"]
    return {
        "unsupported_modality_gap_codes": unsupported,
        "understood_but_not_expressible_gap_codes": [
            code for code in codes if code not in set(unsupported)
        ],
    }


def certified_few_shot_examples(*, vocabulary: PackVocabulary) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for path in CERTIFIED_FEW_SHOT_PATHS:
        payload = json.loads(path.read_text(encoding="utf-8"))
        result = load_meaning_expression_result(payload, vocabulary=vocabulary)
        if result.expression is None:
            raise ValueError(f"certified few-shot fixture is not accepted: {path}")
        expression = result.expression
        examples.append(
            {
                "fixture_path": str(path),
                "expression": expression.canonical_payload(),
                "minimal_contract_guidance": minimal_contract_guidance(expression),
            }
        )
    return examples


def minimal_contract_guidance(expression: MeaningExpressionV0) -> dict[str, Any]:
    contract = expression.target_contract
    return {
        "required_evidence": list(contract.required_evidence),
        "status_fields": [item.field for item in contract.status_semantics],
        "status_values": [
            item.model_dump(mode="json", exclude_none=True) for item in contract.status_semantics
        ],
        "composition_constraint_kinds": [
            constraint.kind for constraint in contract.composition_constraints
        ],
        "operator_applications": [
            item.model_dump(mode="json", exclude_none=True)
            for item in expression.operator_applications
        ],
    }


def claim_boundary_projection(pack: dict[str, Any]) -> dict[str, Any]:
    policy = pack.get("claims_policy") or {}
    recipes = pack.get("recipes") or []
    return {
        "policy": policy,
        "recipes": [
            {
                "recipe_id": recipe.get("recipe_id"),
                "display_name": recipe.get("display_name"),
                "allowed_claims": recipe.get("allowed_claims") or [],
                "disallowed_claims": recipe.get("disallowed_claims") or [],
                "limitations": recipe.get("limitations") or [],
            }
            for recipe in sorted(recipes, key=lambda item: str(item.get("recipe_id")))
        ],
    }


def render_model_prompt(
    projection: PromptProjection,
    *,
    text: str,
    context: HermesNLContext | None = None,
) -> str:
    request = {
        "request_text": text,
        "pending_clarification": (
            context.pending_clarification.model_dump(mode="json", exclude_none=True)
            if context and context.pending_clarification
            else None
        ),
        "answer": context.answer if context else None,
    }
    return (
        projection.prompt
        + "\nREQUEST:\n"
        + json.dumps(request, indent=2, sort_keys=True)
        + "\nReturn only the JSON object. No prose before or after it.\n"
    )


def render_repair_prompt(
    projection: PromptProjection,
    *,
    text: str,
    context: HermesNLContext | None,
    rejected_completion: str,
    validation_error: str,
    repair_attempt: int,
) -> str:
    request = {
        "request_text": text,
        "pending_clarification": (
            context.pending_clarification.model_dump(mode="json", exclude_none=True)
            if context and context.pending_clarification
            else None
        ),
        "answer": context.answer if context else None,
    }
    repair_payload = {
        "repair_attempt": repair_attempt,
        "request": request,
        "rejected_output": rejected_completion,
        "validation_error": validation_error,
    }
    return (
        projection.prompt
        + "\nThe previous final answer was rejected by the bridge. It was not accepted as an output surface.\n"
        + "Convert the same intended semantics into exactly one allowed JSON object. "
        + "Do not explain the repair. If the intended semantics are unsupported, emit a typed refusal JSON object.\n"
        + "REPAIR_INPUT:\n"
        + json.dumps(repair_payload, indent=2, sort_keys=True)
        + "\nReturn only the corrected JSON object. No prose before or after it.\n"
    )


def render_truncation_prompt(
    projection: PromptProjection,
    *,
    text: str,
    context: HermesNLContext | None,
    rejected_completion: str,
    validation_error: str,
    repair_attempt: int,
) -> str:
    request = {
        "request_text": text,
        "pending_clarification": (
            context.pending_clarification.model_dump(mode="json", exclude_none=True)
            if context and context.pending_clarification
            else None
        ),
        "answer": context.answer if context else None,
    }
    repair_payload = {
        "repair_attempt": repair_attempt,
        "error_code": "MODEL_OUTPUT_TRUNCATED",
        "request": request,
        "cut_off_output_hash": stable_hash({"completion": rejected_completion}),
        "validation_error": validation_error,
    }
    return (
        projection.prompt
        + "\nThe previous final JSON was cut off before it closed. Treat this as MODEL_OUTPUT_TRUNCATED.\n"
        + "Return the COMPLETE allowed JSON object for the same request from the beginning, not a fragment. "
        + "If the complete object is too large to emit safely, emit understood_but_not_expressible with "
        + "gap_code MODEL_OUTPUT_TRUNCATED, missing_capability model_output_completion, and a retry message.\n"
        + "TRUNCATION_REPAIR_INPUT:\n"
        + json.dumps(repair_payload, indent=2, sort_keys=True)
        + "\nReturn only one complete JSON object. No prose before or after it.\n"
    )


def parse_hermes_completion(
    raw_completion: str,
    *,
    transcript: TranscriptEvidence,
    vocabulary: PackVocabulary,
) -> HermesOutcome:
    text = strip_json_fence(raw_completion)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        if is_truncated_json_decode_error(text, exc):
            raise HermesNLModelOutputTruncatedError(
                f"Hermes output JSON appears truncated at end-of-output: {exc}",
                raw_completion=raw_completion,
            ) from exc
        raise HermesNLModelOutputError(
            f"Hermes output is not valid JSON: {exc}",
            raw_completion=raw_completion,
        ) from exc
    try:
        parsed = MODEL_OUTPUT_ADAPTER.validate_python(payload)
    except Exception as exc:  # noqa: BLE001
        raise HermesNLModelOutputError(
            f"Hermes output is not an allowed SCP2-2 shape: {exc}",
            raw_completion=raw_completion,
        ) from exc
    if isinstance(parsed, ModelExpressionOutput):
        return expression_outcome(parsed.expression, transcript=transcript, vocabulary=vocabulary)
    if isinstance(parsed, ModelClarificationOutput):
        dimension = canonical_ambiguity_dimension(parsed.dimension, pack_path=vocabulary.pack_path)
        readings = [
            ClarificationReading(
                reading_id=item.reading_id,
                label=item.label,
                answer_aliases=item.answer_aliases,
                expression=validated_expression(item.expression, vocabulary=vocabulary, transcript=transcript),
            )
            for item in parsed.readings
        ]
        state = ClarificationState(
            state_id=stable_hash(
                {
                    "dimension": dimension,
                    "question": parsed.question,
                    "readings": [reading.model_dump(mode="json", exclude_none=True) for reading in readings],
                    "prompt_hash": transcript.prompt_hash,
                }
            ),
            original_text=str(transcript.invocation.get("request_text") or ""),
            dimension=dimension,
            question=parsed.question,
            readings=readings,
            prompt_hash=transcript.prompt_hash,
            pack_sha256=transcript.pack_sha256,
        )
        return ClarificationRequiredOutcome(
            outcome="clarification_required",
            dimension=dimension,
            question=parsed.question,
            readings=readings,
            state=state,
            transcript=transcript,
        )
    if isinstance(parsed, ModelUnderstoodOutput):
        return UnderstoodButNotExpressibleOutcome(
            outcome="understood_but_not_expressible",
            gap_code=parsed.gap_code,
            missing_capability=parsed.missing_capability,
            message=parsed.message,
            transcript=transcript,
        )
    return UnsupportedModalityOutcome(
        outcome="unsupported_modality",
        modality=parsed.modality,
        gap_code=parsed.gap_code,
        message=parsed.message,
        transcript=transcript,
    )


def is_truncated_json_decode_error(text: str, exc: json.JSONDecodeError) -> bool:
    stripped = text.rstrip()
    if not stripped:
        return False
    if exc.pos >= max(0, len(stripped) - 4):
        return True
    if exc.msg.startswith("Unterminated string"):
        return not stripped.endswith(("}", "]"))
    if exc.msg.startswith("Expecting") and not stripped.endswith(("}", "]")):
        open_braces = stripped.count("{") - stripped.count("}")
        open_brackets = stripped.count("[") - stripped.count("]")
        return open_braces > 0 or open_brackets > 0
    return False


def model_output_truncated_refusal(*, transcript: TranscriptEvidence) -> UnderstoodButNotExpressibleOutcome:
    return UnderstoodButNotExpressibleOutcome(
        outcome="understood_but_not_expressible",
        gap_code="MODEL_OUTPUT_TRUNCATED",
        missing_capability="model_output_completion",
        message="The model's answer got cut off before it produced complete JSON. Retry the ask.",
        transcript=transcript,
    )


def expression_outcome(
    payload: dict[str, Any],
    *,
    transcript: TranscriptEvidence,
    vocabulary: PackVocabulary,
) -> HermesOutcome:
    try:
        result = load_meaning_expression_result(payload, vocabulary=vocabulary)
    except MissingGapCodeError as exc:
        raise HermesNLModelOutputError(
            f"expression references out-of-pack vocabulary without a generated gap code: {exc}"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HermesNLModelOutputError(
            f"expression is not a valid gated MeaningExpressionV0: {exc}"
        ) from exc
    if result.refusal is not None:
        refusal = result.refusal
        if refusal.outcome == BridgeRefusalKind.UNSUPPORTED_MODALITY:
            return UnsupportedModalityOutcome(
                outcome="unsupported_modality",
                modality=refusal.reference,
                gap_code=refusal.gap_code,
                message=refusal.message,
                transcript=transcript,
            )
        return UnderstoodButNotExpressibleOutcome(
            outcome="understood_but_not_expressible",
            gap_code=refusal.gap_code,
            missing_capability=refusal.missing_capability,
            message=refusal.message,
            transcript=transcript,
            refusal=refusal,
        )
    assert result.expression is not None
    return ExpressionOutcome(
        outcome="expression",
        expression=result.expression,
        expression_json=json.loads(stable_expression_json(result.expression)),
        document_hash=result.expression.document_hash(),
        transcript=transcript,
    )


def validated_expression(
    payload: dict[str, Any],
    *,
    vocabulary: PackVocabulary,
    transcript: TranscriptEvidence,
) -> MeaningExpressionV0:
    outcome = expression_outcome(payload, transcript=transcript, vocabulary=vocabulary)
    if not isinstance(outcome, ExpressionOutcome):
        raise HermesNLModelOutputError("clarification reading is not expressible")
    return outcome.expression


def resume_from_clarification(state: ClarificationState, answer: str) -> HermesOutcome:
    reading = select_clarification_reading(state.readings, answer)
    if reading is not None:
        transcript = TranscriptEvidence(
            prompt_hash=state.prompt_hash,
            pack_sha256=state.pack_sha256,
            raw_completion="",
            completion_hash=stable_hash({"typed_resume": state.state_id, "answer": answer}),
            model_provider=None,
            model_name=None,
            invocation={
                "source": "typed_clarification_state",
                "state_id": state.state_id,
                "answer": answer,
                "selected_reading_id": reading.reading_id,
            },
        )
        return expression_outcome(
            reading.expression.canonical_payload(),
            transcript=transcript,
            vocabulary=load_pack_vocabulary(),
        )
    raise HermesNLClarificationSelectionError(f"clarification answer did not select a typed reading: {answer}")


def transcript_for(
    *,
    projection: PromptProjection,
    raw_completion: str,
    provider: str | None,
    model: str | None,
    invocation: dict[str, Any] | None = None,
) -> TranscriptEvidence:
    return TranscriptEvidence(
        prompt_hash=projection.prompt_hash,
        pack_sha256=projection.pack_sha256,
        raw_completion=raw_completion,
        completion_hash=stable_hash({"completion": raw_completion}),
        model_provider=provider,
        model_name=model,
        invocation=invocation or {},
    )


def strip_json_fence(text: str) -> str:
    stripped = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def normalize_text(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9_]+", " ", text.lower()).split())


def normalized_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for token in normalize_text(text).replace("_", " ").split():
        tokens.add(NUMBER_WORDS.get(token, token))
    return tokens


def select_clarification_reading(
    readings: list[ClarificationReading],
    answer: str,
) -> ClarificationReading | None:
    exact = [reading for reading in readings if reading.matches(answer)]
    if len(exact) == 1:
        return exact[0]
    answer_tokens = normalized_tokens(answer)
    if not answer_tokens:
        return None
    scored: list[tuple[int, str, ClarificationReading]] = []
    for reading in readings:
        candidate_tokens: set[str] = set()
        for candidate in clarification_reading_candidates(reading):
            candidate_tokens.update(normalized_tokens(candidate))
        score = len(answer_tokens & candidate_tokens)
        if score:
            scored.append((score, reading.reading_id, reading))
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], item[1]))
    if scored[0][0] < 2:
        return None
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][2]


def clarification_reading_candidates(reading: ClarificationReading) -> list[str]:
    return [
        reading.reading_id,
        reading.label,
        *reading.answer_aliases,
        reading.expression.expression_id,
        reading.expression.concept_identity,
    ]


def canonical_ambiguity_dimension(dimension: str, *, pack_path: Path) -> str:
    normalized = normalize_text(dimension)
    if not normalized:
        return dimension
    try:
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
    except OSError:
        return dimension
    aliases: dict[str, str] = {}
    for item in pack.get("ambiguity_dimensions") or []:
        code = str(item.get("code") or "")
        if not code:
            continue
        aliases[normalize_text(code)] = code
        aliases[normalize_text(str(item.get("label") or ""))] = code
        aliases[normalize_text(str(item.get("description") or ""))] = code
    for alias, code in sorted(aliases.items(), key=lambda item: (-len(item[0]), item[0])):
        if alias and (normalized == alias or normalized in alias or alias in normalized):
            return code
    return dimension
