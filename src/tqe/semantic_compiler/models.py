"""Typed semantic program models for SCP-1.

These models are deliberately above the runtime IR. They describe the football
meaning the compiler has understood before executable parts lower into a
TacticalQueryDocument.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tqe.runtime.ir import TacticalQueryDocument, TypedValue


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CompilerOutcome(StrEnum):
    COMPILED = "COMPILED"
    COMPILED_WITH_DISCLOSED_DEFAULT_PROFILE = "COMPILED_WITH_DISCLOSED_DEFAULT_PROFILE"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    CAPABILITY_GAP = "CAPABILITY_GAP"
    MODALITY_GAP = "MODALITY_GAP"
    NON_IDENTIFIABLE = "NON_IDENTIFIABLE"
    COMPILER_ERROR = "COMPILER_ERROR"


class SemanticGapKind(StrEnum):
    MISSING_TYPE = "MISSING_TYPE"
    MISSING_OPERATOR = "MISSING_OPERATOR"
    MISSING_CONCEPT = "MISSING_CONCEPT"
    MISSING_OPERATIONALIZATION = "MISSING_OPERATIONALIZATION"
    MISSING_RUNTIME_IMPLEMENTATION = "MISSING_RUNTIME_IMPLEMENTATION"
    MODALITY_GAP = "MODALITY_GAP"
    NON_IDENTIFIABLE = "NON_IDENTIFIABLE"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    COMPILER_ERROR = "COMPILER_ERROR"


class SemanticTypeRef(StrictModel):
    container: str
    value: str
    unit: str = "none"
    cardinality: str | None = None
    entity_scope: str | None = None
    temporal_basis: str = "canonical_frame_time"


class SemanticPort(StrictModel):
    name: str
    semantic_type: SemanticTypeRef
    description: str


class SupportFacts(StrictModel):
    expressible: bool
    compilable: bool
    executable: bool
    identifiable: bool
    validated: bool


class NormalFormSlot(StrictModel):
    summary: str = Field(min_length=1)
    semantic_refs: list[str] = Field(default_factory=list)
    runtime_refs: list[str] = Field(default_factory=list)


class FootballQueryNormalForm(StrictModel):
    scope: NormalFormSlot
    anchor: NormalFormSlot
    bind: NormalFormSlot
    measure: NormalFormSlot
    match: NormalFormSlot
    outcome: NormalFormSlot
    judge: NormalFormSlot
    return_: NormalFormSlot = Field(alias="return")

    @model_validator(mode="after")
    def all_slots_are_declared(self) -> "FootballQueryNormalForm":
        for slot_name in (
            "scope",
            "anchor",
            "bind",
            "measure",
            "match",
            "outcome",
            "judge",
            "return_",
        ):
            slot = getattr(self, slot_name)
            if not slot.summary.strip():
                raise ValueError(f"{slot_name} summary must not be blank")
        return self


class SemanticGap(StrictModel):
    kind: SemanticGapKind
    concept: str
    expected_input: list[SemanticPort] = Field(default_factory=list)
    expected_output: SemanticTypeRef | None = None
    semantic_basis: str
    required_modalities: list[str] = Field(default_factory=list)
    claim_boundary: str
    evidence_obligations: list[str] = Field(default_factory=list)
    surrounding_program_type_correct: bool = True
    executable_prefix_exists: bool = False
    executable_suffix_exists: bool = False
    message: str


class LoweringTarget(StrictModel):
    kind: Literal["existing_tactical_query_document"] = "existing_tactical_query_document"
    plan_path: str
    profile: Literal["reviewed_recipe", "experimental_program"] = "experimental_program"


class FixtureExpectation(StrictModel):
    outcome: CompilerOutcome
    runtime_recipe_id: str | None = None
    blocking_gap_kind: SemanticGapKind | None = None
    blocking_gap_concept: str | None = None


class SemanticExpression(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    expression_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    expression_version: str
    display_name: str
    query_text: str
    description: str
    normal_form: FootballQueryNormalForm
    support: SupportFacts
    concept_refs: list[str] = Field(default_factory=list)
    operator_refs: list[str] = Field(default_factory=list)
    required_modalities: list[str] = Field(default_factory=list)
    lowering_target: LoweringTarget | None = None
    parameter_overrides: dict[str, TypedValue] = Field(default_factory=dict)
    declared_gaps: list[SemanticGap] = Field(default_factory=list)
    fixture_expectation: FixtureExpectation | None = None

    @model_validator(mode="after")
    def executable_programs_need_target_and_gaps_do_not(self) -> "SemanticExpression":
        if self.support.executable and self.lowering_target is None:
            raise ValueError("executable semantic expressions require a lowering target")
        if self.declared_gaps and self.lowering_target is not None:
            raise ValueError("gap-only semantic expressions must not declare a lowering target")
        if not self.support.executable and not self.declared_gaps:
            raise ValueError("non-executable semantic expressions must declare typed gaps")
        return self


class SemanticCompilerResult(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    expression_id: str
    outcome: CompilerOutcome
    support: SupportFacts
    semantic_program_hash: str
    normal_form_complete: bool
    runtime_recipe_id: str | None = None
    runtime_plan_id: str | None = None
    lowered_document_hash: str | None = None
    plan_hash: str | None = None
    bound_plan_hash: str | None = None
    blocking_gap: SemanticGap | None = None
    notes: list[str] = Field(default_factory=list)
    runtime_document: TacticalQueryDocument | None = None
