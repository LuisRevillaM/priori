from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from tqe.runtime.binder import bind_document
from tqe.runtime.ir import PayloadType, Unit, model_payload, stable_hash
from tqe.semantic_compiler import (
    CompilerOutcome,
    SemanticExpression,
    compile_semantic_expression,
    missing_operationalization_gap_expression,
)


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

    def test_missing_operationalization_helper_emits_canonical_gap_shape(self) -> None:
        expression = missing_operationalization_gap_expression(
            expression_id="test_lane_coverage_gap",
            expression_version="0.1.0",
            display_name="Lane Coverage Gap",
            query_text="Show lane coverage after a switch.",
            description="Coverage is blocked until reachability exists.",
            normal_form=self.gap_normal_form(
                outcome={
                    "summary": "Lane coverage requires reachability.",
                    "semantic_refs": ["time_to_arrival"],
                    "runtime_refs": [],
                }
            ),
            blocking_concept="time_to_arrival",
            blocked_slot="outcome",
            expected_input=[
                {
                    "name": "lane_region",
                    "semantic_type": {
                        "container": "region",
                        "value": "LaneRegion",
                        "unit": "none",
                    },
                    "description": "The lane being tested.",
                }
            ],
            expected_output={
                "container": "frame_signal",
                "value": "ReachabilityMargin",
                "unit": "second",
            },
            semantic_basis="lane_coverage_requires_reachability_not_occupancy",
            required_modalities=["tracking"],
            claim_boundary="No lane coverage claim without reachability.",
            evidence_obligations=["defender_position_time_series"],
            message="Missing operationalization: time_to_arrival.",
            executable_prefix_exists=True,
        )

        result = compile_semantic_expression(expression)

        self.assertEqual(CompilerOutcome.CAPABILITY_GAP, result.outcome)
        self.assertIsNotNone(result.blocking_gap)
        self.assertEqual("MISSING_OPERATIONALIZATION", result.blocking_gap.kind.value)
        self.assertEqual("time_to_arrival", result.blocking_gap.concept)
        self.assertTrue(result.blocking_gap.executable_prefix_exists)
        self.assertEqual([], expression.normal_form.outcome.runtime_refs)
        self.assertEqual("time_to_arrival", expression.fixture_expectation.blocking_gap_concept)

    def test_missing_operationalization_helper_rejects_runtime_refs_on_blocked_slot(self) -> None:
        with self.assertRaises(ValueError):
            missing_operationalization_gap_expression(
                expression_id="test_bad_lane_coverage_gap",
                expression_version="0.1.0",
                display_name="Bad Lane Coverage Gap",
                query_text="Show lane coverage after a switch.",
                description="Bad fixture with fabricated runtime refs.",
                normal_form=self.gap_normal_form(
                    outcome={
                        "summary": "Lane coverage requires reachability.",
                        "semantic_refs": ["time_to_arrival"],
                        "runtime_refs": ["lane_coverage"],
                    }
                ),
                blocking_concept="time_to_arrival",
                blocked_slot="outcome",
                expected_input=[
                    {
                        "name": "lane_region",
                        "semantic_type": {"container": "region", "value": "LaneRegion"},
                        "description": "The lane being tested.",
                    }
                ],
                expected_output={"container": "frame_signal", "value": "ReachabilityMargin"},
                semantic_basis="lane_coverage_requires_reachability_not_occupancy",
                required_modalities=["tracking"],
                claim_boundary="No lane coverage claim without reachability.",
                evidence_obligations=["defender_position_time_series"],
                message="Missing operationalization: time_to_arrival.",
                executable_prefix_exists=True,
            )

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

    @staticmethod
    def gap_normal_form(**overrides: dict) -> dict:
        slots = {
            "scope": {"summary": "Selected matches.", "semantic_refs": [], "runtime_refs": []},
            "anchor": {"summary": "A relevant anchor.", "semantic_refs": [], "runtime_refs": []},
            "bind": {"summary": "Relevant entities.", "semantic_refs": [], "runtime_refs": []},
            "measure": {"summary": "Available measurements.", "semantic_refs": [], "runtime_refs": []},
            "match": {"summary": "Available predicates.", "semantic_refs": [], "runtime_refs": []},
            "outcome": {"summary": "Blocked outcome.", "semantic_refs": [], "runtime_refs": []},
            "judge": {"summary": "Return an honest gap.", "semantic_refs": [], "runtime_refs": []},
            "return": {"summary": "Typed gap.", "semantic_refs": [], "runtime_refs": []},
        }
        slots.update(overrides)
        return slots


if __name__ == "__main__":
    unittest.main()
