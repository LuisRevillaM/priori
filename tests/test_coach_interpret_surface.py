import unittest
from copy import deepcopy
from typing import Any

from src.tqe.workshop.app_service import (
    COACH_PRODUCT_CLAIM_REQUIREMENTS,
    coach_moment_payload,
    coach_no_moments_kind,
    coach_preview_runtime_family_without_surface,
    coach_product_claim_gate,
    coach_template,
    coach_visual_moment_kind,
)


def with_dotted_value(payload: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
    mutated = deepcopy(payload)
    current: Any = mutated
    parts = path.split(".")
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value
    return mutated


class CoachInterpretSurfaceTests(unittest.TestCase):
    def test_progressive_carry_zero_has_specific_kind(self) -> None:
        contract = {
            "required_evidence": ["carry_status", "pressure_status", "carry_forward_progression_m"],
            "status_semantics": [
                {"field": "carry_status", "required_value": "PASS"},
                {"field": "pressure_status", "required_value": "PASS"},
            ],
        }

        self.assertEqual("progressive_carry_under_pressure", coach_no_moments_kind(contract))
        self.assertEqual(
            "Across these matches, no carry progressed forward under defender pressure.",
            coach_template("no_moments_found.progressive_carry_under_pressure"),
        )

    def test_line_break_zero_has_corpus_scoped_copy(self) -> None:
        contract = {
            "required_evidence": [
                "line_break_status",
                "support_arrival_status",
                "support_region_mode",
                "supporting_player_ids",
            ],
            "status_semantics": [
                {"field": "line_break_status", "required_value": "PASS"},
                {"field": "support_arrival_status", "required_value": "FAIL"},
            ],
        }

        self.assertEqual("line_break_no_underneath_support", coach_no_moments_kind(contract))
        self.assertEqual(
            "Across these matches, that clean-control line-break moment did not appear.",
            coach_template("no_moments_found.line_break_no_underneath_support"),
        )

    def test_line_break_two_support_zero_has_specific_kind(self) -> None:
        contract = {
            "required_evidence": [
                "line_break_status",
                "support_arrival_status",
                "support_region_mode",
                "supporting_player_ids",
            ],
            "status_semantics": [
                {"field": "line_break_status", "required_value": "PASS"},
                {"field": "support_arrival_status", "required_value": "PASS"},
            ],
            "composition_constraints": [{"kind": "relation_on_anchor", "minimum_supporting_players": 2}],
        }

        self.assertEqual("line_break_with_two_underneath_outlets", coach_no_moments_kind(contract))
        self.assertFalse(coach_preview_runtime_family_without_surface(contract))
        self.assertEqual(
            "Across these matches, no clean-control line break had two underneath outlets.",
            coach_template("no_moments_found.line_break_with_two_underneath_outlets"),
        )

    def test_line_break_with_support_has_positive_visual_kind(self) -> None:
        contract = {
            "required_evidence": [
                "line_break_status",
                "support_arrival_status",
                "support_region_mode",
                "supporting_player_ids",
            ],
            "status_semantics": [
                {"field": "line_break_status", "required_value": "PASS"},
                {"field": "support_arrival_status", "required_value": "PASS"},
            ],
            "composition_constraints": [{"kind": "relation_on_anchor", "minimum_supporting_players": 1}],
        }

        self.assertEqual("line_break_with_underneath_outlet", coach_visual_moment_kind(contract))
        self.assertEqual("line_break_with_underneath_outlet", coach_no_moments_kind(contract))
        self.assertFalse(coach_preview_runtime_family_without_surface(contract))
        self.assertEqual(
            "Line broken. Support arrives underneath.",
            coach_template("moment_found.line_break_with_underneath_outlet"),
        )

    def test_high_bypass_pass_has_visual_and_zero_kind(self) -> None:
        contract = {
            "required_evidence": [
                "pass_episode_id",
                "passer_id",
                "receiver_id",
                "release_frame_id",
                "reception_frame_id",
                "release_ball_point",
                "reception_ball_point",
                "forward_progression_m",
                "opponents_bypassed_count",
                "bypassed_player_ids",
                "evaluation_status",
            ],
            "status_semantics": [
                {"field": "evaluation_status", "required_value": "PASS"},
                {"field": "forward_progression_m", "operator": "gte", "threshold": 8.0, "unit": "metre"},
                {"field": "opponents_bypassed_count", "operator": "gte", "threshold": 5.0, "unit": "count"},
            ],
        }

        self.assertEqual("high_bypass_completed_pass", coach_visual_moment_kind(contract))
        self.assertEqual("high_bypass_completed_pass", coach_no_moments_kind(contract))
        self.assertFalse(coach_preview_runtime_family_without_surface(contract))
        self.assertEqual(
            "Passes bypassed multiple opponents with control after reception.",
            coach_template("moment_found.high_bypass_completed_pass"),
        )
        self.assertEqual(
            "Across these matches, no clean-control pass bypassed five opponents.",
            coach_template("no_moments_found.high_bypass_completed_pass"),
        )

    def test_public_preview_skips_runtime_families_without_surface(self) -> None:
        contract = {
            "required_evidence": ["carry_status", "pressure_status", "carry_forward_progression_m"],
            "status_semantics": [
                {"field": "carry_status", "required_value": "PASS"},
                {"field": "pressure_status", "required_value": "PASS"},
            ],
        }

        self.assertTrue(coach_preview_runtime_family_without_surface(contract))

    def test_high_bypass_claim_gate_enforces_every_declared_requirement(self) -> None:
        kind = "high_bypass_completed_pass"
        payload = coach_moment_payload(kind)
        gate = coach_product_claim_gate(kind, payload)

        self.assertTrue(gate["passed"])
        spec = COACH_PRODUCT_CLAIM_REQUIREMENTS[kind]
        self.assertEqual(spec["claim_id"], gate["claim_id"])
        # The claim id must stay in observed-evidence language.
        self.assertTrue(gate["claim_id"].startswith("observed_"))

        # The clean-control retention evidence is load-bearing: contradicting it
        # must flip the gate with an explicit failure record.
        unbacked = with_dotted_value(payload, "moment.clean_control_retention.status", "FAIL")
        failed = coach_product_claim_gate(kind, unbacked)
        self.assertFalse(failed["passed"])
        self.assertIn(
            {
                "path": "moment.clean_control_retention.status",
                "expected": "PASS",
                "actual": "FAIL",
            },
            failed["failures"],
        )

        # Every equals-requirement in the declared claim contract is enforced,
        # not just the retention path.
        for requirement in spec["requirements"]:
            if "equals" not in requirement:
                continue
            tampered = with_dotted_value(payload, requirement["path"], "__contradicted__")
            self.assertFalse(
                coach_product_claim_gate(kind, tampered)["passed"],
                f"requirement not enforced: {requirement['path']}",
            )

    def test_unknown_kind_fails_closed_without_claim_id(self) -> None:
        gate = coach_product_claim_gate("not_a_registered_kind", {})

        self.assertFalse(gate["passed"])
        self.assertIsNone(gate["claim_id"])
        self.assertIn({"path": "kind", "reason": "claim_requirements_missing"}, gate["failures"])

    def test_line_break_claim_requires_clean_control_but_not_possession_retention(self) -> None:
        kind = "line_break_with_underneath_outlet"
        payload = coach_moment_payload(kind)
        # Possession retention is not proven for this moment...
        self.assertNotEqual("PASS", payload["moment"]["possession_retention"]["status"])

        gate = coach_product_claim_gate(kind, payload)

        # ...and the claim passes anyway, because the declared claim is scoped to
        # clean control after reception, not possession retention.
        self.assertTrue(gate["passed"])
        self.assertEqual(
            COACH_PRODUCT_CLAIM_REQUIREMENTS[kind]["claim_id"], gate["claim_id"]
        )
        self.assertTrue(gate["claim_id"].startswith("observed_"))

        # Clean-control retention is still required evidence.
        unbacked = with_dotted_value(payload, "moment.clean_control_retention.status", "FAIL")
        self.assertFalse(coach_product_claim_gate(kind, unbacked)["passed"])


if __name__ == "__main__":
    unittest.main()
