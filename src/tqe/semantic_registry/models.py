"""Pydantic models for the SCP-0 semantic registry.

The registry is a shadow semantic-control-plane layer. It describes meaning,
claims, evidence, maturity, exposure, and runtime bindings, while the existing
runtime catalog remains authoritative for executable availability.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ObjectKind(StrEnum):
    CONCEPT = "Concept"
    OPERATIONALIZATION = "Operationalization"
    DEFINITION_PROFILE = "DefinitionProfile"
    IMPLEMENTATION = "Implementation"
    RUNTIME_BINDING = "RuntimeBinding"
    OPERATOR_DEFINITION = "OperatorDefinition"
    RECIPE_DEFINITION = "RecipeDefinition"
    PLAN_ARTIFACT = "PlanArtifact"
    COMPOSITION_INSTANCE = "CompositionInstance"
    EXECUTION_RECORD = "ExecutionRecord"
    CLAIM_CONTRACT = "ClaimContract"
    EVIDENCE_CONTRACT = "EvidenceContract"
    EXPOSURE_POLICY = "ExposurePolicy"
    PROJECTION_POLICY = "ProjectionPolicy"
    MATURITY_ASSESSMENT = "MaturityAssessment"
    ATLAS_ENTRY = "AtlasEntry"


class Status(StrEnum):
    CURRENT = "CURRENT"
    PROPOSED_ATLAS = "PROPOSED_ATLAS"
    DEPRECATED = "DEPRECATED"
    SHADOW = "SHADOW"


class SemanticBasis(StrEnum):
    OBSERVED = "OBSERVED"
    DETERMINISTIC = "DETERMINISTIC"
    INFERRED_CANDIDATE = "INFERRED_CANDIDATE"
    MODELLED = "MODELLED"
    EVIDENCE = "EVIDENCE"


class AuthoringExposure(StrEnum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"
    REVIEWED_PLAN_ONLY = "REVIEWED_PLAN_ONLY"


class ProjectionTarget(StrEnum):
    PRODUCT = "product"
    AI = "ai"
    RECIPE_LIBRARY = "recipe_library"
    UNSUPPORTED = "unsupported"
    RESEARCH_ATLAS = "research_atlas"


class ConformanceStatus(StrEnum):
    EXACT = "EXACT"
    PARTIAL = "PARTIAL"
    LEGACY_APPROXIMATION = "LEGACY_APPROXIMATION"


class MaturityLevel(StrEnum):
    NONE = "NONE"
    PROPOSED = "PROPOSED"
    REVIEWED = "REVIEWED"
    IMPLEMENTED = "IMPLEMENTED"
    VERIFIED = "VERIFIED"
    APPROVED = "APPROVED"
    EXPOSED = "EXPOSED"
    NOT_REVIEWED = "NOT_REVIEWED"
    NOT_EXPOSED = "NOT_EXPOSED"


class CommonEnvelope(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_.:-]+$")
    version: str = "1.0.0"
    kind: ObjectKind
    display_name: str
    description: str
    status: Status = Status.CURRENT
    aliases: list[str] = Field(default_factory=list)
    supersedes: list[str] = Field(default_factory=list)
    deprecated_by: str | None = None
    created_from: list[str] = Field(default_factory=list)
    owners: list[str] = Field(default_factory=list)
    reviewers: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class TypeRef(StrictModel):
    container: str
    value: str
    quantity: str | None = None
    unit: str = "none"
    coordinate_frame: str | None = None
    perspective: str | None = None
    temporal_basis: str = "canonical_frame_time"
    entity_scope: str | None = None
    nullable: bool = True


class TypedField(StrictModel):
    name: str
    type: TypeRef
    required: bool = True
    description: str = ""


class Concept(CommonEnvelope):
    kind: Literal[ObjectKind.CONCEPT] = ObjectKind.CONCEPT
    claim_contract_ref: str
    evidence_contract_ref: str | None = None


class Operationalization(CommonEnvelope):
    kind: Literal[ObjectKind.OPERATIONALIZATION] = ObjectKind.OPERATIONALIZATION
    concept_refs: list[str] = Field(min_length=1)
    semantic_basis: SemanticBasis
    required_modalities: list[str] = Field(min_length=1)
    applicability: list[str] = Field(default_factory=list)
    inputs: list[TypedField] = Field(min_length=1)
    outputs: list[TypedField] = Field(min_length=1)
    lowering: list[str] = Field(default_factory=list)
    claim_contract_ref: str
    evidence_contract_ref: str


class DefinitionProfile(CommonEnvelope):
    kind: Literal[ObjectKind.DEFINITION_PROFILE] = ObjectKind.DEFINITION_PROFILE
    operationalization_ref: str
    bindings: dict[str, Any] = Field(default_factory=dict)
    claim_contract_ref: str
    evidence_contract_ref: str


class Implementation(CommonEnvelope):
    kind: Literal[ObjectKind.IMPLEMENTATION] = ObjectKind.IMPLEMENTATION
    implements: list[str] = Field(min_length=1)
    source_refs: list[str] = Field(default_factory=list)
    implementation_type: str = "python"


class RuntimeCapabilityRef(StrictModel):
    id: str
    version: str
    kind: Literal["primitive", "relation"]


class RuntimeBinding(CommonEnvelope):
    kind: Literal[ObjectKind.RUNTIME_BINDING] = ObjectKind.RUNTIME_BINDING
    runtime_capability: RuntimeCapabilityRef
    implementation_ref: str
    implements: list[str] = Field(min_length=1)
    conformance_status: ConformanceStatus
    known_deviations: list[str] = Field(default_factory=list)


class OperatorParameter(StrictModel):
    name: str
    type: TypeRef
    required: bool = False
    description: str = ""


class OperatorDefinition(CommonEnvelope):
    kind: Literal[ObjectKind.OPERATOR_DEFINITION] = ObjectKind.OPERATOR_DEFINITION
    operator_id: str
    operator_version: str
    input: TypeRef
    output: TypeRef
    compare: TypeRef | None = None
    parameters: list[OperatorParameter] = Field(default_factory=list)
    unknown_semantics: dict[str, Any] = Field(default_factory=dict)
    authorability: AuthoringExposure = AuthoringExposure.ALLOWED


class ClaimContract(CommonEnvelope):
    kind: Literal[ObjectKind.CLAIM_CONTRACT] = ObjectKind.CLAIM_CONTRACT
    inherits: list[str] = Field(default_factory=list)
    permitted: list[str] = Field(default_factory=list)
    prohibited: list[str] = Field(default_factory=list)
    unknown_conditions: list[str] = Field(default_factory=list)


class EvidenceContract(CommonEnvelope):
    kind: Literal[ObjectKind.EVIDENCE_CONTRACT] = ObjectKind.EVIDENCE_CONTRACT
    inherits: list[str] = Field(default_factory=list)
    required: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)
    replay_projection: list[str] = Field(default_factory=list)


class ExposurePolicy(CommonEnvelope):
    kind: Literal[ObjectKind.EXPOSURE_POLICY] = ObjectKind.EXPOSURE_POLICY
    subject_ref: str
    ai_compiler: AuthoringExposure = AuthoringExposure.DENIED
    product: AuthoringExposure = AuthoringExposure.DENIED
    reviewed_recipes: AuthoringExposure = AuthoringExposure.ALLOWED
    parameter_overrides: dict[str, Any] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)


class ProjectionPolicy(CommonEnvelope):
    kind: Literal[ObjectKind.PROJECTION_POLICY] = ObjectKind.PROJECTION_POLICY
    target: ProjectionTarget
    requires: dict[str, Any] = Field(default_factory=dict)
    excludes: list[str] = Field(default_factory=list)


class MaturityAssessment(CommonEnvelope):
    kind: Literal[ObjectKind.MATURITY_ASSESSMENT] = ObjectKind.MATURITY_ASSESSMENT
    subject_ref: str
    semantic: MaturityLevel
    implementation: MaturityLevel
    validation: MaturityLevel
    agent_safety: MaturityLevel
    product: MaturityLevel


class RecipeDefinitionMapping(CommonEnvelope):
    kind: Literal[ObjectKind.RECIPE_DEFINITION] = ObjectKind.RECIPE_DEFINITION
    recipe_id: str
    recipe_version: str
    plan_artifact_ref: str
    dependency_refs: list[str] = Field(default_factory=list)
    profile_refs: list[str] = Field(default_factory=list)
    claim_contract_ref: str
    evidence_contract_ref: str


class PlanArtifact(CommonEnvelope):
    kind: Literal[ObjectKind.PLAN_ARTIFACT] = ObjectKind.PLAN_ARTIFACT
    origin: Literal["REVIEWED_RECIPE", "MANUAL_PRESET", "AI_AUTHORED"]
    promotion_status: Literal[
        "REGISTERED_RECIPE",
        "VALIDATED_COMPOSITION",
        "EXPERIMENTAL_PRESET",
        "REVIEWED_RECIPE",
    ]
    exact_typed_plan_ref: str
    recipe_ref: str | None = None


class CompositionInstance(CommonEnvelope):
    kind: Literal[ObjectKind.COMPOSITION_INSTANCE] = ObjectKind.COMPOSITION_INSTANCE
    plan_artifact_ref: str
    origin: Literal["AI_AUTHORED", "MANUAL_PRESET"]
    promotion_status: Literal["VALIDATED_COMPOSITION", "EXPERIMENTAL"]
    claim_contract_ref: str
    evidence_contract_ref: str


class ExecutionRecord(CommonEnvelope):
    kind: Literal[ObjectKind.EXECUTION_RECORD] = ObjectKind.EXECUTION_RECORD
    plan_artifact_ref: str
    execution_ref: str
    scope: dict[str, Any] = Field(default_factory=dict)


class AtlasEntry(CommonEnvelope):
    kind: Literal[ObjectKind.ATLAS_ENTRY] = ObjectKind.ATLAS_ENTRY
    source_name: str
    family: str
    provisional_kind: str = "UNCLASSIFIED"
    source_provenance: dict[str, Any]
    exposure_default: AuthoringExposure = AuthoringExposure.DENIED


class SemanticRegistry(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    registry_id: str
    registry_version: str
    concepts: list[Concept] = Field(default_factory=list)
    operationalizations: list[Operationalization] = Field(default_factory=list)
    definition_profiles: list[DefinitionProfile] = Field(default_factory=list)
    implementations: list[Implementation] = Field(default_factory=list)
    runtime_bindings: list[RuntimeBinding] = Field(default_factory=list)
    operator_definitions: list[OperatorDefinition] = Field(default_factory=list)
    recipe_definitions: list[RecipeDefinitionMapping] = Field(default_factory=list)
    plan_artifacts: list[PlanArtifact] = Field(default_factory=list)
    composition_instances: list[CompositionInstance] = Field(default_factory=list)
    execution_records: list[ExecutionRecord] = Field(default_factory=list)
    claim_contracts: list[ClaimContract] = Field(default_factory=list)
    evidence_contracts: list[EvidenceContract] = Field(default_factory=list)
    exposure_policies: list[ExposurePolicy] = Field(default_factory=list)
    projection_policies: list[ProjectionPolicy] = Field(default_factory=list)
    maturity_assessments: list[MaturityAssessment] = Field(default_factory=list)
    atlas_entries: list[AtlasEntry] = Field(default_factory=list)

    @field_validator(
        "concepts",
        "operationalizations",
        "definition_profiles",
        "implementations",
        "runtime_bindings",
        "operator_definitions",
        "recipe_definitions",
        "plan_artifacts",
        "composition_instances",
        "execution_records",
        "claim_contracts",
        "evidence_contracts",
        "exposure_policies",
        "projection_policies",
        "maturity_assessments",
        "atlas_entries",
    )
    @classmethod
    def object_ids_are_unique(cls, items: list[CommonEnvelope]) -> list[CommonEnvelope]:
        ids = [item.id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("registry object ids must be unique within each object collection")
        return items

    @model_validator(mode="after")
    def global_object_ids_are_unique(self) -> "SemanticRegistry":
        all_ids: list[str] = []
        for collection in (
            self.concepts,
            self.operationalizations,
            self.definition_profiles,
            self.implementations,
            self.runtime_bindings,
            self.operator_definitions,
            self.recipe_definitions,
            self.plan_artifacts,
            self.composition_instances,
            self.execution_records,
            self.claim_contracts,
            self.evidence_contracts,
            self.exposure_policies,
            self.projection_policies,
            self.maturity_assessments,
            self.atlas_entries,
        ):
            all_ids.extend(item.id for item in collection)
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("registry object ids must be globally unique")
        return self


class RegistryLock(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    registry_revision: str
    runtime_manifest_revision: str
    plan_artifact_revision: str
    generator_version: str
    product_projection_policy: str
    ai_projection_policy: str
    recipe_projection_policy: str
    unsupported_projection_policy: str
    research_atlas_projection_policy: str
    evidence_schema_version: str
    typed_plan_schema_version: str
    lock_hash: str


class ValidationFinding(StrictModel):
    code: str
    message: str
    path: str


class SemanticParityReport(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    status: Literal["PASS", "FAIL"]
    registry_lock: RegistryLock
    findings: list[ValidationFinding] = Field(default_factory=list)
    runtime_capabilities: dict[str, Any]
    operators: dict[str, Any]
    recipes: dict[str, Any]
    validated_compositions: dict[str, Any]
    projection_differences: dict[str, Any]
    atlas_leakage: dict[str, int]
    pilots: dict[str, Any]
