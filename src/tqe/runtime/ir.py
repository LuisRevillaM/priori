"""Typed Tactical Query IR v1.

These Pydantic models are the authoritative schema source for M1.1 Gate A.
The generic executor arrives in later gates; this module only defines the
objects that can be validated and bound.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


JsonDict = dict[str, Any]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TemporalContainer(StrEnum):
    SCALAR = "scalar"
    FRAME_SIGNAL = "frame_signal"
    EPISODE_SET = "episode_set"
    RELATION_EPISODE_SET = "relation_episode_set"


class PayloadType(StrEnum):
    BOOLEAN = "boolean"
    NUMBER = "number"
    ENUM = "enum"
    ANCHOR_REF = "anchor_ref"
    ENTITY_REF = "entity_ref"
    TEAM_REF = "team_ref"
    REGION_REF = "region_ref"
    POINT = "point"
    ENTITY_SET = "entity_set"
    RELATION_REF = "relation_ref"


class Cardinality(StrEnum):
    SINGLE = "single"
    PER_PLAYER = "per_player"
    PER_TEAM = "per_team"
    COLLECTION = "collection"


class Unit(StrEnum):
    NONE = "none"
    METRE = "metre"
    SECOND = "second"
    MILLISECOND = "millisecond"
    FRAME = "frame"
    FRACTION = "fraction"
    HERTZ = "hertz"
    COUNT = "count"


class EntityScope(StrEnum):
    NONE = "none"
    ANCHOR = "anchor"
    BALL = "ball"
    PLAYER = "player"
    TEAM = "team"
    MATCH = "match"
    POSSESSION = "possession"
    FRAME = "frame"
    RELATION = "relation"


class MissingDataSemantics(StrEnum):
    UNKNOWN = "unknown"
    QUALITY_FAIL = "quality_fail"
    NOT_APPLICABLE = "not_applicable"


class UnknownEvidencePolicy(StrEnum):
    EXCLUDE_CANDIDATE = "exclude_candidate"
    INCLUDE_WITH_WARNING = "include_with_warning"
    INVALIDATE_EXECUTION = "invalidate_execution"


class NodeKind(StrEnum):
    PRIMITIVE = "primitive"
    RELATION = "relation"
    PREDICATE = "predicate"


class ExecutionMode(StrEnum):
    BIND_ONLY = "bind_only"
    DRY_RUN = "dry_run"
    EXECUTE = "execute"


class PlanStatus(StrEnum):
    APPROVED = "approved"
    EXPERIMENTAL = "experimental"


class ClassificationMode(StrEnum):
    EXHAUSTIVE = "exhaustive"
    PARTIAL_DECLARED = "partial_declared"


class ExecutionStatus(StrEnum):
    NOT_STARTED = "not_started"
    PASS = "pass"
    FAIL = "fail"
    INCOMPLETE = "incomplete"


class BindIssue(StrictModel):
    code: str
    message: str
    path: str


class TypedValue(StrictModel):
    payload_type: PayloadType
    value: Any
    unit: Unit = Unit.NONE

    @model_validator(mode="after")
    def validate_value_shape(self) -> "TypedValue":
        if self.payload_type == PayloadType.BOOLEAN and not isinstance(self.value, bool):
            raise ValueError("boolean typed values must contain a bool")
        if self.payload_type == PayloadType.NUMBER:
            if isinstance(self.value, bool) or not isinstance(self.value, int | float):
                raise ValueError("number typed values must contain an int or float")
        if self.payload_type in {
            PayloadType.ENUM,
            PayloadType.ANCHOR_REF,
            PayloadType.ENTITY_REF,
            PayloadType.TEAM_REF,
            PayloadType.REGION_REF,
            PayloadType.RELATION_REF,
        } and not isinstance(self.value, str):
            raise ValueError(f"{self.payload_type.value} typed values must contain a string")
        if self.payload_type == PayloadType.POINT:
            if (
                not isinstance(self.value, dict)
                or set(self.value) != {"x_m", "y_m"}
                or not all(isinstance(self.value[key], int | float) for key in ("x_m", "y_m"))
            ):
                raise ValueError("point typed values must contain numeric x_m and y_m")
        if self.payload_type == PayloadType.ENTITY_SET:
            if not isinstance(self.value, list) or not all(isinstance(item, str) for item in self.value):
                raise ValueError("entity_set typed values must contain a string list")
        if self.payload_type != PayloadType.NUMBER and self.unit not in {Unit.NONE, Unit.COUNT}:
            raise ValueError("only number values can carry physical units")
        return self


class ParameterDefinition(StrictModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    payload_type: PayloadType
    unit: Unit = Unit.NONE
    required: bool = False
    default: TypedValue | None = None
    minimum: float | None = None
    maximum: float | None = None
    allowed_values: list[str] | None = None
    description: str

    @model_validator(mode="after")
    def validate_default_matches_definition(self) -> "ParameterDefinition":
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("parameter minimum cannot exceed maximum")
        if self.allowed_values is not None and self.payload_type != PayloadType.ENUM:
            raise ValueError("allowed_values can only be declared for enum parameters")
        if self.default is None:
            if not self.required:
                raise ValueError("non-required parameters must declare a default")
            return self
        if self.default.payload_type != self.payload_type:
            raise ValueError("parameter default payload_type must match definition")
        if self.default.unit != self.unit:
            raise ValueError("parameter default unit must match definition")
        if self.default.payload_type == PayloadType.NUMBER:
            numeric = float(self.default.value)
            if self.minimum is not None and numeric < self.minimum:
                raise ValueError("parameter default is below minimum")
            if self.maximum is not None and numeric > self.maximum:
                raise ValueError("parameter default is above maximum")
        if self.allowed_values is not None and str(self.default.value) not in set(self.allowed_values):
            raise ValueError("parameter default is not in allowed_values")
        return self


class QueryInvocation(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    invocation_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    match_ids: list[str] = Field(min_length=1)
    periods: list[Literal["firstHalf", "secondHalf"]] = Field(min_length=1)
    perspective_team_role: Literal["home", "away"]
    parameters: dict[str, TypedValue] = Field(default_factory=dict)
    max_results: int = Field(ge=1, le=500)
    execution_mode: ExecutionMode = ExecutionMode.BIND_ONLY

    @field_validator("match_ids")
    @classmethod
    def unique_match_ids(cls, match_ids: list[str]) -> list[str]:
        if len(set(match_ids)) != len(match_ids):
            raise ValueError("match_ids must be unique")
        return match_ids


class EvaluationTarget(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    target_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    match_id: str
    period: Literal["firstHalf", "secondHalf"]
    approximate_time_ms: int = Field(ge=0)
    search_radius_ms: int = Field(gt=0)


class SignalRef(StrictModel):
    source_node_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    output_name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")


class OperatorRef(StrictModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    version: str


class ParameterRef(StrictModel):
    kind: Literal["parameter"] = "parameter"
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")


TypedArgument = Annotated[TypedValue | ParameterRef, Field(union_mode="left_to_right")]


class EvidenceRequest(StrictModel):
    source: SignalRef
    field: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    alias: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$")


class DraftCatalogNode(StrictModel):
    kind: Literal[NodeKind.PRIMITIVE, NodeKind.RELATION]
    node_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    catalog_ref: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    version: str
    inputs: dict[str, SignalRef] = Field(default_factory=dict)
    parameters: dict[str, TypedArgument] = Field(default_factory=dict)


class DraftPredicateNode(StrictModel):
    kind: Literal[NodeKind.PREDICATE] = NodeKind.PREDICATE
    node_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    input: SignalRef
    operator: OperatorRef
    compare: TypedArgument | None = None
    duration: TypedArgument | None = None
    required_cardinality: Cardinality | None = None
    required_entity_scope: EntityScope | None = None


DraftPlanNode = Annotated[DraftCatalogNode | DraftPredicateNode, Field(discriminator="kind")]


class ClassificationRule(StrictModel):
    label: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    predicate_ids: list[str] = Field(min_length=1)
    description: str


class ComplexityLimits(StrictModel):
    max_plan_nodes: int = Field(default=40, ge=1)
    max_nesting_depth: int = Field(default=8, ge=1)
    max_temporal_horizon_seconds: float = Field(default=15.0, gt=0)
    max_returned_moments: int = Field(default=100, ge=1)
    max_relations_per_anchor: int = Field(default=1000, ge=1)
    max_execution_cost: int = Field(default=100000, ge=1)


class DraftQueryPlan(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    plan_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    plan_version: str
    recipe_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    recipe_version: str
    status: PlanStatus
    unknown_evidence_policy: UnknownEvidencePolicy
    classification_mode: ClassificationMode
    nodes: list[DraftPlanNode] = Field(min_length=1)
    classification_rules: list[ClassificationRule] = Field(min_length=1)
    anchor_source: SignalRef | None = None
    requested_evidence: list[EvidenceRequest] = Field(default_factory=list)
    complexity_limits: ComplexityLimits = Field(default_factory=ComplexityLimits)

    @field_validator("nodes")
    @classmethod
    def node_ids_are_unique(cls, nodes: list[DraftPlanNode]) -> list[DraftPlanNode]:
        node_ids = [node.node_id for node in nodes]
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("node_ids must be unique")
        return nodes


class RecipeDefinition(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    recipe_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    recipe_version: str
    display_name: str
    description: str
    parameters: list[ParameterDefinition] = Field(default_factory=list)
    default_unknown_evidence_policy: UnknownEvidencePolicy
    allowed_claims: list[str] = Field(default_factory=list)
    disallowed_claims: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    output_classifications: list[str] = Field(min_length=1)

    @field_validator("parameters")
    @classmethod
    def parameter_names_are_unique(
        cls, parameters: list[ParameterDefinition]
    ) -> list[ParameterDefinition]:
        names = [parameter.name for parameter in parameters]
        if len(set(names)) != len(names):
            raise ValueError("parameter names must be unique")
        return parameters


class TacticalQueryDocument(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    recipe: RecipeDefinition
    default_invocation: QueryInvocation
    draft_plan: DraftQueryPlan


class CatalogInput(StrictModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    temporal_type: TemporalContainer
    payload_type: PayloadType
    cardinality: Cardinality
    unit: Unit = Unit.NONE
    entity_scope: EntityScope = EntityScope.NONE
    required: bool = True


class CatalogOutput(StrictModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    temporal_type: TemporalContainer
    payload_type: PayloadType
    cardinality: Cardinality
    unit: Unit = Unit.NONE
    entity_scope: EntityScope = EntityScope.NONE
    missing_data_semantics: MissingDataSemantics
    evidence_fields: list[str] = Field(default_factory=list)


class CatalogEntry(StrictModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    version: str
    kind: Literal[NodeKind.PRIMITIVE, NodeKind.RELATION]
    purpose: str
    inputs: list[CatalogInput] = Field(default_factory=list)
    outputs: list[CatalogOutput] = Field(min_length=1)
    parameters: list[ParameterDefinition] = Field(default_factory=list)
    executable: bool = True
    limitations: list[str] = Field(default_factory=list)
    missing_data_semantics: MissingDataSemantics
    evidence_fields: list[str] = Field(default_factory=list)

    @field_validator("inputs")
    @classmethod
    def input_names_are_unique(cls, inputs: list[CatalogInput]) -> list[CatalogInput]:
        names = [item.name for item in inputs]
        if len(set(names)) != len(names):
            raise ValueError("catalog input names must be unique")
        return inputs

    @field_validator("outputs")
    @classmethod
    def output_names_are_unique(cls, outputs: list[CatalogOutput]) -> list[CatalogOutput]:
        names = [item.name for item in outputs]
        if len(set(names)) != len(names):
            raise ValueError("catalog output names must be unique")
        return outputs

    @field_validator("parameters")
    @classmethod
    def catalog_parameter_names_are_unique(
        cls, parameters: list[ParameterDefinition]
    ) -> list[ParameterDefinition]:
        names = [parameter.name for parameter in parameters]
        if len(set(names)) != len(names):
            raise ValueError("catalog parameter names must be unique")
        return parameters


class OperatorSignature(StrictModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    version: str
    purpose: str
    input_temporal_types: list[TemporalContainer] = Field(min_length=1)
    input_payload_types: list[PayloadType] = Field(min_length=1)
    input_cardinalities: list[Cardinality] = Field(min_length=1)
    compare_payload_types: list[PayloadType] = Field(default_factory=list)
    compare_required: bool = False
    compare_unit_must_match: bool = False
    duration_required: bool = False
    output_temporal_type: TemporalContainer
    output_payload_type: PayloadType
    output_cardinality: Cardinality
    output_unit: Unit = Unit.NONE
    limitations: list[str] = Field(default_factory=list)


class CapabilityCatalog(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    primitives: list[CatalogEntry] = Field(default_factory=list)
    relations: list[CatalogEntry] = Field(default_factory=list)
    operators: list[OperatorSignature] = Field(default_factory=list)
    default_complexity_limits: ComplexityLimits = Field(default_factory=ComplexityLimits)


class ResolvedParameter(StrictModel):
    name: str
    value: TypedValue
    source: Literal["invocation", "default"]


class BoundCatalogNode(StrictModel):
    kind: Literal[NodeKind.PRIMITIVE, NodeKind.RELATION]
    node_id: str
    catalog_ref: str
    version: str
    inputs: dict[str, SignalRef] = Field(default_factory=dict)
    input_types: dict[str, CatalogOutput] = Field(default_factory=dict)
    outputs: list[CatalogOutput]
    resolved_parameters: dict[str, TypedValue] = Field(default_factory=dict)


class BoundPredicateNode(StrictModel):
    kind: Literal[NodeKind.PREDICATE] = NodeKind.PREDICATE
    node_id: str
    input: SignalRef
    input_type: CatalogOutput
    operator: OperatorRef
    operator_signature: OperatorSignature
    compare: TypedValue | None = None
    duration: TypedValue | None = None
    output: CatalogOutput


BoundPlanNode = Annotated[BoundCatalogNode | BoundPredicateNode, Field(discriminator="kind")]


class BoundQueryPlan(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    plan_id: str
    plan_version: str
    plan_status: PlanStatus
    recipe_id: str
    recipe_version: str
    invocation_id: str
    match_ids: list[str]
    periods: list[Literal["firstHalf", "secondHalf"]]
    perspective_team_role: Literal["home", "away"]
    max_results: int
    execution_mode: ExecutionMode
    unknown_evidence_policy: UnknownEvidencePolicy
    classification_mode: ClassificationMode
    classification_rules: list[ClassificationRule]
    anchor_source: SignalRef | None = None
    requested_evidence: list[EvidenceRequest]
    complexity_limits: ComplexityLimits
    resolved_parameters: list[ResolvedParameter]
    nodes: list[BoundPlanNode]
    plan_hash: str
    bound_plan_hash: str


class QueryResult(StrictModel):
    result_id: str
    classification: str
    match_id: str
    period: Literal["firstHalf", "secondHalf"]
    anchor_frame_id: int
    evidence: JsonDict = Field(default_factory=dict)


class PredicateTrace(StrictModel):
    predicate_id: str
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    value: TypedValue | None = None
    threshold: TypedValue | None = None
    unit: Unit = Unit.NONE
    frame_id: int | None = None
    window: JsonDict | None = None
    source_evidence: JsonDict = Field(default_factory=dict)


class QueryExecution(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    execution_id: str
    status: ExecutionStatus
    plan_hash: str
    bound_plan_hash: str
    results: list[QueryResult] = Field(default_factory=list)
    predicate_traces: list[PredicateTrace] = Field(default_factory=list)
    provenance: JsonDict = Field(default_factory=dict)
    timing_ms: JsonDict = Field(default_factory=dict)


class TacticalQuerySchemaBundle(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    recipe_definition: RecipeDefinition
    query_invocation: QueryInvocation
    evaluation_target: EvaluationTarget
    draft_query_plan: DraftQueryPlan
    bound_query_plan: BoundQueryPlan
    query_execution: QueryExecution


def canonical_json(payload: Any) -> str:
    return json.dumps(_json_ready(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def model_payload(model: BaseModel) -> JsonDict:
    return model.model_dump(mode="json", exclude_none=True)


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _json_ready(payload: Any) -> Any:
    if isinstance(payload, BaseModel):
        return model_payload(payload)
    if isinstance(payload, dict):
        return {str(key): _json_ready(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_json_ready(value) for value in payload]
    if isinstance(payload, tuple):
        return [_json_ready(value) for value in payload]
    return payload
