import unittest

from src.tqe.workshop.app_service import (
    coach_no_moments_kind,
    coach_preview_runtime_family_without_surface,
    coach_template,
    coach_visual_moment_kind,
)


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
            "In this match, no carry progressed forward under defender pressure.",
            coach_template("no_moments_found.progressive_carry_under_pressure"),
        )

    def test_line_break_zero_has_match_scoped_copy(self) -> None:
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
            "In this match, that line-break moment did not appear.",
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
            "In this match, no line break had two underneath outlets.",
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
            "One completed pass bypassed multiple opponents. The ball reaches the final third.",
            coach_template("moment_found.high_bypass_completed_pass"),
        )
        self.assertEqual(
            "In this match, no completed pass bypassed five opponents.",
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


if __name__ == "__main__":
    unittest.main()
