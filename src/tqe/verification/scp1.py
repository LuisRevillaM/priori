"""SCP-1L semantic compiler verifier."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document, load_tactical_query_document
from tqe.runtime.ir import PayloadType, Unit, model_payload, stable_hash
from tqe.semantic_compiler import (
    CompilerOutcome,
    SemanticExpression,
    SemanticGapKind,
    compile_semantic_expression,
    load_expression_from_path,
)
from tqe.semantic_compiler.lowering import result_public_payload
from tqe.write_mode import output_path


PROGRAM_DIR = Path("delivery/scp-1/semantic-programs")
REPORT_PATH = Path("artifacts/scp-1/verification-report.json")

EXECUTABLE_PROGRAMS = {
    "ball_side_block_shift": PROGRAM_DIR / "ball_side_block_shift.semantic.json",
    "high_bypass_completed_pass": PROGRAM_DIR / "high_bypass_completed_pass.semantic.json",
}
GAP_PROGRAMS = {
    "goal_kick_restart_candidate": PROGRAM_DIR / "goal_kick_restart_candidate_gap.semantic.json",
    "player_intent_modality": PROGRAM_DIR / "player_intent_modality_gap.semantic.json",
    "support_arrival_clarification": PROGRAM_DIR / "support_arrival_clarification.semantic.json",
}


def main() -> None:
    report = run_verification()
    report_path = output_path(REPORT_PATH)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True))
    if report["status"] != "PASS":
        raise SystemExit(1)


def run_verification() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    compiled: dict[str, Any] = {}
    gaps: dict[str, Any] = {}

    for name, path in EXECUTABLE_PROGRAMS.items():
        expression = load_expression_from_path(path)
        result = compile_semantic_expression(expression)
        compiled[name] = result_public_payload(result)
        _check(
            checks,
            f"{name}.outcome_compiled",
            result.outcome == CompilerOutcome.COMPILED,
            {"outcome": result.outcome.value},
        )
        _check(
            checks,
            f"{name}.normal_form_complete",
            result.normal_form_complete,
            {},
        )
        expected = expression.fixture_expectation
        _check(
            checks,
            f"{name}.recipe_id_matches_expectation",
            expected is not None and result.runtime_recipe_id == expected.runtime_recipe_id,
            {
                "expected": expected.runtime_recipe_id if expected else None,
                "actual": result.runtime_recipe_id,
            },
        )
        _check(
            checks,
            f"{name}.lowered_document_binds",
            result.runtime_document is not None
            and bind_document(result.runtime_document).bound_plan_hash == result.bound_plan_hash,
            {"bound_plan_hash": result.bound_plan_hash},
        )
        _check(
            checks,
            f"{name}.lowered_document_matches_source_without_overrides",
            _source_document_hash(expression) == result.lowered_document_hash,
            {
                "source_document_hash": _source_document_hash(expression),
                "lowered_document_hash": result.lowered_document_hash,
            },
        )

    high_bypass = load_expression_from_path(EXECUTABLE_PROGRAMS["high_bypass_completed_pass"])
    override_result = compile_semantic_expression(_with_high_bypass_threshold(high_bypass, 6))
    override_params = (
        override_result.runtime_document.default_invocation.parameters
        if override_result.runtime_document is not None
        else {}
    )
    _check(
        checks,
        "high_bypass.parameter_override_survives_lowering",
        override_result.outcome == CompilerOutcome.COMPILED
        and "minimum_bypassed_opponents" in override_params
        and override_params["minimum_bypassed_opponents"].value == 6,
        {
            "outcome": override_result.outcome.value,
            "override": override_params.get("minimum_bypassed_opponents").model_dump(mode="json")
            if "minimum_bypassed_opponents" in override_params
            else None,
        },
    )
    _check(
        checks,
        "high_bypass.parameter_override_changes_document_hash",
        override_result.lowered_document_hash
        != compiled["high_bypass_completed_pass"]["lowered_document_hash"],
        {
            "base": compiled["high_bypass_completed_pass"]["lowered_document_hash"],
            "override": override_result.lowered_document_hash,
        },
    )

    invalid_override = compile_semantic_expression(_with_high_bypass_wrong_unit(high_bypass))
    _check(
        checks,
        "high_bypass.invalid_parameter_unit_fails_closed",
        invalid_override.outcome == CompilerOutcome.COMPILER_ERROR
        and invalid_override.runtime_document is None
        and invalid_override.blocking_gap is not None
        and invalid_override.blocking_gap.kind == SemanticGapKind.COMPILER_ERROR,
        result_public_payload(invalid_override),
    )

    for name, path in GAP_PROGRAMS.items():
        expression = load_expression_from_path(path)
        result = compile_semantic_expression(expression)
        gaps[name] = result_public_payload(result)
        expected = expression.fixture_expectation
        _check(
            checks,
            f"{name}.expected_gap_outcome",
            expected is not None
            and result.outcome == expected.outcome
            and result.blocking_gap is not None
            and result.blocking_gap.kind == expected.blocking_gap_kind
            and result.blocking_gap.concept == expected.blocking_gap_concept,
            {
                "expected_outcome": expected.outcome.value if expected else None,
                "actual_outcome": result.outcome.value,
                "expected_gap_kind": expected.blocking_gap_kind.value
                if expected and expected.blocking_gap_kind
                else None,
                "actual_gap_kind": result.blocking_gap.kind.value if result.blocking_gap else None,
                "expected_concept": expected.blocking_gap_concept if expected else None,
                "actual_concept": result.blocking_gap.concept if result.blocking_gap else None,
            },
        )
        _check(
            checks,
            f"{name}.gap_does_not_emit_runtime_document",
            result.runtime_document is None
            and result.plan_hash is None
            and result.bound_plan_hash is None,
            {},
        )
        _check(
            checks,
            f"{name}.normal_form_complete",
            result.normal_form_complete,
            {},
        )

    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    return {
        "schema_version": "scp1.verification.v1",
        "milestone": "SCP-1L",
        "status": status,
        "summary": {
            "checks_total": len(checks),
            "checks_passed": sum(1 for item in checks if item["status"] == "PASS"),
            "checks_failed": sum(1 for item in checks if item["status"] == "FAIL"),
            "executable_programs": sorted(EXECUTABLE_PROGRAMS),
            "gap_programs": sorted(GAP_PROGRAMS),
        },
        "compiled": compiled,
        "gaps": gaps,
        "checks": checks,
    }


def _source_document_hash(expression: SemanticExpression) -> str | None:
    if expression.lowering_target is None:
        return None
    document = load_tactical_query_document(Path(expression.lowering_target.plan_path))
    return stable_hash(model_payload(document))


def _with_high_bypass_threshold(
    expression: SemanticExpression,
    threshold: int,
) -> SemanticExpression:
    payload = deepcopy(expression.model_dump(mode="json", by_alias=True, exclude_none=True))
    payload["parameter_overrides"] = {
        "minimum_bypassed_opponents": {
            "payload_type": PayloadType.NUMBER.value,
            "unit": Unit.COUNT.value,
            "value": threshold,
        }
    }
    return SemanticExpression.model_validate(payload)


def _with_high_bypass_wrong_unit(expression: SemanticExpression) -> SemanticExpression:
    payload = deepcopy(expression.model_dump(mode="json", by_alias=True, exclude_none=True))
    payload["parameter_overrides"] = {
        "minimum_bypassed_opponents": {
            "payload_type": PayloadType.NUMBER.value,
            "unit": Unit.SECOND.value,
            "value": 6,
        }
    }
    return SemanticExpression.model_validate(payload)


def _check(
    checks: list[dict[str, Any]],
    check_id: str,
    condition: bool,
    details: dict[str, Any],
) -> None:
    checks.append(
        {
            "id": check_id,
            "status": "PASS" if condition else "FAIL",
            "details": details,
        }
    )


if __name__ == "__main__":
    main()
