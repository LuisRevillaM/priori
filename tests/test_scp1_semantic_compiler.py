from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from tqe.runtime.binder import bind_document
from tqe.runtime.ir import PayloadType, Unit, model_payload, stable_hash
from tqe.semantic_compiler import CompilerOutcome, SemanticExpression, compile_semantic_expression


PROGRAM_DIR = Path("delivery/scp-1/semantic-programs")


class SCP1SemanticCompilerTests(unittest.TestCase):
    def test_executable_ball_side_program_lowers_and_binds(self) -> None:
        expression = self.load_expression("ball_side_block_shift.semantic.json")

        result = compile_semantic_expression(expression)

        self.assertEqual(CompilerOutcome.COMPILED, result.outcome)
        self.assertEqual("ball_side_block_shift_v1", result.runtime_recipe_id)
        self.assertIsNotNone(result.runtime_document)
        self.assertEqual(
            bind_document(result.runtime_document).bound_plan_hash,
            result.bound_plan_hash,
        )

    def test_executable_high_bypass_program_lowers_to_current_runtime_document(self) -> None:
        expression = self.load_expression("high_bypass_completed_pass.semantic.json")

        result = compile_semantic_expression(expression)

        self.assertEqual(CompilerOutcome.COMPILED, result.outcome)
        self.assertEqual("high_bypass_completed_pass_v1", result.runtime_recipe_id)
        self.assertIsNotNone(result.runtime_document)
        self.assertEqual(
            stable_hash(model_payload(result.runtime_document)),
            result.lowered_document_hash,
        )

    def test_parameter_override_is_typed_and_survives_lowering(self) -> None:
        expression = self.load_expression("high_bypass_completed_pass.semantic.json")
        payload = deepcopy(expression.model_dump(mode="json", by_alias=True, exclude_none=True))
        payload["parameter_overrides"] = {
            "minimum_bypassed_opponents": {
                "payload_type": PayloadType.NUMBER.value,
                "unit": Unit.COUNT.value,
                "value": 6,
            }
        }

        result = compile_semantic_expression(SemanticExpression.model_validate(payload))

        self.assertEqual(CompilerOutcome.COMPILED, result.outcome)
        self.assertIsNotNone(result.runtime_document)
        override = result.runtime_document.default_invocation.parameters[
            "minimum_bypassed_opponents"
        ]
        self.assertEqual(PayloadType.NUMBER, override.payload_type)
        self.assertEqual(Unit.COUNT, override.unit)
        self.assertEqual(6, override.value)

    def test_unknown_parameter_override_fails_closed_without_runtime_document(self) -> None:
        expression = self.load_expression("high_bypass_completed_pass.semantic.json")
        payload = deepcopy(expression.model_dump(mode="json", by_alias=True, exclude_none=True))
        payload["parameter_overrides"] = {
            "made_up_threshold": {
                "payload_type": PayloadType.NUMBER.value,
                "unit": Unit.COUNT.value,
                "value": 6,
            }
        }

        result = compile_semantic_expression(SemanticExpression.model_validate(payload))

        self.assertEqual(CompilerOutcome.COMPILER_ERROR, result.outcome)
        self.assertIsNone(result.runtime_document)
        self.assertIsNotNone(result.blocking_gap)
        self.assertEqual("made_up_threshold", result.blocking_gap.concept)

    def test_goal_kick_gap_is_smallest_missing_operationalization(self) -> None:
        result = compile_semantic_expression(
            self.load_expression("goal_kick_restart_candidate_gap.semantic.json")
        )

        self.assertEqual(CompilerOutcome.CAPABILITY_GAP, result.outcome)
        self.assertIsNone(result.runtime_document)
        self.assertIsNotNone(result.blocking_gap)
        self.assertEqual("MISSING_OPERATIONALIZATION", result.blocking_gap.kind.value)
        self.assertEqual("restart_taken_candidate", result.blocking_gap.concept)

    def test_modality_gap_is_not_collapsed_into_capability_gap(self) -> None:
        result = compile_semantic_expression(
            self.load_expression("player_intent_modality_gap.semantic.json")
        )

        self.assertEqual(CompilerOutcome.MODALITY_GAP, result.outcome)
        self.assertIsNone(result.runtime_document)
        self.assertIsNotNone(result.blocking_gap)
        self.assertEqual(
            "player_intent_from_scanning_and_body_orientation",
            result.blocking_gap.concept,
        )

    def test_clarification_gap_is_not_executable(self) -> None:
        result = compile_semantic_expression(
            self.load_expression("support_arrival_clarification.semantic.json")
        )

        self.assertEqual(CompilerOutcome.CLARIFICATION_REQUIRED, result.outcome)
        self.assertIsNone(result.runtime_document)
        self.assertIsNotNone(result.blocking_gap)
        self.assertEqual("support_arrival_profile", result.blocking_gap.concept)

    def test_every_fixture_declares_full_football_query_normal_form(self) -> None:
        for path in sorted(PROGRAM_DIR.glob("*.semantic.json")):
            with self.subTest(path=path.name):
                result = compile_semantic_expression(self.load_expression(path.name))
                self.assertTrue(result.normal_form_complete)

    @staticmethod
    def load_expression(name: str) -> SemanticExpression:
        return SemanticExpression.model_validate_json(
            (PROGRAM_DIR / name).read_text(encoding="utf-8")
        )


if __name__ == "__main__":
    unittest.main()
