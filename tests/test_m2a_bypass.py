import unittest

from tqe.runtime.bypass import BypassConfig, PlayerPosition, evaluate_opponents_bypassed_by_action


class M2ABypassMeasurementTest(unittest.TestCase):
    def test_attacking_direction_mirroring_preserves_count(self) -> None:
        forward = evaluate_opponents_bypassed_by_action(
            release_ball_x_m=0.0,
            reception_ball_x_m=10.0,
            attack_x_sign=1,
            expected_active_opponent_ids={"a", "b"},
            release_opponent_positions={
                "a": PlayerPosition(5.0, 1.0),
                "b": PlayerPosition(-2.0, 1.0),
            },
            reception_opponent_positions={
                "a": PlayerPosition(5.0, 1.0),
                "b": PlayerPosition(-2.0, 1.0),
            },
        )
        mirrored = evaluate_opponents_bypassed_by_action(
            release_ball_x_m=0.0,
            reception_ball_x_m=-10.0,
            attack_x_sign=-1,
            expected_active_opponent_ids={"a", "b"},
            release_opponent_positions={
                "a": PlayerPosition(-5.0, 1.0),
                "b": PlayerPosition(2.0, 1.0),
            },
            reception_opponent_positions={
                "a": PlayerPosition(-5.0, 1.0),
                "b": PlayerPosition(2.0, 1.0),
            },
        )

        self.assertEqual("PASS", forward.evaluation_status)
        self.assertEqual("PASS", mirrored.evaluation_status)
        self.assertEqual(("a",), forward.bypassed_player_ids)
        self.assertEqual(forward.bypassed_player_ids, mirrored.bypassed_player_ids)
        self.assertEqual(forward.opponents_bypassed_count, mirrored.opponents_bypassed_count)

    def test_player_order_does_not_change_result(self) -> None:
        first = evaluate_opponents_bypassed_by_action(
            release_ball_x_m=0.0,
            reception_ball_x_m=12.0,
            attack_x_sign=1,
            expected_active_opponent_ids=["c", "a", "b"],
            release_opponent_positions={
                "b": (6.0, 0.0),
                "a": (4.0, 0.0),
                "c": (-1.0, 0.0),
            },
            reception_opponent_positions={
                "c": (-1.0, 0.0),
                "a": (4.0, 0.0),
                "b": (6.0, 0.0),
            },
        )
        second = evaluate_opponents_bypassed_by_action(
            release_ball_x_m=0.0,
            reception_ball_x_m=12.0,
            attack_x_sign=1,
            expected_active_opponent_ids=["b", "c", "a"],
            release_opponent_positions={
                "c": (-1.0, 0.0),
                "a": (4.0, 0.0),
                "b": (6.0, 0.0),
            },
            reception_opponent_positions={
                "b": (6.0, 0.0),
                "c": (-1.0, 0.0),
                "a": (4.0, 0.0),
            },
        )

        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(("a", "b"), first.bypassed_player_ids)

    def test_buffer_edges_are_strict(self) -> None:
        evaluation = evaluate_opponents_bypassed_by_action(
            release_ball_x_m=0.0,
            reception_ball_x_m=10.0,
            attack_x_sign=1,
            config=BypassConfig(goal_side_buffer_m=1.0, bypassed_buffer_m=1.0),
            expected_active_opponent_ids={"level_release", "level_reception", "clear"},
            release_opponent_positions={
                "level_release": (1.0, 0.0),
                "level_reception": (2.0, 0.0),
                "clear": (2.0, 0.0),
            },
            reception_opponent_positions={
                "level_release": (0.0, 0.0),
                "level_reception": (9.0, 0.0),
                "clear": (8.99, 0.0),
            },
        )

        self.assertEqual(("clear", "level_reception"), evaluation.candidate_goal_side_ids)
        self.assertEqual(("clear",), evaluation.bypassed_player_ids)
        self.assertEqual(1, evaluation.opponents_bypassed_count)

    def test_missing_expected_active_opponent_makes_unknown(self) -> None:
        evaluation = evaluate_opponents_bypassed_by_action(
            release_ball_x_m=0.0,
            reception_ball_x_m=10.0,
            attack_x_sign=1,
            expected_active_opponent_ids={"a", "missing"},
            release_opponent_positions={"a": (5.0, 0.0), "missing": (7.0, 0.0)},
            reception_opponent_positions={"a": (5.0, 0.0)},
        )

        self.assertEqual("UNKNOWN", evaluation.evaluation_status)
        self.assertEqual("UNKNOWN", evaluation.coverage_status)
        self.assertEqual(("missing",), evaluation.missing_active_opponent_ids)
        self.assertEqual(("a",), evaluation.bypassed_player_ids)
        self.assertEqual(1, evaluation.opponents_bypassed_count)

    def test_excluded_goalkeeper_is_not_required_or_counted(self) -> None:
        evaluation = evaluate_opponents_bypassed_by_action(
            release_ball_x_m=0.0,
            reception_ball_x_m=10.0,
            attack_x_sign=1,
            expected_active_opponent_ids={"a", "gk"},
            excluded_opponent_ids={"gk"},
            release_opponent_positions={"a": (5.0, 0.0), "gk": (7.0, 0.0)},
            reception_opponent_positions={"a": (5.0, 0.0)},
        )

        self.assertEqual("PASS", evaluation.evaluation_status)
        self.assertEqual(("a",), evaluation.expected_active_opponent_ids)
        self.assertEqual((), evaluation.missing_active_opponent_ids)
        self.assertEqual(("a",), evaluation.bypassed_player_ids)

    def test_measurement_is_threshold_free(self) -> None:
        evaluation = evaluate_opponents_bypassed_by_action(
            release_ball_x_m=0.0,
            reception_ball_x_m=20.0,
            attack_x_sign=1,
            expected_active_opponent_ids={"a", "b", "c", "d"},
            release_opponent_positions={
                "a": (2.0, 0.0),
                "b": (4.0, 0.0),
                "c": (6.0, 0.0),
                "d": (8.0, 0.0),
            },
            reception_opponent_positions={
                "a": (2.0, 0.0),
                "b": (4.0, 0.0),
                "c": (6.0, 0.0),
                "d": (8.0, 0.0),
            },
        )

        self.assertEqual("PASS", evaluation.evaluation_status)
        self.assertEqual(4, evaluation.opponents_bypassed_count)
        self.assertNotIn("threshold", evaluation.to_dict())


if __name__ == "__main__":
    unittest.main()
