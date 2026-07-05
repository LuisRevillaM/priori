"""SCP2-1 meaning-expression schema and pack-derived vocabulary gate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from tqe.runtime.ir import stable_hash


DEFAULT_KNOWLEDGE_PACK_PATH = Path("generated/tactical-knowledge-pack.json")
EXPECTED_PRIMITIVE_COUNT = 37
EXPECTED_OPERATOR_COUNT = 8
EXPECTED_GAP_CODE_COUNT = 14


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BridgeRefusalKind(StrEnum):
    CLARIFICATION_REQUIRED = "clarification_required"
    UNDERSTOOD_BUT_NOT_EXPRESSIBLE = "understood_but_not_expressible"
    UNSUPPORTED_MODALITY = "unsupported_modality"


class BridgeRefusal(StrictModel):
    outcome: BridgeRefusalKind
    gap_code: str
    missing_capability: str
    reference: str
    vocabulary_section: str
    message: str
    pack_sha256: str


class MeaningLoadResult(StrictModel):
    outcome: Literal["accepted", "refused"]
    expression: "MeaningExpressionV0 | None" = None
    refusal: BridgeRefusal | None = None


class VocabularyGateError(ValueError):
    """Raised by require_* helpers when a meaning expression is not expressible."""

    def __init__(self, refusal: BridgeRefusal) -> None:
        super().__init__(refusal.message)
        self.refusal = refusal


class MeaningParameter(StrictModel):
    name: str = Field(min_length=1)
    value: Any
    unit: str = "none"


class OperatorApplication(StrictModel):
    operator: str = Field(min_length=1)
    input_field: str | None = None
    output_field: str | None = None
    parameters: list[MeaningParameter] = Field(default_factory=list)


class PopulationScope(StrictModel):
    match_ids: list[str] = Field(default_factory=list)
    periods: list[str] = Field(default_factory=lambda: ["firstHalf", "secondHalf"])
    perspective_team_roles: list[Literal["home", "away"]] = Field(default_factory=lambda: ["home"])


class TeamPerspectiveDeclaration(StrictModel):
    required: bool = False
    team_role_field: str | None = None
    same_team_enforced: bool = False
    statement: str = ""


class StatusSemantic(StrictModel):
    field: str
    required_value: str | None = None
    operator: str | None = None
    threshold: float | None = None
    unit: str | None = None


class TargetContract(StrictModel):
    desired_output: str = "classification"
    required_evidence: list[str] = Field(default_factory=list)
    required_modalities: list[str] = Field(default_factory=list)
    status_semantics: list[StatusSemantic] = Field(default_factory=list)
    composition_constraints: list[dict[str, Any]] = Field(default_factory=list)
    claim_boundary: str = Field(min_length=1)


class TargetSynthesisDeclaration(StrictModel):
    target_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    held_out: bool = True
    multi_step: bool = False


class MeaningExpressionV0(StrictModel):
    schema_version: Literal["meaning_expression.v0"] = "meaning_expression.v0"
    expression_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    expression_version: str = "0.1.0"
    concept_identity: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str = Field(min_length=1)
    meaning: str = Field(min_length=1)
    concept_refs: list[str] = Field(default_factory=list)
    operator_applications: list[OperatorApplication] = Field(default_factory=list)
    population: PopulationScope = Field(default_factory=PopulationScope)
    group_by: list[str] = Field(default_factory=list)
    team_perspective: TeamPerspectiveDeclaration = Field(default_factory=TeamPerspectiveDeclaration)
    target: TargetSynthesisDeclaration
    target_contract: TargetContract
    correspondence: dict[str, Any] = Field(default_factory=dict)
    fixture_notes: list[str] = Field(default_factory=list)

    def canonical_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    def document_hash(self) -> str:
        return stable_hash(self.canonical_payload())


@dataclass(frozen=True)
class PackVocabulary:
    primitive_names: frozenset[str]
    relation_names: frozenset[str]
    operator_names: frozenset[str]
    gap_codes: frozenset[str]
    field_names: frozenset[str]
    parameter_names: frozenset[str]
    pack_sha256: str
    pack_path: Path

    @property
    def concept_names(self) -> frozenset[str]:
        return self.primitive_names | self.relation_names

    def gap_code_for_missing(self, reference: str) -> str:
        normalized = _normalize_token(reference)
        aliases: dict[str, str] = {}
        for code in self.gap_codes:
            aliases[_normalize_token(code)] = code
        if "body_orientation" in normalized:
            aliases.setdefault("body_orientation", "BODY_ORIENTATION")
        if "body_shape" in normalized:
            aliases.setdefault("body_shape", "BODY_SHAPE")
        if "scan" in normalized or "head_check" in normalized:
            aliases.setdefault("scan", "SCANNING")
        if "intent" in normalized:
            aliases.setdefault("intent", "PLAYER_INTENT")
        if "pass_probability" in normalized:
            aliases.setdefault("pass_probability", "PASS_PROBABILITY")
        if "optimal" in normalized:
            aliases.setdefault("optimal", "OPTIMALITY")
        for alias, code in sorted(aliases.items(), key=lambda item: (-len(item[0]), item[0])):
            if alias and alias in normalized and code in self.gap_codes:
                return code
        return "PRIMITIVE_MUTATION" if "PRIMITIVE_MUTATION" in self.gap_codes else sorted(self.gap_codes)[0]


def load_pack_vocabulary(path: Path = DEFAULT_KNOWLEDGE_PACK_PATH) -> PackVocabulary:
    payload = json.loads(path.read_text(encoding="utf-8"))
    primitives = payload.get("primitives") or []
    operators = payload.get("operators") or []
    gap_codes = payload.get("capability_gap_codes") or []
    if len(primitives) != EXPECTED_PRIMITIVE_COUNT:
        raise ValueError(f"knowledge pack primitive count drifted: {len(primitives)}")
    if len(operators) != EXPECTED_OPERATOR_COUNT:
        raise ValueError(f"knowledge pack operator count drifted: {len(operators)}")
    if len(gap_codes) != EXPECTED_GAP_CODE_COUNT:
        raise ValueError(f"knowledge pack gap-code count drifted: {len(gap_codes)}")

    relations = payload.get("relations") or []
    primitive_names = frozenset(str(item["name"]) for item in primitives)
    relation_names = frozenset(str(item["name"]) for item in relations)
    operator_names = frozenset(str(item["name"]) for item in operators)
    code_names = frozenset(str(item["code"]) for item in gap_codes)
    field_names: set[str] = set()
    parameter_names: set[str] = set()
    for bucket, values in (payload.get("evidence_fields") or {}).items():
        field_names.add(str(bucket))
        field_names.update(str(value) for value in values)
    for item in [*primitives, *relations]:
        for field in item.get("evidence_fields") or []:
            field_names.add(str(field))
        for output in item.get("outputs") or []:
            field_names.add(str(output.get("name")))
            field_names.update(str(field) for field in output.get("evidence_fields") or [])
        for parameter in item.get("parameters") or []:
            parameter_names.add(str(parameter["name"]))
    for operator in operators:
        if operator.get("compare_required"):
            parameter_names.add("compare")
            parameter_names.add("threshold")
        if operator.get("duration_required"):
            parameter_names.add("duration")
        parameter_names.add("input_field")
        parameter_names.add("output_field")
        parameter_names.add("unit")
        parameter_names.add("required_value")

    return PackVocabulary(
        primitive_names=primitive_names,
        relation_names=relation_names,
        operator_names=operator_names,
        gap_codes=code_names,
        field_names=frozenset(field_names),
        parameter_names=frozenset(parameter_names),
        pack_sha256=str(payload["knowledge_pack_sha256"]),
        pack_path=path,
    )


def load_meaning_expression_result(
    payload: dict[str, Any] | str,
    *,
    vocabulary: PackVocabulary | None = None,
) -> MeaningLoadResult:
    vocab = vocabulary or load_pack_vocabulary()
    raw = json.loads(payload) if isinstance(payload, str) else payload
    expression = MeaningExpressionV0.model_validate(raw)
    refusal = first_vocabulary_refusal(expression, vocab)
    if refusal is not None:
        return MeaningLoadResult(outcome="refused", refusal=refusal)
    return MeaningLoadResult(outcome="accepted", expression=expression)


def load_meaning_expression_from_path(
    path: Path,
    *,
    vocabulary: PackVocabulary | None = None,
) -> MeaningLoadResult:
    return load_meaning_expression_result(path.read_text(encoding="utf-8"), vocabulary=vocabulary)


def require_meaning_expression(
    payload: dict[str, Any] | str,
    *,
    vocabulary: PackVocabulary | None = None,
) -> MeaningExpressionV0:
    result = load_meaning_expression_result(payload, vocabulary=vocabulary)
    if result.refusal is not None:
        raise VocabularyGateError(result.refusal)
    assert result.expression is not None
    return result.expression


def first_vocabulary_refusal(
    expression: MeaningExpressionV0,
    vocabulary: PackVocabulary,
) -> BridgeRefusal | None:
    for ref in expression.concept_refs:
        if ref not in vocabulary.concept_names:
            return _refusal(vocabulary, "concept_refs", ref, f"concept:{ref}")
    for application in expression.operator_applications:
        if application.operator not in vocabulary.operator_names:
            return _refusal(
                vocabulary,
                "operator_applications.operator",
                application.operator,
                f"operator:{application.operator}",
            )
        for field in (application.input_field, application.output_field):
            if field and field not in vocabulary.field_names:
                return _refusal(vocabulary, "operator_applications.field", field, f"field:{field}")
        for parameter in application.parameters:
            if parameter.name not in vocabulary.parameter_names:
                return _refusal(
                    vocabulary,
                    "operator_applications.parameters",
                    parameter.name,
                    f"parameter:{parameter.name}",
                )
    for field in expression.group_by:
        if field not in vocabulary.field_names:
            return _refusal(vocabulary, "group_by", field, f"field:{field}")
    if expression.team_perspective.team_role_field:
        field = expression.team_perspective.team_role_field
        if field not in vocabulary.field_names:
            return _refusal(vocabulary, "team_perspective.team_role_field", field, f"field:{field}")
    for field in expression.target_contract.required_evidence:
        if field not in vocabulary.field_names:
            return _refusal(vocabulary, "target_contract.required_evidence", field, f"field:{field}")
    for modality in expression.target_contract.required_modalities:
        if modality not in {"tracking", "events", "tracking_event_synchronized"}:
            return BridgeRefusal(
                outcome=BridgeRefusalKind.UNSUPPORTED_MODALITY,
                gap_code="VIDEO" if "VIDEO" in vocabulary.gap_codes else vocabulary.gap_code_for_missing(modality),
                missing_capability=f"modality:{modality}",
                reference=modality,
                vocabulary_section="target_contract.required_modalities",
                message=f"Unsupported modality: {modality}",
                pack_sha256=vocabulary.pack_sha256,
            )
    for item in expression.target_contract.status_semantics:
        if item.field not in vocabulary.field_names:
            return _refusal(vocabulary, "target_contract.status_semantics.field", item.field, f"field:{item.field}")
        if item.operator and item.operator not in vocabulary.operator_names:
            return _refusal(
                vocabulary,
                "target_contract.status_semantics.operator",
                item.operator,
                f"operator:{item.operator}",
            )
    for constraint in expression.target_contract.composition_constraints:
        refusal = _constraint_refusal(constraint, vocabulary)
        if refusal is not None:
            return refusal
    return None


def stable_expression_json(expression: MeaningExpressionV0) -> str:
    return json.dumps(expression.canonical_payload(), indent=2, sort_keys=True) + "\n"


def _constraint_refusal(constraint: dict[str, Any], vocabulary: PackVocabulary) -> BridgeRefusal | None:
    for key, value in sorted(constraint.items()):
        if key.endswith("_field") and isinstance(value, str) and value != "none":
            if value not in vocabulary.field_names:
                return _refusal(vocabulary, f"composition_constraints.{key}", value, f"field:{value}")
        if key.endswith("_fields") and isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item != "none" and item not in vocabulary.field_names:
                    return _refusal(vocabulary, f"composition_constraints.{key}", item, f"field:{item}")
        if key in vocabulary.parameter_names:
            continue
    return None


def _refusal(
    vocabulary: PackVocabulary,
    section: str,
    reference: str,
    missing_capability: str,
) -> BridgeRefusal:
    gap_code = vocabulary.gap_code_for_missing(reference)
    return BridgeRefusal(
        outcome=BridgeRefusalKind.UNDERSTOOD_BUT_NOT_EXPRESSIBLE,
        gap_code=gap_code,
        missing_capability=missing_capability,
        reference=reference,
        vocabulary_section=section,
        message=(
            f"Meaning expression references out-of-pack {missing_capability}; "
            f"smallest missing capability is {missing_capability}."
        ),
        pack_sha256=vocabulary.pack_sha256,
    )


def _normalize_token(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "_" for char in value)
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_")
