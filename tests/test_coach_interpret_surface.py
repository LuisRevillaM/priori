import unittest

from src.tqe.workshop.app_service import coach_no_moments_kind, coach_template


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


if __name__ == "__main__":
    unittest.main()
