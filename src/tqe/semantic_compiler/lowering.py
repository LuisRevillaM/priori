"""Lower SCP-1 semantic expressions into the existing runtime authority chain."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from pydantic import ValidationError

from tqe.runtime.binder import BindError, bind_document, load_tactical_query_document
from tqe.runtime.ir import (
    ParameterDefinition,
    PayloadType,
    TacticalQueryDocument,
    TypedValue,
    model_payload,
    stable_hash,
)
from tqe.semantic_compiler.models import (
    CompilerOutcome,
    SemanticCompilerResult,
    SemanticExpression,
    SemanticGap,
    SemanticGapKind,
    SemanticPort,
    SemanticTypeRef,
)


def load_expression_from_path(path: Path) -> SemanticExpression:
    return SemanticExpression.model_validate_json(path.read_text(encoding="utf-8"))


def compile_semantic_expression(
    expression: SemanticExpression,
    *,
    root: Path = Path("."),
) -> SemanticCompilerResult:
    """Compile a semantic expression or return the smallest typed gap.

    SCP-1L intentionally lowers only through checked-in TacticalQueryDocument
    targets. It does not construct a separate runtime AST or bypass the binder.
    """

    expression_hash = stable_hash(
        expression.model_dump(mode="json", by_alias=True, exclude_none=True)
    )
    normal_form_complete = _normal_form_complete(expression)

    if expression.declared_gaps:
        gap = expression.declared_gaps[0]
        return SemanticCompilerResult(
            expression_id=expression.expression_id,
            outcome=_outcome_for_gap(gap),
            support=expression.support,
            semantic_program_hash=expression_hash,
            normal_form_complete=normal_form_complete,
            blocking_gap=gap,
            notes=["typed semantic gap returned without executable runtime document"],
        )

    if expression.lowering_target is None:
        return _compiler_error(
            expression=expression,
            expression_hash=expression_hash,
            normal_form_complete=normal_form_complete,
            concept="lowering_target",
            message="Executable semantic expression has no lowering target.",
        )

    plan_path = root / expression.lowering_target.plan_path
    try:
        document = load_tactical_query_document(plan_path)
    except (OSError, ValidationError, ValueError) as exc:
        return _compiler_error(
            expression=expression,
            expression_hash=expression_hash,
            normal_form_complete=normal_form_complete,
            concept="tactical_query_document",
            message=f"{type(exc).__name__}: {exc}",
        )

    override_error = _validate_parameter_overrides(document, expression.parameter_overrides)
    if override_error is not None:
        return _compiler_error(
            expression=expression,
            expression_hash=expression_hash,
            normal_form_complete=normal_form_complete,
            concept=override_error[0],
            message=override_error[1],
        )

    lowered_payload = _apply_parameter_overrides(document, expression.parameter_overrides)
    try:
        lowered_document = TacticalQueryDocument.model_validate(lowered_payload)
        bound = bind_document(lowered_document)
    except (ValidationError, BindError, ValueError) as exc:
        return _compiler_error(
            expression=expression,
            expression_hash=expression_hash,
            normal_form_complete=normal_form_complete,
            concept="runtime_binding",
            message=f"{type(exc).__name__}: {exc}",
        )

    return SemanticCompilerResult(
        expression_id=expression.expression_id,
        outcome=CompilerOutcome.COMPILED,
        support=expression.support,
        semantic_program_hash=expression_hash,
        normal_form_complete=normal_form_complete,
        runtime_recipe_id=lowered_document.recipe.recipe_id,
        runtime_plan_id=lowered_document.draft_plan.plan_id,
        lowered_document_hash=stable_hash(model_payload(lowered_document)),
        plan_hash=bound.plan_hash,
        bound_plan_hash=bound.bound_plan_hash,
        notes=[
            "lowered through existing TacticalQueryDocument",
            "bound by existing deterministic binder",
        ],
        runtime_document=lowered_document,
    )


def _apply_parameter_overrides(
    document: TacticalQueryDocument,
    overrides: dict[str, TypedValue],
) -> dict:
    payload = deepcopy(document.model_dump(mode="json", exclude_none=True))
    invocation = payload["default_invocation"]
    invocation.setdefault("parameters", {})
    for name, value in sorted(overrides.items()):
        invocation["parameters"][name] = value.model_dump(mode="json", exclude_none=True)
    return payload


def _validate_parameter_overrides(
    document: TacticalQueryDocument,
    overrides: dict[str, TypedValue],
) -> tuple[str, str] | None:
    definitions = {parameter.name: parameter for parameter in document.recipe.parameters}
    for name, value in sorted(overrides.items()):
        parameter = definitions.get(name)
        if parameter is None:
            return name, f"Unknown semantic parameter override: {name}"
        mismatch = _parameter_mismatch(parameter, value)
        if mismatch is not None:
            return name, mismatch
    return None


def _parameter_mismatch(parameter: ParameterDefinition, value: TypedValue) -> str | None:
    if value.payload_type != parameter.payload_type:
        return (
            f"Parameter {parameter.name} expects {parameter.payload_type.value}, "
            f"got {value.payload_type.value}"
        )
    if value.unit != parameter.unit:
        return f"Parameter {parameter.name} expects {parameter.unit.value}, got {value.unit.value}"
    if value.payload_type == PayloadType.NUMBER:
        numeric = float(value.value)
        if parameter.minimum is not None and numeric < parameter.minimum:
            return f"Parameter {parameter.name} must be >= {parameter.minimum}, got {numeric}"
        if parameter.maximum is not None and numeric > parameter.maximum:
            return f"Parameter {parameter.name} must be <= {parameter.maximum}, got {numeric}"
    if (
        parameter.allowed_values is not None
        and str(value.value) not in set(parameter.allowed_values)
    ):
        return f"Parameter {parameter.name} must be one of {sorted(parameter.allowed_values)}"
    return None


def _normal_form_complete(expression: SemanticExpression) -> bool:
    normal_form = expression.normal_form
    return all(
        getattr(normal_form, slot).summary.strip()
        for slot in (
            "scope",
            "anchor",
            "bind",
            "measure",
            "match",
            "outcome",
            "judge",
            "return_",
        )
    )


def _outcome_for_gap(gap: SemanticGap) -> CompilerOutcome:
    if gap.kind == SemanticGapKind.CLARIFICATION_REQUIRED:
        return CompilerOutcome.CLARIFICATION_REQUIRED
    if gap.kind == SemanticGapKind.MODALITY_GAP:
        return CompilerOutcome.MODALITY_GAP
    if gap.kind == SemanticGapKind.NON_IDENTIFIABLE:
        return CompilerOutcome.NON_IDENTIFIABLE
    if gap.kind == SemanticGapKind.COMPILER_ERROR:
        return CompilerOutcome.COMPILER_ERROR
    return CompilerOutcome.CAPABILITY_GAP


def _compiler_error(
    *,
    expression: SemanticExpression,
    expression_hash: str,
    normal_form_complete: bool,
    concept: str,
    message: str,
) -> SemanticCompilerResult:
    return SemanticCompilerResult(
        expression_id=expression.expression_id,
        outcome=CompilerOutcome.COMPILER_ERROR,
        support=expression.support,
        semantic_program_hash=expression_hash,
        normal_form_complete=normal_form_complete,
        blocking_gap=SemanticGap(
            kind=SemanticGapKind.COMPILER_ERROR,
            concept=concept,
            expected_input=[
                SemanticPort(
                    name="semantic_expression",
                    semantic_type=SemanticTypeRef(container="program", value="SemanticExpression"),
                    description="A valid SCP-1 semantic expression.",
                )
            ],
            expected_output=SemanticTypeRef(container="document", value="TacticalQueryDocument"),
            semantic_basis="compiler_boundary",
            required_modalities=[],
            claim_boundary="Compiler errors are not football capability gaps.",
            evidence_obligations=["deterministic_error_message"],
            surrounding_program_type_correct=False,
            message=message,
        ),
        notes=[message],
    )


def result_public_payload(result: SemanticCompilerResult) -> dict:
    return json.loads(
        result.model_dump_json(
            exclude={"runtime_document"},
            exclude_none=True,
        )
    )
