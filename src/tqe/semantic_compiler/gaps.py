"""Canonical helpers for typed semantic gaps.

Gap expressions are compiler artifacts, not runtime plans. These helpers keep
unsupported query clauses structured enough for coverage maps and future
compiler agents to harvest mechanically.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from tqe.semantic_compiler.models import (
    FixtureExpectation,
    FootballQueryNormalForm,
    NormalFormSlot,
    SemanticExpression,
    SemanticGap,
    SemanticGapKind,
    SemanticPort,
    SemanticTypeRef,
    SupportFacts,
)

NormalFormSlotName = Literal[
    "scope",
    "anchor",
    "bind",
    "measure",
    "match",
    "outcome",
    "judge",
    "return",
]


def missing_operationalization_gap(
    *,
    concept: str,
    expected_input: Sequence[SemanticPort | Mapping[str, Any]],
    expected_output: SemanticTypeRef | Mapping[str, Any],
    semantic_basis: str,
    required_modalities: Sequence[str],
    claim_boundary: str,
    evidence_obligations: Sequence[str],
    message: str,
    executable_prefix_exists: bool,
    executable_suffix_exists: bool = False,
    surrounding_program_type_correct: bool = True,
) -> SemanticGap:
    """Build the canonical declared gap for a missing operationalization."""

    return SemanticGap(
        kind=SemanticGapKind.MISSING_OPERATIONALIZATION,
        concept=concept,
        expected_input=[
            item if isinstance(item, SemanticPort) else SemanticPort.model_validate(item)
            for item in expected_input
        ],
        expected_output=(
            expected_output
            if isinstance(expected_output, SemanticTypeRef)
            else SemanticTypeRef.model_validate(expected_output)
        ),
        semantic_basis=semantic_basis,
        required_modalities=list(required_modalities),
        claim_boundary=claim_boundary,
        evidence_obligations=list(evidence_obligations),
        surrounding_program_type_correct=surrounding_program_type_correct,
        executable_prefix_exists=executable_prefix_exists,
        executable_suffix_exists=executable_suffix_exists,
        message=message,
    )


def missing_operationalization_gap_expression(
    *,
    expression_id: str,
    expression_version: str,
    display_name: str,
    query_text: str,
    description: str,
    normal_form: FootballQueryNormalForm | Mapping[str, Any],
    blocking_concept: str,
    blocked_slot: NormalFormSlotName,
    expected_input: Sequence[SemanticPort | Mapping[str, Any]],
    expected_output: SemanticTypeRef | Mapping[str, Any],
    semantic_basis: str,
    required_modalities: Sequence[str],
    claim_boundary: str,
    evidence_obligations: Sequence[str],
    message: str,
    executable_prefix_exists: bool,
    concept_refs: Sequence[str] = (),
    operator_refs: Sequence[str] = (),
    support: SupportFacts | Mapping[str, Any] | None = None,
    executable_suffix_exists: bool = False,
) -> SemanticExpression:
    """Build a canonical gap-only expression for a blocked query clause.

    The blocked normal-form slot must name the missing concept in
    ``semantic_refs`` and must have no runtime refs. That makes the gap
    mechanically harvestable: the coverage map can read the blocked clause,
    blocker, reason, and evidence obligations without inferring from prose.
    """

    normal = (
        normal_form
        if isinstance(normal_form, FootballQueryNormalForm)
        else FootballQueryNormalForm.model_validate(normal_form)
    )
    _validate_blocked_slot(
        normal_form=normal,
        blocked_slot=blocked_slot,
        blocking_concept=blocking_concept,
    )

    gap = missing_operationalization_gap(
        concept=blocking_concept,
        expected_input=expected_input,
        expected_output=expected_output,
        semantic_basis=semantic_basis,
        required_modalities=required_modalities,
        claim_boundary=claim_boundary,
        evidence_obligations=evidence_obligations,
        executable_prefix_exists=executable_prefix_exists,
        executable_suffix_exists=executable_suffix_exists,
        message=message,
    )
    support_facts = (
        SupportFacts(
            expressible=True,
            compilable=False,
            executable=False,
            identifiable=False,
            validated=False,
        )
        if support is None
        else support
        if isinstance(support, SupportFacts)
        else SupportFacts.model_validate(support)
    )

    return SemanticExpression(
        expression_id=expression_id,
        expression_version=expression_version,
        display_name=display_name,
        query_text=query_text,
        description=description,
        normal_form=normal,
        support=support_facts,
        concept_refs=list(concept_refs),
        operator_refs=list(operator_refs),
        required_modalities=list(required_modalities),
        declared_gaps=[gap],
        fixture_expectation=FixtureExpectation(
            outcome="CAPABILITY_GAP",
            blocking_gap_kind=SemanticGapKind.MISSING_OPERATIONALIZATION,
            blocking_gap_concept=blocking_concept,
        ),
    )


def _validate_blocked_slot(
    *,
    normal_form: FootballQueryNormalForm,
    blocked_slot: NormalFormSlotName,
    blocking_concept: str,
) -> None:
    slot = _normal_form_slot(normal_form, blocked_slot)
    if slot.runtime_refs:
        raise ValueError(
            f"blocked slot {blocked_slot!r} must not declare runtime refs for "
            f"missing operationalization {blocking_concept!r}"
        )
    if blocking_concept not in slot.semantic_refs:
        raise ValueError(
            f"blocked slot {blocked_slot!r} must include {blocking_concept!r} "
            "in semantic_refs"
        )


def _normal_form_slot(
    normal_form: FootballQueryNormalForm,
    slot: NormalFormSlotName,
) -> NormalFormSlot:
    if slot == "return":
        return normal_form.return_
    return getattr(normal_form, slot)
