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


DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-sonnet-4-5"
DEFAULT_TOOLSET = "mcp-priori_tactical"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HermesNLAccessError(RuntimeError):
    """Raised when the required real Hermes model path cannot produce output."""


class HermesNLModelOutputError(ValueError):
    """Raised when Hermes returns JSON that is not one of the four allowed shapes."""


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
        candidates = [self.reading_id, self.label, *self.answer_aliases]
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


@dataclass(frozen=True)
class WorkshopHermesInvoker:
    provider: str = DEFAULT_PROVIDER
    model: str = DEFAULT_MODEL
    toolset: str = DEFAULT_TOOLSET
    timeout_seconds: int = 180
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
    )
    raw_completion = active_invoker.invoke(prompt)
    transcript = transcript_for(
        projection=projection,
        raw_completion=raw_completion,
        provider=active_invoker.provider,
        model=active_invoker.model,
        invocation={"request_text": text},
    )
    return parse_hermes_completion(raw_completion, transcript=transcript, vocabulary=vocabulary)


def build_prompt_projection(pack_path: Path = DEFAULT_KNOWLEDGE_PACK_PATH) -> PromptProjection:
    payload = json.loads(pack_path.read_text(encoding="utf-8"))
    sections = prompt_sections_from_pack(payload)
    section_json = json.dumps(sections, indent=2, sort_keys=True)
    prompt = (
        "You are the SCP2-2 Hermes NL-to-meaning compiler.\n"
        "Your only valid output is one JSON object with outcome equal to exactly one of: "
        "expression, clarification_required, understood_but_not_expressible, unsupported_modality.\n"
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
        "source media such as video, audio, images, or external annotation.\n"
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


def prompt_sections_from_pack(pack: dict[str, Any]) -> dict[str, Any]:
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
            }
            for parameter in item.get("parameters") or []
        ],
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
        + "\nReturn only the JSON object.\n"
    )


def parse_hermes_completion(
    raw_completion: str,
    *,
    transcript: TranscriptEvidence,
    vocabulary: PackVocabulary,
) -> HermesOutcome:
    try:
        payload = json.loads(strip_json_fence(raw_completion))
        parsed = MODEL_OUTPUT_ADAPTER.validate_python(payload)
    except Exception as exc:  # noqa: BLE001
        raise HermesNLModelOutputError(f"Hermes output is not an allowed SCP2-2 shape: {exc}") from exc
    if isinstance(parsed, ModelExpressionOutput):
        return expression_outcome(parsed.expression, transcript=transcript, vocabulary=vocabulary)
    if isinstance(parsed, ModelClarificationOutput):
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
                    "dimension": parsed.dimension,
                    "question": parsed.question,
                    "readings": [reading.model_dump(mode="json", exclude_none=True) for reading in readings],
                    "prompt_hash": transcript.prompt_hash,
                }
            ),
            original_text=str(transcript.invocation.get("request_text") or ""),
            dimension=parsed.dimension,
            question=parsed.question,
            readings=readings,
            prompt_hash=transcript.prompt_hash,
            pack_sha256=transcript.pack_sha256,
        )
        return ClarificationRequiredOutcome(
            outcome="clarification_required",
            dimension=parsed.dimension,
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
    for reading in state.readings:
        if reading.matches(answer):
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
            return ExpressionOutcome(
                outcome="expression",
                expression=reading.expression,
                expression_json=json.loads(stable_expression_json(reading.expression)),
                document_hash=reading.expression.document_hash(),
                transcript=transcript,
            )
    raise HermesNLModelOutputError(f"clarification answer did not select a typed reading: {answer}")


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
