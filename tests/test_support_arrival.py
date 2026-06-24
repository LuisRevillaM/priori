import json
import unittest

from tqe.runtime.support_arrival import (
    AHEAD_OF_BALL_OPTION,
    BEHIND_BALL_OUTLET,
    FAIL,
    PASS,
    UNKNOWN,
    SupportArrivalConfig,
    SupportArrivalReason,
    evaluate_support_arrival_relation,
)


class SupportArrivalRelationKernelTest(unittest.TestCase):
    def test_positive_arrival_within_window_and_duration(self) -> None:
        evaluation = evaluate_support_arrival_relation(
            anchor_id="pass-1",
            anchor_frame_id=10,
            reference_point={"x_m": 0.0, "y_m": 0.0},
            candidate_player_ids=["support-1"],
            candidate_positions=[
                player("support-1", frame_id=10, x_m=8.0),
                player("support-1", frame_id=11, x_m=2.0),
                player("support-1", frame_id=12, x_m=2.0),
                player("support-1", frame_id=13, x_m=2.0),
            ],
            analysis_rate_hz=2,
            config=SupportArrivalConfig(
                maximum_arrival_seconds=1.0,
                minimum_duration_seconds=0.5,
                maximum_support_distance_m=3.0,
            ),
        )

        self.assertEqual(PASS, evaluation.status)
        self.assertEqual(SupportArrivalReason.REQUIREMENT_SATISFIED.value, evaluation.reason)
        self.assertEqual("pass-1", evaluation.anchor_id)
        self.assertEqual(10, evaluation.support_window_start_frame_id)
        self.assertEqual(13, evaluation.support_window_end_frame_id)
        self.assertEqual(("support-1",), evaluation.supporting_player_ids)
        self.assertEqual(11, evaluation.first_arrival_frame_id)
        self.assertAlmostEqual(0.5, evaluation.first_arrival_seconds_after_anchor)
        self.assertAlmostEqual(0.5, evaluation.support_duration_seconds)
        self.assertEqual("COMPLETE", evaluation.coverage_status)

    def test_fails_when_full_window_evaluated_and_not_enough_support_arrives(self) -> None:
        evaluation = evaluate_support_arrival_relation(
            anchor_frame_id=20,
            reference_point=(0.0, 0.0),
            candidate_player_ids=["support-1", "support-2"],
            candidate_positions=[
                player("support-1", frame_id=20, x_m=8.0),
                player("support-1", frame_id=21, x_m=8.0),
                player("support-1", frame_id=22, x_m=8.0),
                player("support-2", frame_id=20, x_m=9.0),
                player("support-2", frame_id=21, x_m=9.0),
                player("support-2", frame_id=22, x_m=9.0),
            ],
            analysis_rate_hz=2,
            config=SupportArrivalConfig(
                maximum_arrival_seconds=1.0,
                minimum_duration_seconds=0.0,
                maximum_support_distance_m=3.0,
                minimum_supporting_players=1,
            ),
        )

        self.assertEqual(FAIL, evaluation.status)
        self.assertEqual(SupportArrivalReason.REQUIREMENT_NOT_MET.value, evaluation.reason)
        self.assertEqual("COMPLETE", evaluation.coverage_status)
        self.assertEqual((), evaluation.supporting_player_ids)
        self.assertTrue(all(item.status == FAIL for item in evaluation.per_player_evidence))

    def test_unknown_when_missing_candidate_frame_could_change_answer(self) -> None:
        evaluation = evaluate_support_arrival_relation(
            anchor_frame_id=30,
            reference_point=(0.0, 0.0),
            candidate_player_ids=["support-1"],
            candidate_positions=[
                player("support-1", frame_id=30, x_m=8.0),
                player("support-1", frame_id=32, x_m=8.0),
            ],
            analysis_rate_hz=2,
            config=SupportArrivalConfig(
                maximum_arrival_seconds=1.0,
                minimum_duration_seconds=0.0,
                maximum_support_distance_m=3.0,
            ),
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual(SupportArrivalReason.CANDIDATE_FRAME_EVIDENCE_MISSING.value, evaluation.reason)
        self.assertEqual((31,), evaluation.missing_frame_ids)
        self.assertEqual((31,), evaluation.per_player_evidence[0].missing_frame_ids)

    def test_unknown_when_reference_evidence_is_missing(self) -> None:
        evaluation = evaluate_support_arrival_relation(
            anchor_frame_id=40,
            reference_player_id="ball",
            reference_positions=[
                player("ball", frame_id=40, x_m=0.0),
                player("ball", frame_id=42, x_m=0.0),
            ],
            candidate_player_ids=["support-1"],
            candidate_positions=[
                player("support-1", frame_id=40, x_m=8.0),
                player("support-1", frame_id=41, x_m=2.0),
                player("support-1", frame_id=42, x_m=8.0),
            ],
            analysis_rate_hz=2,
            config=SupportArrivalConfig(
                maximum_arrival_seconds=1.0,
                minimum_duration_seconds=0.0,
                maximum_support_distance_m=3.0,
            ),
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual(SupportArrivalReason.REFERENCE_POSITION_MISSING.value, evaluation.reason)
        self.assertEqual((41,), evaluation.missing_reference_frame_ids)

    def test_boundaries_include_exact_maximum_arrival_and_exact_duration(self) -> None:
        evaluation = evaluate_support_arrival_relation(
            anchor_frame_id=100,
            reference_point=(0.0, 0.0),
            candidate_player_ids=["support-1"],
            candidate_positions=[
                player("support-1", frame_id=100, x_m=8.0),
                player("support-1", frame_id=101, x_m=8.0),
                player("support-1", frame_id=102, x_m=3.0),
                player("support-1", frame_id=103, x_m=3.0),
            ],
            analysis_rate_hz=2,
            config=SupportArrivalConfig(
                maximum_arrival_seconds=1.0,
                minimum_duration_seconds=0.5,
                maximum_support_distance_m=3.0,
            ),
        )

        self.assertEqual(PASS, evaluation.status)
        self.assertEqual(102, evaluation.first_arrival_frame_id)
        self.assertAlmostEqual(1.0, evaluation.first_arrival_seconds_after_anchor)
        self.assertAlmostEqual(0.5, evaluation.support_duration_seconds)
        self.assertEqual((102, 103), evaluation.per_player_evidence[0].qualifying_frame_ids)

    def test_ordering_is_deterministic_for_candidates_and_frames(self) -> None:
        common_kwargs = dict(
            anchor_id="shape-1",
            anchor_frame_id=200,
            reference_point=(0.0, 0.0),
            analysis_rate_hz=2,
            config=SupportArrivalConfig(
                maximum_arrival_seconds=1.0,
                minimum_duration_seconds=0.5,
                maximum_support_distance_m=3.0,
                minimum_supporting_players=2,
            ),
        )
        first = evaluate_support_arrival_relation(
            **common_kwargs,
            candidate_player_ids=["support-b", "support-a"],
            candidate_positions=[
                player("support-b", frame_id=201, x_m=2.0),
                player("support-a", frame_id=200, x_m=8.0),
                player("support-b", frame_id=200, x_m=8.0),
                player("support-a", frame_id=202, x_m=2.0),
                player("support-b", frame_id=202, x_m=2.0),
                player("support-a", frame_id=201, x_m=2.0),
                player("support-a", frame_id=203, x_m=2.0),
                player("support-b", frame_id=203, x_m=2.0),
            ],
        )
        second = evaluate_support_arrival_relation(
            **common_kwargs,
            candidate_player_ids=["support-a", "support-b"],
            candidate_positions=[
                player("support-a", frame_id=203, x_m=2.0),
                player("support-b", frame_id=203, x_m=2.0),
                player("support-b", frame_id=202, x_m=2.0),
                player("support-a", frame_id=201, x_m=2.0),
                player("support-b", frame_id=201, x_m=2.0),
                player("support-a", frame_id=202, x_m=2.0),
                player("support-b", frame_id=200, x_m=8.0),
                player("support-a", frame_id=200, x_m=8.0),
            ],
        )

        self.assertEqual(PASS, first.status)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(("support-a", "support-b"), first.supporting_player_ids)

    def test_invalid_parameter_returns_unknown_with_config_evidence(self) -> None:
        evaluation = evaluate_support_arrival_relation(
            anchor_frame_id=1,
            reference_point=(0.0, 0.0),
            candidate_player_ids=["support-1"],
            candidate_positions=[player("support-1", frame_id=1, x_m=0.0)],
            analysis_rate_hz=2,
            maximum_arrival_seconds=-0.1,
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual(SupportArrivalReason.INVALID_CONFIG.value, evaluation.reason)
        self.assertEqual(("maximum_arrival_seconds",), evaluation.config_evidence.invalid_config_fields)

    def test_duplicate_candidate_frame_returns_unknown_and_identifies_player(self) -> None:
        evaluation = evaluate_support_arrival_relation(
            anchor_frame_id=300,
            reference_point=(0.0, 0.0),
            candidate_player_ids=["support-1"],
            candidate_positions=[
                player("support-1", frame_id=300, x_m=8.0),
                player("support-1", frame_id=300, x_m=2.0),
                player("support-1", frame_id=301, x_m=8.0),
                player("support-1", frame_id=302, x_m=8.0),
            ],
            analysis_rate_hz=2,
            config=SupportArrivalConfig(
                maximum_arrival_seconds=1.0,
                minimum_duration_seconds=0.0,
                maximum_support_distance_m=3.0,
            ),
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual(SupportArrivalReason.DUPLICATE_CANDIDATE_FRAME_RECORDS.value, evaluation.reason)
        self.assertEqual(("support-1",), evaluation.duplicate_candidate_player_ids)
        self.assertEqual((300,), evaluation.per_player_evidence[0].duplicate_frame_ids)

    def test_directional_modes_are_geometric_only(self) -> None:
        behind = evaluate_support_arrival_relation(
            anchor_frame_id=400,
            reference_point=(10.0, 0.0),
            candidate_player_ids=["behind"],
            candidate_positions=[player("behind", frame_id=400, x_m=8.0)],
            analysis_rate_hz=2,
            config=SupportArrivalConfig(
                support_region_mode=BEHIND_BALL_OUTLET,
                maximum_arrival_seconds=0.0,
                minimum_duration_seconds=0.0,
                maximum_support_distance_m=3.0,
                attacking_direction=1,
            ),
        )
        ahead = evaluate_support_arrival_relation(
            anchor_frame_id=400,
            reference_point=(10.0, 0.0),
            candidate_player_ids=["ahead"],
            candidate_positions=[player("ahead", frame_id=400, x_m=12.0)],
            analysis_rate_hz=2,
            config=SupportArrivalConfig(
                support_region_mode=AHEAD_OF_BALL_OPTION,
                maximum_arrival_seconds=0.0,
                minimum_duration_seconds=0.0,
                maximum_support_distance_m=3.0,
                attacking_direction=1,
            ),
        )

        self.assertEqual(PASS, behind.status)
        self.assertEqual(PASS, ahead.status)

    def test_to_dict_is_stable_and_json_compatible(self) -> None:
        evaluation = evaluate_support_arrival_relation(
            anchor_id="pass-2",
            anchor_frame_id=500,
            reference_point={"x": 0.0, "y": 0.0},
            candidate_player_ids=["support-1"],
            candidate_positions=[player("support-1", frame_id=500, x_m=0.0)],
            analysis_rate_hz=2,
            config=SupportArrivalConfig(
                maximum_arrival_seconds=0.0,
                minimum_duration_seconds=0.0,
                maximum_support_distance_m=1.0,
            ),
        )

        first = evaluation.to_dict()
        second = evaluation.to_dict()

        self.assertEqual(first, second)
        self.assertEqual(PASS, first["status"])
        serialized = json.dumps(first, sort_keys=True)
        self.assertIn("support_arrival_requirement_satisfied", serialized)
        self.assertIn("WITHIN_DISTANCE_OF_REFERENCE_POINT", serialized)


def player(player_id: str, *, frame_id: int, x_m: object, y_m: object = 0.0) -> dict[str, object]:
    return {
        "player_id": player_id,
        "frame_id": frame_id,
        "x_m": x_m,
        "y_m": y_m,
        "team_id": "home",
    }


if __name__ == "__main__":
    unittest.main()
