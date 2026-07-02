import unittest

from tqe.runtime.local_number_relation import (
    FAIL,
    PASS,
    UNKNOWN,
    LocalNumberConfig,
    LocalNumberReason,
    evaluate_local_number_relation,
)


class LocalNumberRelationKernelTest(unittest.TestCase):
    def test_pass_when_local_difference_meets_threshold(self) -> None:
        evaluation = evaluate_local_number_relation(
            anchor_id="a1",
            anchor_frame_id=10,
            evaluation_frame_id=10,
            reference_point={"x_m": 0.0, "y_m": 0.0},
            perspective_positions=[
                player("p1", 10, 0.0, 0.0),
                player("p2", 10, 3.0, 4.0),
                player("p3", 10, 20.0, 0.0),
            ],
            defending_positions=[
                player("d1", 10, 7.0, 0.0),
                player("d2", 10, 20.0, 0.0),
            ],
            config=LocalNumberConfig(radius_m=10.0, minimum_difference=1),
        )

        self.assertEqual(PASS, evaluation.status)
        self.assertEqual(LocalNumberReason.REQUIREMENT_SATISFIED.value, evaluation.reason)
        self.assertEqual(2, evaluation.perspective_count)
        self.assertEqual(1, evaluation.defending_count)
        self.assertEqual(1, evaluation.local_number_difference)
        self.assertEqual(("p1", "p2"), evaluation.perspective_in_region_player_ids)
        self.assertEqual(("d1",), evaluation.defending_in_region_player_ids)
        self.assertEqual("COMPLETE", evaluation.coverage_status)

    def test_fail_when_complete_evidence_does_not_meet_threshold(self) -> None:
        evaluation = evaluate_local_number_relation(
            anchor_frame_id=20,
            evaluation_frame_id=20,
            reference_point=(0.0, 0.0),
            perspective_positions=[player("p1", 20, 0.0, 0.0)],
            defending_positions=[
                player("d1", 20, 1.0, 0.0),
                player("d2", 20, 2.0, 0.0),
            ],
            config=LocalNumberConfig(radius_m=10.0, minimum_difference=0),
        )

        self.assertEqual(FAIL, evaluation.status)
        self.assertEqual(LocalNumberReason.REQUIREMENT_NOT_MET.value, evaluation.reason)
        self.assertEqual(1, evaluation.perspective_count)
        self.assertEqual(2, evaluation.defending_count)
        self.assertEqual(-1, evaluation.local_number_difference)
        self.assertEqual("COMPLETE", evaluation.coverage_status)

    def test_unknown_when_reference_point_missing(self) -> None:
        evaluation = evaluate_local_number_relation(
            anchor_frame_id=30,
            evaluation_frame_id=30,
            reference_point=None,
            perspective_positions=[player("p1", 30, 0.0, 0.0)],
            defending_positions=[],
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual(LocalNumberReason.REFERENCE_POINT_MISSING.value, evaluation.reason)

    def test_unknown_when_expected_player_evidence_is_missing(self) -> None:
        evaluation = evaluate_local_number_relation(
            anchor_frame_id=40,
            evaluation_frame_id=40,
            reference_point=(0.0, 0.0),
            perspective_player_ids=["p1", "p2"],
            defending_player_ids=["d1"],
            perspective_positions=[player("p1", 40, 0.0, 0.0)],
            defending_positions=[player("d1", 40, 20.0, 0.0)],
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual(LocalNumberReason.MISSING_PLAYER_EVIDENCE.value, evaluation.reason)
        self.assertEqual(("p2",), evaluation.missing_perspective_player_ids)

    def test_unknown_when_coordinates_are_invalid(self) -> None:
        evaluation = evaluate_local_number_relation(
            anchor_frame_id=50,
            evaluation_frame_id=50,
            reference_point=(0.0, 0.0),
            perspective_positions=[player("p1", 50, None, 0.0)],
            defending_positions=[player("d1", 50, 20.0, 0.0)],
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual(LocalNumberReason.INVALID_PLAYER_COORDINATES.value, evaluation.reason)
        self.assertEqual(("p1",), evaluation.invalid_coordinate_player_ids)

    def test_duplicate_side_player_frame_records_are_unknown(self) -> None:
        evaluation = evaluate_local_number_relation(
            anchor_frame_id=60,
            evaluation_frame_id=60,
            reference_point=(0.0, 0.0),
            perspective_positions=[
                player("p1", 60, 0.0, 0.0),
                player("p1", 60, 1.0, 0.0),
            ],
            defending_positions=[player("d1", 60, 20.0, 0.0)],
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual(LocalNumberReason.DUPLICATE_PLAYER_POSITION_RECORDS.value, evaluation.reason)
        self.assertEqual(("p1",), evaluation.duplicate_perspective_player_ids)

    def test_exact_radius_boundary_is_included(self) -> None:
        evaluation = evaluate_local_number_relation(
            anchor_frame_id=70,
            evaluation_frame_id=70,
            reference_point=(0.0, 0.0),
            perspective_positions=[player("p1", 70, 3.0, 4.0)],
            defending_positions=[],
            config=LocalNumberConfig(radius_m=5.0, minimum_difference=1),
        )

        self.assertEqual(PASS, evaluation.status)
        self.assertEqual(("p1",), evaluation.perspective_in_region_player_ids)
        self.assertAlmostEqual(5.0, evaluation.per_player_evidence[0].distance_to_reference_m)

    def test_ordering_is_deterministic(self) -> None:
        first = evaluate_local_number_relation(
            anchor_id="a",
            anchor_frame_id=80,
            evaluation_frame_id=80,
            reference_point=(0.0, 0.0),
            perspective_positions=[
                player("p2", 80, 1.0, 0.0),
                player("p1", 80, 0.0, 0.0),
            ],
            defending_positions=[
                player("d2", 80, 20.0, 0.0),
                player("d1", 80, 2.0, 0.0),
            ],
        )
        second = evaluate_local_number_relation(
            anchor_id="a",
            anchor_frame_id=80,
            evaluation_frame_id=80,
            reference_point=(0.0, 0.0),
            perspective_positions=[
                player("p1", 80, 0.0, 0.0),
                player("p2", 80, 1.0, 0.0),
            ],
            defending_positions=[
                player("d1", 80, 2.0, 0.0),
                player("d2", 80, 20.0, 0.0),
            ],
        )

        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(("p1", "p2"), first.perspective_player_ids)

    def test_player_on_both_sides_is_unknown_not_double_counted(self) -> None:
        # A 1v1 where the same player id appears on both sides must not become
        # a 2v1 PASS; contradictory side membership is UNKNOWN.
        evaluation = evaluate_local_number_relation(
            anchor_frame_id=100,
            evaluation_frame_id=100,
            reference_point=(0.0, 0.0),
            perspective_positions=[
                player("p1", 100, 0.0, 0.0),
                player("shared", 100, 1.0, 0.0),
            ],
            defending_positions=[
                player("shared", 100, 1.0, 0.0),
                player("d1", 100, 2.0, 0.0),
            ],
            config=LocalNumberConfig(radius_m=10.0, minimum_difference=1),
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual(LocalNumberReason.PLAYER_ON_BOTH_SIDES.value, evaluation.reason)
        self.assertIsNone(evaluation.perspective_count)
        self.assertIsNone(evaluation.defending_count)
        self.assertIsNone(evaluation.local_number_difference)

    def test_overlap_detected_from_explicit_player_id_declarations(self) -> None:
        evaluation = evaluate_local_number_relation(
            anchor_frame_id=110,
            evaluation_frame_id=110,
            reference_point=(0.0, 0.0),
            perspective_player_ids=["p1", "shared"],
            defending_player_ids=["shared", "d1"],
            perspective_positions=[
                player("p1", 110, 0.0, 0.0),
                player("shared", 110, 1.0, 0.0),
            ],
            defending_positions=[
                player("shared", 110, 1.0, 0.0),
                player("d1", 110, 2.0, 0.0),
            ],
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual(LocalNumberReason.PLAYER_ON_BOTH_SIDES.value, evaluation.reason)

    def test_disjoint_sides_are_unaffected_by_overlap_guard(self) -> None:
        evaluation = evaluate_local_number_relation(
            anchor_frame_id=120,
            evaluation_frame_id=120,
            reference_point=(0.0, 0.0),
            perspective_positions=[
                player("p1", 120, 0.0, 0.0),
                player("p2", 120, 1.0, 0.0),
            ],
            defending_positions=[player("d1", 120, 2.0, 0.0)],
            config=LocalNumberConfig(radius_m=10.0, minimum_difference=1),
        )

        self.assertEqual(PASS, evaluation.status)
        self.assertEqual(2, evaluation.perspective_count)
        self.assertEqual(1, evaluation.defending_count)

    def test_invalid_config_fails_closed(self) -> None:
        evaluation = evaluate_local_number_relation(
            anchor_frame_id=90,
            evaluation_frame_id=90,
            reference_point=(0.0, 0.0),
            perspective_positions=[player("p1", 90, 0.0, 0.0)],
            defending_positions=[],
            config=LocalNumberConfig(radius_m=-1.0),
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual(LocalNumberReason.INVALID_CONFIG.value, evaluation.reason)
        self.assertEqual(("radius_m",), evaluation.config_evidence.invalid_config_fields)


def player(player_id: str, frame_id: int, x_m: float | None, y_m: float | None) -> dict[str, object]:
    return {
        "player_id": player_id,
        "frame_id": frame_id,
        "x_m": x_m,
        "y_m": y_m,
    }


if __name__ == "__main__":
    unittest.main()
