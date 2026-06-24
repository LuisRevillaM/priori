import json
import unittest

import pandas as pd

from tqe.runtime.lane_occupancy import (
    CENTRAL,
    FAIL,
    LEFT_HALF_SPACE,
    LEFT_WIDE,
    PASS,
    RIGHT_HALF_SPACE,
    RIGHT_WIDE,
    UNKNOWN,
    LaneOccupancyReason,
    evaluate_lane_occupancy,
)
from tqe.runtime.executor import observed_outfield_positions_at_frame


class LaneOccupancyKernelTest(unittest.TestCase):
    def test_default_lane_assignment_classifies_selected_players(self) -> None:
        evaluation = evaluate_lane_occupancy(
            anchor_id="shape-1",
            frame_id=100,
            player_positions=[
                player("lw", frame_id=100, y_m=-30.0),
                player("lhs", frame_id=100, y_m=-15.0),
                player("c", frame_id=100, y_m=0.0),
                player("rhs", frame_id=100, y_m=15.0),
                player("rw", frame_id=100, y_m=30.0),
                player("ignored", frame_id=100, y_m=0.0),
            ],
            target_player_ids=["lw", "lhs", "c", "rhs", "rw"],
        )

        self.assertEqual(PASS, evaluation.status)
        self.assertEqual(LaneOccupancyReason.OCCUPANCY_CLASSIFIED.value, evaluation.reason)
        self.assertEqual((LEFT_WIDE, LEFT_HALF_SPACE, CENTRAL, RIGHT_HALF_SPACE, RIGHT_WIDE), evaluation.occupied_lanes)
        self.assertEqual(
            {
                LEFT_WIDE: 1,
                LEFT_HALF_SPACE: 1,
                CENTRAL: 1,
                RIGHT_HALF_SPACE: 1,
                RIGHT_WIDE: 1,
            },
            evaluation.lane_counts,
        )
        self.assertEqual("shape-1", evaluation.anchor_id)
        self.assertEqual(100, evaluation.anchor_frame_id)
        self.assertEqual((100,), evaluation.frame_ids)
        self.assertEqual(-34.0, evaluation.lane_definitions[0].min_y_m)
        self.assertEqual(34.0, evaluation.lane_definitions[-1].max_y_m)
        self.assertEqual("min_y_inclusive_max_y_exclusive_except_final_lane", evaluation.boundary_policy)

    def test_passes_multi_lane_and_count_requirement(self) -> None:
        evaluation = evaluate_lane_occupancy(
            player_positions=[
                player("left", y_m=-28.0),
                player("central-a", y_m=-1.0),
                player("central-b", y_m=1.0),
                player("right", y_m=28.0),
            ],
            target_player_ids=["left", "central-a", "central-b", "right"],
            required_lane_ids=[LEFT_WIDE, RIGHT_WIDE],
            required_lane_counts={CENTRAL: 2},
            required_occupied_lane_count=3,
        )

        self.assertEqual(PASS, evaluation.status)
        self.assertEqual(LaneOccupancyReason.REQUIREMENT_SATISFIED.value, evaluation.reason)
        self.assertEqual(2, evaluation.lane_counts[CENTRAL])
        self.assertEqual({CENTRAL: 2}, evaluation.required_lane_counts)
        self.assertEqual(3, evaluation.required_occupied_lane_count)

    def test_fails_when_fully_evaluated_requirement_is_not_met(self) -> None:
        evaluation = evaluate_lane_occupancy(
            player_positions=[player("a", y_m=-2.0), player("b", y_m=2.0)],
            target_player_ids=["a", "b"],
            required_lane_ids=[LEFT_WIDE],
            required_lane_counts={CENTRAL: 3},
        )

        self.assertEqual(FAIL, evaluation.status)
        self.assertEqual(LaneOccupancyReason.REQUIREMENT_NOT_MET.value, evaluation.reason)
        self.assertEqual("COMPLETE", evaluation.coverage_status)
        self.assertEqual((), evaluation.missing_player_ids)
        self.assertEqual((), evaluation.invalid_coordinate_player_ids)
        self.assertEqual((), evaluation.duplicate_player_ids)

    def test_unknown_when_missing_target_player_evidence_could_change_answer(self) -> None:
        evaluation = evaluate_lane_occupancy(
            player_positions=[player("a", y_m=0.0)],
            target_player_ids=["a", "missing"],
            required_occupied_lane_count=2,
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual(LaneOccupancyReason.MISSING_TARGET_PLAYER_EVIDENCE.value, evaluation.reason)
        self.assertEqual(("missing",), evaluation.missing_player_ids)
        self.assertEqual((CENTRAL,), evaluation.occupied_lanes)

    def test_boundary_positions_use_documented_tie_policy(self) -> None:
        evaluation = evaluate_lane_occupancy(
            player_positions=[
                player("left-touchline", y_m=-34.0),
                player("left-half-boundary", y_m=-20.4),
                player("central-boundary", y_m=-6.8),
                player("right-half-boundary", y_m=6.8),
                player("right-wide-boundary", y_m=20.4),
                player("right-touchline", y_m=34.0),
            ]
        )

        self.assertEqual(PASS, evaluation.status)
        assignments = {assignment.player_id: assignment.lane_id for assignment in evaluation.player_assignments}
        self.assertEqual(LEFT_WIDE, assignments["left-touchline"])
        self.assertEqual(LEFT_HALF_SPACE, assignments["left-half-boundary"])
        self.assertEqual(CENTRAL, assignments["central-boundary"])
        self.assertEqual(RIGHT_HALF_SPACE, assignments["right-half-boundary"])
        self.assertEqual(RIGHT_WIDE, assignments["right-wide-boundary"])
        self.assertEqual(RIGHT_WIDE, assignments["right-touchline"])

    def test_record_order_does_not_affect_result(self) -> None:
        first = evaluate_lane_occupancy(
            anchor_id="shape-1",
            frame_id=200,
            player_positions=[
                player("a", frame_id=200, x_m=15.0, y_m=-30.0),
                player("b", frame_id=200, x_m=10.0, y_m=0.0),
                player("c", frame_id=200, x_m=5.0, y_m=30.0),
            ],
            target_player_ids=["c", "a", "b"],
            required_occupied_lane_count=3,
        )
        second = evaluate_lane_occupancy(
            anchor_id="shape-1",
            frame_id=200,
            player_positions=[
                player("c", frame_id=200, x_m=5.0, y_m=30.0),
                player("a", frame_id=200, x_m=15.0, y_m=-30.0),
                player("b", frame_id=200, x_m=10.0, y_m=0.0),
            ],
            target_player_ids=["b", "c", "a"],
            required_occupied_lane_count=3,
        )

        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(PASS, first.status)

    def test_left_right_lane_naming_is_stable_under_x_mirroring(self) -> None:
        forward = evaluate_lane_occupancy(
            player_positions=[
                player("left", x_m=40.0, y_m=-30.0),
                player("right", x_m=40.0, y_m=30.0),
            ],
            target_player_ids=["left", "right"],
        )
        mirrored_x = evaluate_lane_occupancy(
            player_positions=[
                player("left", x_m=-40.0, y_m=-30.0),
                player("right", x_m=-40.0, y_m=30.0),
            ],
            target_player_ids=["left", "right"],
        )

        self.assertEqual(PASS, forward.status)
        self.assertEqual(PASS, mirrored_x.status)
        self.assertEqual(forward.lane_counts, mirrored_x.lane_counts)
        self.assertEqual(
            {assignment.player_id: assignment.lane_id for assignment in forward.player_assignments},
            {assignment.player_id: assignment.lane_id for assignment in mirrored_x.player_assignments},
        )

    def test_invalid_coordinate_is_unknown_and_explicit(self) -> None:
        evaluation = evaluate_lane_occupancy(
            player_positions=[player("a", y_m="bad")],
            target_player_ids=["a"],
            required_lane_ids=[CENTRAL],
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual(LaneOccupancyReason.INVALID_PLAYER_COORDINATES.value, evaluation.reason)
        self.assertEqual(("a",), evaluation.invalid_coordinate_player_ids)
        self.assertEqual(0, evaluation.lane_counts[CENTRAL])

    def test_duplicate_player_id_in_same_frame_is_unknown_and_explicit(self) -> None:
        evaluation = evaluate_lane_occupancy(
            player_positions=[
                player("a", frame_id=10, y_m=-30.0),
                player("a", frame_id=10, y_m=30.0),
            ],
            target_player_ids=["a"],
            frame_id=10,
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual(LaneOccupancyReason.DUPLICATE_PLAYER_POSITION_RECORDS.value, evaluation.reason)
        self.assertEqual(("a",), evaluation.duplicate_player_ids)
        self.assertEqual((), evaluation.player_assignments)

    def test_unknown_required_lane_id_is_unknown_and_explicit(self) -> None:
        evaluation = evaluate_lane_occupancy(
            player_positions=[player("a", y_m=0.0)],
            target_player_ids=["a"],
            required_lane_ids=["INSIDE_LEFT"],
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual(LaneOccupancyReason.UNKNOWN_REQUIRED_LANE_IDS.value, evaluation.reason)
        self.assertEqual(("INSIDE_LEFT",), evaluation.unknown_lane_ids)

    def test_to_dict_is_stable_and_json_compatible(self) -> None:
        evaluation = evaluate_lane_occupancy(
            anchor_id="shape-1",
            frame_id=300,
            player_positions=[player("a", frame_id=300, y_m=-30.0), player("b", frame_id=300, y_m=30.0)],
            target_player_ids=["a", "b"],
            required_lane_ids=[LEFT_WIDE, RIGHT_WIDE],
        )

        first = evaluation.to_dict()
        second = evaluation.to_dict()

        self.assertEqual(first, second)
        self.assertEqual(PASS, first["status"])
        serialized = json.dumps(first, sort_keys=True)
        self.assertIn("LEFT_WIDE", serialized)
        self.assertIn("lane_definitions", serialized)

    def test_runtime_helper_does_not_treat_unknown_outfield_ids_as_all_players(self) -> None:
        positions = pd.DataFrame(
            [
                {
                    "frame_id": 10,
                    "entity_type": "player",
                    "team_role": "home",
                    "entity_id": "goalkeeper-or-unknown",
                    "x_m": 0.0,
                    "y_m": 0.0,
                }
            ]
        )

        self.assertEqual(
            [],
            observed_outfield_positions_at_frame(
                positions,
                frame_id=10,
                team_role="home",
                outfield_ids=set(),
            ),
        )


def player(player_id: str, *, frame_id: int = 1, x_m: object = 0.0, y_m: object) -> dict[str, object]:
    return {
        "player_id": player_id,
        "frame_id": frame_id,
        "team_role": "home",
        "x_m": x_m,
        "y_m": y_m,
    }


if __name__ == "__main__":
    unittest.main()
