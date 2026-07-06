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
MeaningValue = str | int | float | bool | list[str]


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


class MissingGapCodeError(RuntimeError):
    """Raised when the pack has no truthful gap code for a failed vocabulary family."""


class MeaningParameter(StrictModel):
    name: str = Field(min_length=1)
    value: MeaningValue
    unit: str = "none"


class OperatorApplication(StrictModel):
    operator: str = Field(min_length=1)
    parameters: list[MeaningParameter] = Field(default_factory=list)


class MeaningClause(StrictModel):
    subject: str = Field(min_length=1)
    action: str = Field(min_length=1)
    field: str | None = None
    operator: str | None = None
    value: MeaningValue | None = None
    unit: str | None = None
    frame_scope: str | None = None


class CorrespondenceClause(StrictModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    value: MeaningValue


class CompositionConstraint(StrictModel):
    kind: str = Field(min_length=1)
    parameters: list[MeaningParameter] = Field(default_factory=list)
    left_input_context: list[MeaningParameter] = Field(default_factory=list)
    right_input_context: list[MeaningParameter] = Field(default_factory=list)
    left_composition_constraints: list["CompositionConstraint"] = Field(default_factory=list)
    right_composition_constraints: list["CompositionConstraint"] = Field(default_factory=list)
    population_composition_constraints: list["CompositionConstraint"] = Field(default_factory=list)
    numerator_composition_constraints: list["CompositionConstraint"] = Field(default_factory=list)
    denominator_composition_constraints: list["CompositionConstraint"] = Field(default_factory=list)


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
    composition_constraints: list[CompositionConstraint] = Field(default_factory=list)
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
    meaning_clauses: list[MeaningClause] = Field(min_length=1)
    concept_refs: list[str] = Field(default_factory=list)
    operator_applications: list[OperatorApplication] = Field(default_factory=list)
    population: PopulationScope = Field(default_factory=PopulationScope)
    group_by: list[str] = Field(default_factory=list)
    team_perspective: TeamPerspectiveDeclaration = Field(default_factory=TeamPerspectiveDeclaration)
    target: TargetSynthesisDeclaration
    target_contract: TargetContract
    correspondence_clauses: list[CorrespondenceClause] = Field(default_factory=list)
    fixture_notes: list[str] = Field(default_factory=list)

    def canonical_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    def document_hash(self) -> str:
        return stable_hash(self.canonical_payload())


@dataclass(frozen=True)
class PackVocabulary:
    primitive_names: frozenset[str]
    relation_names: frozenset[str]
    predicate_operator_names: frozenset[str]
    composition_operator_names: frozenset[str]
    constraint_kind_parameters: dict[str, frozenset[str]]
    gap_codes: frozenset[str]
    field_names: frozenset[str]
    parameter_names: frozenset[str]
    pack_sha256: str
    pack_path: Path

    @property
    def concept_names(self) -> frozenset[str]:
        return self.primitive_names | self.relation_names

    @property
    def operator_names(self) -> frozenset[str]:
        return self.predicate_operator_names | self.composition_operator_names

    @property
    def constraint_kinds(self) -> frozenset[str]:
        return frozenset(self.constraint_kind_parameters)

    def gap_code_for_missing(self, reference: str) -> str | None:
        normalized = _normalize_token(reference)
        aliases: dict[str, str] = {}
        for code in self.gap_codes:
            aliases[_normalize_token(code)] = code
        for alias, code in sorted(aliases.items(), key=lambda item: (-len(item[0]), item[0])):
            if alias and alias in normalized and code in self.gap_codes:
                return code
        return None


def load_pack_vocabulary(path: Path = DEFAULT_KNOWLEDGE_PACK_PATH) -> PackVocabulary:
    payload = json.loads(path.read_text(encoding="utf-8"))
    primitives = payload.get("primitives") or []
    predicate_operators = payload.get("operators") or []
    gap_codes = payload.get("capability_gap_codes") or []
    relations = payload.get("relations") or []
    grammar = payload.get("composition_grammar") or {}
    composition_operators = grammar.get("operators") or []
    constraint_kinds = grammar.get("constraint_kinds") or []
    if not primitives or not predicate_operators or not gap_codes:
        raise ValueError("knowledge pack is missing primitive/operator/gap vocabulary")
    if not composition_operators or not constraint_kinds:
        raise ValueError("knowledge pack is missing composition_grammar vocabulary")

    primitive_names = frozenset(str(item["name"]) for item in primitives)
    relation_names = frozenset(str(item["name"]) for item in relations)
    predicate_operator_names = frozenset(str(item["name"]) for item in predicate_operators)
    composition_operator_names = frozenset(str(item["name"]) for item in composition_operators)
    code_names = frozenset(str(item["code"]) for item in gap_codes)
    field_names: set[str] = set()
    parameter_names: set[str] = set()
    constraint_kind_parameters: dict[str, frozenset[str]] = {}
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
    for operator in predicate_operators:
        if operator.get("compare_required"):
            parameter_names.add("compare")
            parameter_names.add("threshold")
        if operator.get("duration_required"):
            parameter_names.add("duration")
        parameter_names.add("input_field")
        parameter_names.add("output_field")
        parameter_names.add("unit")
        parameter_names.add("required_value")
    for operator in composition_operators:
        for output in operator.get("outputs") or []:
            field_names.add(str(output.get("name")))
            field_names.update(str(field) for field in output.get("evidence_fields") or [])
        for parameter in operator.get("parameters") or []:
            parameter_names.add(str(parameter["name"]))
    for item in constraint_kinds:
        kind = str(item["kind"])
        parameters = frozenset(str(parameter) for parameter in item.get("parameters") or [])
        if not parameters:
            raise ValueError(f"composition constraint kind {kind} has no parameter schema")
        constraint_kind_parameters[kind] = parameters
        parameter_names.update(parameters)

    return PackVocabulary(
        primitive_names=primitive_names,
        relation_names=relation_names,
        predicate_operator_names=predicate_operator_names,
        composition_operator_names=composition_operator_names,
        constraint_kind_parameters=constraint_kind_parameters,
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
    refusal = first_numeric_clause_parameter_refusal(expression, vocabulary)
    if refusal is not None:
        return refusal
    for ref in expression.concept_refs:
        if ref not in vocabulary.concept_names:
            return _refusal(vocabulary, "concept_refs", ref, f"concept:{ref}")
    for application in expression.operator_applications:
        if application.operator not in vocabulary.composition_operator_names:
            return _refusal(
                vocabulary,
                "operator_applications.operator",
                application.operator,
                f"operator:{application.operator}",
            )
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
        if item.operator and item.operator not in vocabulary.predicate_operator_names:
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


def first_numeric_clause_parameter_refusal(
    expression: MeaningExpressionV0,
    vocabulary: PackVocabulary,
) -> BridgeRefusal | None:
    parameter_values = _numeric_parameter_values_by_field(expression)
    for index, clause in enumerate(expression.meaning_clauses):
        if clause.field is None or clause.value is None:
            continue
        if isinstance(clause.value, bool) or not isinstance(clause.value, (int, float)):
            continue
        declarations = parameter_values.get(clause.field)
        if not declarations:
            continue
        clause_value = float(clause.value)
        for declaration in declarations:
            if float(declaration["value"]) == clause_value:
                continue
            return BridgeRefusal(
                outcome=BridgeRefusalKind.UNDERSTOOD_BUT_NOT_EXPRESSIBLE,
                gap_code="MEANING_PARAMETER_MISMATCH",
                missing_capability="numeric_clause_parameter_consistency",
                reference=f"{clause.field}:{clause_value}!={float(declaration['value'])}",
                vocabulary_section=f"meaning_clauses[{index}]",
                message=(
                    "Numeric meaning clause disagrees with the executable operator parameter: "
                    f"{clause.field} clause value {clause_value} does not match "
                    f"{declaration['parameter_name']} value {float(declaration['value'])}."
                ),
                pack_sha256=vocabulary.pack_sha256,
            )
    return None


def _numeric_parameter_values_by_field(expression: MeaningExpressionV0) -> dict[str, list[dict[str, Any]]]:
    values: dict[str, list[dict[str, Any]]] = {}

    def add_parameters(parameters: list[MeaningParameter], *, path: str) -> None:
        by_name = {parameter.name: parameter for parameter in parameters}
        for parameter in parameters:
            if not parameter.name.endswith("_field"):
                continue
            if not isinstance(parameter.value, str) or parameter.value == "none":
                continue
            value_parameter_name = parameter.name[: -len("_field")] + "_value"
            value_parameter = by_name.get(value_parameter_name)
            if value_parameter is None:
                continue
            if isinstance(value_parameter.value, bool) or not isinstance(value_parameter.value, (int, float)):
                continue
            values.setdefault(parameter.value, []).append(
                {
                    "field_parameter_name": parameter.name,
                    "parameter_name": value_parameter.name,
                    "value": value_parameter.value,
                    "path": path,
                }
            )

    for index, application in enumerate(expression.operator_applications):
        add_parameters(application.parameters, path=f"operator_applications[{index}]")

    def walk_constraint(constraint: CompositionConstraint, *, path: str) -> None:
        add_parameters(constraint.parameters, path=path)
        nested_groups = (
            ("left_composition_constraints", constraint.left_composition_constraints),
            ("right_composition_constraints", constraint.right_composition_constraints),
            ("population_composition_constraints", constraint.population_composition_constraints),
            ("numerator_composition_constraints", constraint.numerator_composition_constraints),
            ("denominator_composition_constraints", constraint.denominator_composition_constraints),
        )
        for name, children in nested_groups:
            for child_index, child in enumerate(children):
                walk_constraint(child, path=f"{path}.{name}[{child_index}]")

    for index, constraint in enumerate(expression.target_contract.composition_constraints):
        walk_constraint(constraint, path=f"target_contract.composition_constraints[{index}]")
    return values


def stable_expression_json(expression: MeaningExpressionV0) -> str:
    return json.dumps(expression.canonical_payload(), indent=2, sort_keys=True) + "\n"


def render_meaning_sentence(expression: MeaningExpressionV0) -> str:
    return " ".join(_render_clause(clause) for clause in expression.meaning_clauses)


def search_constraint_payload(constraint: CompositionConstraint) -> dict[str, Any]:
    payload: dict[str, Any] = {"kind": constraint.kind}
    for parameter in constraint.parameters:
        payload[parameter.name] = parameter.value
    if constraint.left_composition_constraints:
        payload["left_composition_constraints"] = [
            search_constraint_payload(item) for item in constraint.left_composition_constraints
        ]
    if constraint.left_input_context:
        payload["left_input_context"] = {
            parameter.name: parameter.value for parameter in constraint.left_input_context
        }
    if constraint.right_composition_constraints:
        payload["right_composition_constraints"] = [
            search_constraint_payload(item) for item in constraint.right_composition_constraints
        ]
    if constraint.right_input_context:
        payload["right_input_context"] = {
            parameter.name: parameter.value for parameter in constraint.right_input_context
        }
    if constraint.population_composition_constraints:
        payload["population_composition_constraints"] = [
            search_constraint_payload(item) for item in constraint.population_composition_constraints
        ]
    if constraint.numerator_composition_constraints:
        payload["numerator_composition_constraints"] = [
            search_constraint_payload(item) for item in constraint.numerator_composition_constraints
        ]
    if constraint.denominator_composition_constraints:
        payload["denominator_composition_constraints"] = [
            search_constraint_payload(item) for item in constraint.denominator_composition_constraints
        ]
    return payload


def _constraint_refusal(
    constraint: CompositionConstraint,
    vocabulary: PackVocabulary,
    *,
    path: str = "composition_constraints",
) -> BridgeRefusal | None:
    if constraint.kind not in vocabulary.constraint_kinds:
        return _refusal(vocabulary, f"{path}.kind", constraint.kind, f"constraint_kind:{constraint.kind}")
    allowed_parameters = vocabulary.constraint_kind_parameters[constraint.kind]
    for parameter in constraint.parameters:
        if parameter.name not in allowed_parameters:
            return _refusal(vocabulary, f"{path}.{constraint.kind}.parameters", parameter.name, f"parameter:{parameter.name}")
        refusal = _parameter_value_refusal(
            parameter=parameter,
            vocabulary=vocabulary,
            path=f"{path}.{constraint.kind}.{parameter.name}",
        )
        if refusal is not None:
            return refusal
    nested_groups = [
        ("left_composition_constraints", constraint.left_composition_constraints),
        ("right_composition_constraints", constraint.right_composition_constraints),
        ("population_composition_constraints", constraint.population_composition_constraints),
        ("numerator_composition_constraints", constraint.numerator_composition_constraints),
        ("denominator_composition_constraints", constraint.denominator_composition_constraints),
    ]
    for name, nested in nested_groups:
        if nested and name not in allowed_parameters:
            return _refusal(vocabulary, f"{path}.{constraint.kind}", name, f"parameter:{name}")
        for index, item in enumerate(nested):
            refusal = _constraint_refusal(
                item,
                vocabulary,
                path=f"{path}.{constraint.kind}.{name}[{index}]",
            )
            if refusal is not None:
                return refusal
    for name, context_parameters in (
        ("left_input_context", constraint.left_input_context),
        ("right_input_context", constraint.right_input_context),
    ):
        if context_parameters and name not in allowed_parameters:
            return _refusal(vocabulary, f"{path}.{constraint.kind}", name, f"parameter:{name}")
        for parameter in context_parameters:
            if parameter.name not in vocabulary.parameter_names:
                return _refusal(vocabulary, f"{path}.{constraint.kind}.{name}", parameter.name, f"parameter:{parameter.name}")
            refusal = _parameter_value_refusal(
                parameter=parameter,
                vocabulary=vocabulary,
                path=f"{path}.{constraint.kind}.{name}.{parameter.name}",
            )
            if refusal is not None:
                return refusal
    return None


def _parameter_value_refusal(
    *,
    parameter: MeaningParameter,
    vocabulary: PackVocabulary,
    path: str,
) -> BridgeRefusal | None:
    value = parameter.value
    if parameter.name.endswith("_field") and isinstance(value, str) and value != "none":
        if value not in vocabulary.field_names:
            return _refusal(vocabulary, path, value, f"field:{value}")
    if parameter.name.endswith("_fields") and isinstance(value, list):
        for item in value:
            if item != "none" and item not in vocabulary.field_names:
                return _refusal(vocabulary, path, item, f"field:{item}")
    if parameter.name in {"status_fields", "value_fields", "left_required_fields", "right_required_fields", "population_required_fields", "numerator_required_fields", "denominator_required_fields"} and isinstance(value, list):
        for item in value:
            if item != "none" and item not in vocabulary.field_names:
                return _refusal(vocabulary, path, item, f"field:{item}")
    return None


def _refusal(
    vocabulary: PackVocabulary,
    section: str,
    reference: str,
    missing_capability: str,
) -> BridgeRefusal:
    gap_code = vocabulary.gap_code_for_missing(reference)
    if gap_code is None:
        raise MissingGapCodeError(
            f"No truthful generated gap code exists for {missing_capability} in {section}."
        )
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


def _render_clause(clause: MeaningClause) -> str:
    pieces = [clause.subject, clause.action]
    if clause.field is not None:
        pieces.append(clause.field)
    if clause.operator is not None:
        pieces.append(clause.operator)
    if clause.value is not None:
        if isinstance(clause.value, list):
            pieces.append("[" + ", ".join(clause.value) + "]")
        else:
            pieces.append(str(clause.value))
    if clause.unit is not None:
        pieces.append(clause.unit)
    if clause.frame_scope is not None:
        pieces.append(clause.frame_scope)
    return " ".join(pieces).strip() + "."


def _normalize_token(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "_" for char in value)
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_")
