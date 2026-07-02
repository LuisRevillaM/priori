import unittest

from tqe.runtime.defensive_line import (
    DefensiveLineConfig,
    DefensivePlayerPosition,
    evaluate_defensive_line_model,
)


class DefensiveLineModelTest(unittest.TestCase):
    def test_pass_with_compact_goal_side_line(self) -> None:
        evaluation = evaluate_defensive_line_model(
            ball_x_m=0.0,
            attacking_direction=1,
            goalkeeper_excluded_from_positions=True,
            config=DefensiveLineConfig(goal_side_buffer_m=1.0, line_band_width_m=1.0),
            defending_player_positions={
                "d1": (10.0, -12.0),
                "d2": (10.2, -4.0),
                "d3": (10.4, 4.0),
                "d4": (10.7, 12.0),
                "behind_ball": (-1.0, 0.0),
            },
        )

        self.assertEqual("PASS", evaluation.status)
        self.assertEqual("observed_defensive_line", evaluation.line_type)
        self.assertEqual(("d1", "d2", "d3", "d4"), evaluation.defender_ids)
        self.assertEqual(4, evaluation.defenders_goal_side_count)
        self.assertAlmostEqual(0.7, evaluation.compactness_m)

    def test_fail_when_complete_evidence_has_no_compact_band(self) -> None:
        evaluation = evaluate_defensive_line_model(
            ball_x_m=0.0,
            attacking_direction=1,
            goalkeeper_excluded_from_positions=True,
            config=DefensiveLineConfig(goal_side_buffer_m=1.0, line_band_width_m=1.0),
            defending_player_positions={
                "d1": (5.0, -8.0),
                "d2": (8.0, -4.0),
                "d3": (12.0, 0.0),
                "d4": (16.0, 4.0),
                "d5": (20.0, 8.0),
            },
        )

        self.assertEqual("FAIL", evaluation.status)
        self.assertEqual("no_qualifying_line", evaluation.reason)
        self.assertEqual(5, evaluation.defenders_goal_side_count)
        self.assertEqual((), evaluation.defender_ids)

    def test_unknown_for_missing_ball_position(self) -> None:
        evaluation = evaluate_defensive_line_model(
            ball_x_m=None,
            attacking_direction=1,
            goalkeeper_excluded_from_positions=True,
            defending_player_positions=compact_line_positions(),
        )

        self.assertEqual("UNKNOWN", evaluation.status)
        self.assertEqual("ball_x_missing", evaluation.reason)

    def test_unknown_for_invalid_attacking_direction(self) -> None:
        evaluation = evaluate_defensive_line_model(
            ball_x_m=0.0,
            attacking_direction=0,
            defending_player_positions=compact_line_positions(),
        )

        self.assertEqual("UNKNOWN", evaluation.status)
        self.assertEqual("attacking_direction_invalid", evaluation.reason)

    def test_goalkeeper_is_excluded_from_line(self) -> None:
        evaluation = evaluate_defensive_line_model(
            ball_x_m=0.0,
            attacking_direction=1,
            goalkeeper_id="gk",
            config=DefensiveLineConfig(goal_side_buffer_m=1.0, line_band_width_m=1.0),
            defending_player_positions={
                "gk": (10.3, 0.0),
                "d1": (10.0, -12.0),
                "d2": (10.2, -4.0),
                "d3": (10.4, 4.0),
                "d4": (10.7, 12.0),
            },
        )

        self.assertEqual("PASS", evaluation.status)
        self.assertEqual("gk", evaluation.goalkeeper_id)
        self.assertEqual(("d1", "d2", "d3", "d4"), evaluation.defender_ids)
        self.assertNotIn("gk", {item.player_id for item in evaluation.defender_positions_used})

    def test_unknown_when_goalkeeper_unidentified_in_supplied_positions(self) -> None:
        # goalkeeper_id=None with goalkeeper_id_known=True and no declaration
        # that the goalkeeper was excluded upstream is fail-closed: the model
        # must not silently count the goalkeeper as an outfield line member.
        evaluation = evaluate_defensive_line_model(
            ball_x_m=0.0,
            attacking_direction=1,
            config=DefensiveLineConfig(goal_side_buffer_m=1.0, line_band_width_m=1.0),
            defending_player_positions={
                "gk": (10.3, 0.0),
                "d1": (10.0, -12.0),
                "d2": (10.2, -4.0),
                "d3": (10.4, 4.0),
                "d4": (10.7, 12.0),
            },
        )

        self.assertEqual("UNKNOWN", evaluation.status)
        self.assertEqual("goalkeeper_identity_missing", evaluation.reason)
        self.assertEqual((), evaluation.defender_ids)

    def test_goalkeeper_exclusion_declaration_matches_explicit_goalkeeper_id(self) -> None:
        outfield_only = {
            "d1": (10.0, -12.0),
            "d2": (10.2, -4.0),
            "d3": (10.4, 4.0),
            "d4": (10.7, 12.0),
        }
        declared_excluded = evaluate_defensive_line_model(
            ball_x_m=0.0,
            attacking_direction=1,
            goalkeeper_excluded_from_positions=True,
            config=DefensiveLineConfig(goal_side_buffer_m=1.0, line_band_width_m=1.0),
            defending_player_positions=dict(outfield_only),
        )
        identified = evaluate_defensive_line_model(
            ball_x_m=0.0,
            attacking_direction=1,
            goalkeeper_id="gk",
            config=DefensiveLineConfig(goal_side_buffer_m=1.0, line_band_width_m=1.0),
            defending_player_positions={**outfield_only, "gk": (10.3, 0.0)},
        )

        self.assertEqual("PASS", declared_excluded.status)
        self.assertEqual("PASS", identified.status)
        self.assertEqual(declared_excluded.defender_ids, identified.defender_ids)
        self.assertEqual(declared_excluded.line_x_m, identified.line_x_m)

    def test_missing_mapping_y_is_not_fabricated_as_zero(self) -> None:
        with_y = evaluate_defensive_line_model(
            ball_x_m=0.0,
            attacking_direction=1,
            goalkeeper_excluded_from_positions=True,
            config=DefensiveLineConfig(goal_side_buffer_m=1.0, line_band_width_m=1.0),
            defending_player_positions={
                "d1": {"x_m": 10.0, "y_m": -12.0},
                "d2": {"x_m": 10.2, "y_m": -4.0},
                "d3": {"x_m": 10.4, "y_m": 4.0},
                "d4": {"x_m": 10.7, "y_m": 12.0},
            },
        )
        without_y = evaluate_defensive_line_model(
            ball_x_m=0.0,
            attacking_direction=1,
            goalkeeper_excluded_from_positions=True,
            config=DefensiveLineConfig(goal_side_buffer_m=1.0, line_band_width_m=1.0),
            defending_player_positions={
                "d1": {"x_m": 10.0},
                "d2": {"x_m": 10.2},
                "d3": {"x_m": 10.4},
                "d4": {"x_m": 10.7},
            },
        )

        self.assertEqual("PASS", without_y.status)
        self.assertEqual(with_y.defender_ids, without_y.defender_ids)
        self.assertEqual(with_y.line_x_m, without_y.line_x_m)
        self.assertEqual(
            {None},
            {item.y_m for item in without_y.defender_positions_used},
        )
        self.assertNotIn(0.0, {item.y_m for item in without_y.defender_positions_used})

    def test_unknown_when_goalkeeper_identity_uncertain(self) -> None:
        evaluation = evaluate_defensive_line_model(
            ball_x_m=0.0,
            attacking_direction=1,
            goalkeeper_id_known=False,
            defending_player_positions=compact_line_positions(),
        )

        self.assertEqual("UNKNOWN", evaluation.status)
        self.assertEqual("goalkeeper_identity_uncertain", evaluation.reason)

    def test_unknown_when_active_defender_denominator_uncertain(self) -> None:
        evaluation = evaluate_defensive_line_model(
            ball_x_m=0.0,
            attacking_direction=1,
            goalkeeper_excluded_from_positions=True,
            active_defender_ids_known=False,
            defending_player_positions=compact_line_positions(),
        )

        self.assertEqual("UNKNOWN", evaluation.status)
        self.assertEqual("active_defender_denominator_uncertain", evaluation.reason)

    def test_mirrored_attacking_direction_preserves_line_membership_and_counts(self) -> None:
        forward = evaluate_defensive_line_model(
            ball_x_m=0.0,
            attacking_direction=1,
            goalkeeper_excluded_from_positions=True,
            defending_player_positions=compact_line_positions(),
        )
        mirrored = evaluate_defensive_line_model(
            ball_x_m=0.0,
            attacking_direction=-1,
            goalkeeper_excluded_from_positions=True,
            defending_player_positions={
                player_id: DefensivePlayerPosition(x_m=-position.x_m, y_m=position.y_m)
                for player_id, position in compact_line_positions().items()
            },
        )

        self.assertEqual("PASS", forward.status)
        self.assertEqual("PASS", mirrored.status)
        self.assertEqual(forward.defender_ids, mirrored.defender_ids)
        self.assertEqual(forward.defenders_goal_side_count, mirrored.defenders_goal_side_count)
        self.assertAlmostEqual(forward.normalized_line_x_m, mirrored.normalized_line_x_m)

    def test_result_is_deterministic_under_shuffled_player_order(self) -> None:
        first = evaluate_defensive_line_model(
            ball_x_m=0.0,
            attacking_direction=1,
            goalkeeper_excluded_from_positions=True,
            defending_player_positions={
                "d4": (10.7, 12.0),
                "d1": (10.0, -12.0),
                "d3": (10.4, 4.0),
                "d2": (10.2, -4.0),
                "behind_ball": (-1.0, 0.0),
            },
        )
        second = evaluate_defensive_line_model(
            ball_x_m=0.0,
            attacking_direction=1,
            goalkeeper_excluded_from_positions=True,
            defending_player_positions={
                "behind_ball": (-1.0, 0.0),
                "d2": (10.2, -4.0),
                "d3": (10.4, 4.0),
                "d1": (10.0, -12.0),
                "d4": (10.7, 12.0),
            },
        )

        self.assertEqual(first.to_dict(), second.to_dict())

    def test_ambiguous_two_line_tie_returns_unknown(self) -> None:
        evaluation = evaluate_defensive_line_model(
            ball_x_m=0.0,
            attacking_direction=1,
            goalkeeper_excluded_from_positions=True,
            config=DefensiveLineConfig(goal_side_buffer_m=1.0, line_band_width_m=3.0),
            defending_player_positions={
                "a1": (10.0, -12.0),
                "a2": (11.0, -4.0),
                "a3": (12.0, 4.0),
                "a4": (13.0, 12.0),
                "b1": (20.0, -12.0),
                "b2": (21.0, -4.0),
                "b3": (22.0, 4.0),
                "b4": (23.0, 12.0),
            },
        )

        self.assertEqual("UNKNOWN", evaluation.status)
        self.assertEqual("ambiguous_candidate_lines", evaluation.reason)
        self.assertEqual(
            (("a1", "a2", "a3", "a4"), ("b1", "b2", "b3", "b4")),
            evaluation.ambiguous_band_defender_ids,
        )


def compact_line_positions() -> dict[str, DefensivePlayerPosition]:
    return {
        "d1": DefensivePlayerPosition(10.0, -12.0),
        "d2": DefensivePlayerPosition(10.2, -4.0),
        "d3": DefensivePlayerPosition(10.4, 4.0),
        "d4": DefensivePlayerPosition(10.7, 12.0),
    }


if __name__ == "__main__":
    unittest.main()
