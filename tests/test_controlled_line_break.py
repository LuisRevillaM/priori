import unittest

from tqe.runtime.controlled_line_break import (
    AHEAD_OF_LINE,
    BEHIND_LINE,
    FAIL,
    LEVEL_WITH_LINE,
    PASS,
    UNKNOWN,
    ControlledLineBreakConfig,
    ControlledPassEvidence,
    ObservedLineEvidence,
    RelativePositionEvidence,
    evaluate_controlled_line_break_episode,
)


class ControlledLineBreakEpisodeTest(unittest.TestCase):
    def test_pass_when_release_is_not_beyond_and_reception_is_ahead(self) -> None:
        evaluation = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(
                anchor_id="pass-1",
                pass_episode_id="episode-1",
                evidence_id="pass-evidence-1",
                release_anchor_frame_id=10,
                reception_anchor_frame_id=20,
            ),
            observed_line_evidence=ObservedLineEvidence(
                line_x_m=10.0,
                attacking_direction=1,
                anchor_id="line-1",
                relation_id="line-relation-1",
                evidence_id="line-evidence-1",
                anchor_frame_id=12,
            ),
            release_relative_position_evidence=RelativePositionEvidence(
                status=BEHIND_LINE,
                relation_id="release-relation-1",
                evidence_id="release-evidence-1",
                anchor_frame_id=10,
            ),
            reception_relative_position_evidence=RelativePositionEvidence(
                status=AHEAD_OF_LINE,
                relation_id="reception-relation-1",
                evidence_id="reception-evidence-1",
                anchor_frame_id=20,
            ),
        )

        self.assertEqual(PASS, evaluation.status)
        self.assertEqual("observed_controlled_pass_crossed_supplied_line", evaluation.reason)
        self.assertEqual("controlled_line_break:pass-1:line-1", evaluation.anchor_id)
        self.assertEqual("episode-1", evaluation.pass_episode_id)
        self.assertEqual("line-relation-1", evaluation.line_relation_id)
        self.assertEqual("line-evidence-1", evaluation.line_evidence_id)
        self.assertEqual("release-relation-1", evaluation.release_relation_id)
        self.assertEqual("release-evidence-1", evaluation.release_evidence_id)
        self.assertEqual("reception-relation-1", evaluation.reception_relation_id)
        self.assertEqual("reception-evidence-1", evaluation.reception_evidence_id)

    def test_fails_when_already_ahead_at_release(self) -> None:
        evaluation = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(anchor_id="pass-1"),
            observed_line_evidence=line(),
            release_relative_position_evidence=RelativePositionEvidence(status=AHEAD_OF_LINE),
            reception_relative_position_evidence=RelativePositionEvidence(status=AHEAD_OF_LINE),
        )

        self.assertEqual(FAIL, evaluation.status)
        self.assertEqual("release_already_ahead_of_line", evaluation.reason)

    def test_fails_when_still_behind_at_reception(self) -> None:
        evaluation = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(anchor_id="pass-1"),
            observed_line_evidence=line(),
            release_relative_position_evidence=RelativePositionEvidence(status=BEHIND_LINE),
            reception_relative_position_evidence=RelativePositionEvidence(status=BEHIND_LINE),
        )

        self.assertEqual(FAIL, evaluation.status)
        self.assertEqual("reception_not_ahead_of_line", evaluation.reason)

    def test_fails_for_behind_to_level_only(self) -> None:
        evaluation = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(anchor_id="pass-1"),
            observed_line_evidence=line(),
            release_relative_position_evidence=RelativePositionEvidence(status=BEHIND_LINE),
            reception_relative_position_evidence=RelativePositionEvidence(status=LEVEL_WITH_LINE),
        )

        self.assertEqual(FAIL, evaluation.status)
        self.assertEqual("reception_not_ahead_of_line", evaluation.reason)

    def test_definitive_upstream_failures_remain_failures(self) -> None:
        no_pass = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(anchor_id="pass-1", status=FAIL),
            observed_line_evidence=line(),
            release_relative_position_evidence=RelativePositionEvidence(status=BEHIND_LINE),
            reception_relative_position_evidence=RelativePositionEvidence(status=AHEAD_OF_LINE),
        )
        no_line = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(anchor_id="pass-1"),
            observed_line_evidence=ObservedLineEvidence(line_x_m=10.0, attacking_direction=1, status=FAIL),
            release_relative_position_evidence=RelativePositionEvidence(status=BEHIND_LINE),
            reception_relative_position_evidence=RelativePositionEvidence(status=AHEAD_OF_LINE),
        )

        self.assertEqual(FAIL, no_pass.status)
        self.assertEqual("controlled_pass_not_established", no_pass.reason)
        self.assertEqual(FAIL, no_line.status)
        self.assertEqual("line_not_observed", no_line.reason)

    def test_unknown_when_required_evidence_is_missing(self) -> None:
        cases = [
            (
                "controlled_pass_evidence_missing",
                dict(
                    controlled_pass_evidence=None,
                    observed_line_evidence=line(),
                    release_relative_position_evidence=RelativePositionEvidence(status=BEHIND_LINE),
                    reception_relative_position_evidence=RelativePositionEvidence(status=AHEAD_OF_LINE),
                ),
            ),
            (
                "line_evidence_missing",
                dict(
                    controlled_pass_evidence=ControlledPassEvidence(anchor_id="pass-1"),
                    observed_line_evidence=None,
                    release_relative_position_evidence=RelativePositionEvidence(status=BEHIND_LINE),
                    reception_relative_position_evidence=RelativePositionEvidence(status=AHEAD_OF_LINE),
                ),
            ),
            (
                "release_relation_evidence_missing",
                dict(
                    controlled_pass_evidence=ControlledPassEvidence(anchor_id="pass-1"),
                    observed_line_evidence=line(),
                    release_relative_position_evidence=None,
                    reception_relative_position_evidence=RelativePositionEvidence(status=AHEAD_OF_LINE),
                ),
            ),
            (
                "reception_relation_evidence_missing",
                dict(
                    controlled_pass_evidence=ControlledPassEvidence(anchor_id="pass-1"),
                    observed_line_evidence=line(),
                    release_relative_position_evidence=RelativePositionEvidence(status=BEHIND_LINE),
                    reception_relative_position_evidence=None,
                ),
            ),
        ]

        for expected_reason, kwargs in cases:
            with self.subTest(expected_reason):
                evaluation = evaluate_controlled_line_break_episode(**kwargs)
                self.assertEqual(UNKNOWN, evaluation.status)
                self.assertEqual(expected_reason, evaluation.reason)

    def test_unknown_when_line_or_direction_is_missing(self) -> None:
        missing_line = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(anchor_id="pass-1"),
            observed_line_evidence=ObservedLineEvidence(line_x_m=None, attacking_direction=1),
            release_relative_position_evidence=RelativePositionEvidence(status=BEHIND_LINE),
            reception_relative_position_evidence=RelativePositionEvidence(status=AHEAD_OF_LINE),
        )
        missing_direction = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(anchor_id="pass-1"),
            observed_line_evidence=ObservedLineEvidence(line_x_m=10.0, attacking_direction=None),
            release_relative_position_evidence=RelativePositionEvidence(status=BEHIND_LINE),
            reception_relative_position_evidence=RelativePositionEvidence(status=AHEAD_OF_LINE),
        )

        self.assertEqual(UNKNOWN, missing_line.status)
        self.assertEqual("line_x_missing", missing_line.reason)
        self.assertEqual(UNKNOWN, missing_direction.status)
        self.assertEqual("attacking_direction_invalid", missing_direction.reason)

    def test_unknown_for_unknown_or_conflicting_relation_evidence(self) -> None:
        unknown_relation = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(anchor_id="pass-1"),
            observed_line_evidence=line(),
            release_relative_position_evidence=RelativePositionEvidence(status=UNKNOWN),
            reception_relative_position_evidence=RelativePositionEvidence(status=AHEAD_OF_LINE),
        )
        conflicting_relation = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(anchor_id="pass-1"),
            observed_line_evidence=line(),
            release_relative_position_evidence=RelativePositionEvidence(
                status=BEHIND_LINE,
                line_x_m=11.0,
            ),
            reception_relative_position_evidence=RelativePositionEvidence(status=AHEAD_OF_LINE),
        )

        self.assertEqual(UNKNOWN, unknown_relation.status)
        self.assertEqual("relation_position_unknown", unknown_relation.reason)
        self.assertEqual(UNKNOWN, conflicting_relation.status)
        self.assertEqual("relation_line_conflict", conflicting_relation.reason)

    def test_buffer_behavior_uses_supplied_line_and_signed_distances(self) -> None:
        config = ControlledLineBreakConfig(line_buffer_m=0.5)

        level_reception = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(anchor_id="pass-1"),
            observed_line_evidence=line(),
            release_relative_position_evidence=RelativePositionEvidence(signed_distance_to_line_m=-0.6),
            reception_relative_position_evidence=RelativePositionEvidence(signed_distance_to_line_m=0.5),
            config=config,
        )
        ahead_reception = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(anchor_id="pass-1"),
            observed_line_evidence=line(),
            release_relative_position_evidence=RelativePositionEvidence(signed_distance_to_line_m=-0.5),
            reception_relative_position_evidence=RelativePositionEvidence(signed_distance_to_line_m=0.500001),
            config=config,
        )

        self.assertEqual(FAIL, level_reception.status)
        self.assertEqual(LEVEL_WITH_LINE, level_reception.reception_status)
        self.assertEqual(PASS, ahead_reception.status)
        self.assertEqual(LEVEL_WITH_LINE, ahead_reception.release_status)
        self.assertTrue(ahead_reception.release_level_counts_as_not_yet_beyond)

    def test_release_level_can_be_disallowed_by_config(self) -> None:
        evaluation = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(anchor_id="pass-1"),
            observed_line_evidence=line(),
            release_relative_position_evidence=RelativePositionEvidence(status=LEVEL_WITH_LINE),
            reception_relative_position_evidence=RelativePositionEvidence(status=AHEAD_OF_LINE),
            config=ControlledLineBreakConfig(release_level_counts_as_not_yet_beyond=False),
        )

        self.assertEqual(FAIL, evaluation.status)
        self.assertEqual("release_level_not_accepted", evaluation.reason)

    def test_reception_before_release_is_temporally_impossible_and_unknown(self) -> None:
        # Geometry that would otherwise PASS must not survive temporally
        # impossible input evidence (reception frame before release frame).
        evaluation = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(
                anchor_id="pass-1",
                release_anchor_frame_id=100,
                reception_anchor_frame_id=40,
            ),
            observed_line_evidence=line(),
            release_relative_position_evidence=RelativePositionEvidence(status=BEHIND_LINE),
            reception_relative_position_evidence=RelativePositionEvidence(status=AHEAD_OF_LINE),
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual("reception_before_release", evaluation.reason)

    def test_reception_before_release_also_blocks_fail_side_geometry(self) -> None:
        # The temporal contradiction poisons the whole episode: it must not
        # surface as a positively observed FAIL either.
        evaluation = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(
                anchor_id="pass-1",
                release_anchor_frame_id=100,
                reception_anchor_frame_id=40,
            ),
            observed_line_evidence=line(),
            release_relative_position_evidence=RelativePositionEvidence(status=AHEAD_OF_LINE),
            reception_relative_position_evidence=RelativePositionEvidence(status=AHEAD_OF_LINE),
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual("reception_before_release", evaluation.reason)

    def test_temporal_order_boundaries_and_relation_frame_sources(self) -> None:
        equal_frames = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(
                anchor_id="pass-1",
                release_anchor_frame_id=100,
                reception_anchor_frame_id=100,
            ),
            observed_line_evidence=line(),
            release_relative_position_evidence=RelativePositionEvidence(status=BEHIND_LINE),
            reception_relative_position_evidence=RelativePositionEvidence(status=AHEAD_OF_LINE),
        )
        ordered_via_relations = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(anchor_id="pass-1"),
            observed_line_evidence=line(),
            release_relative_position_evidence=RelativePositionEvidence(
                status=BEHIND_LINE,
                anchor_frame_id=100,
            ),
            reception_relative_position_evidence=RelativePositionEvidence(
                status=AHEAD_OF_LINE,
                anchor_frame_id=40,
            ),
        )
        unordered_missing_frame = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(
                anchor_id="pass-1",
                release_anchor_frame_id=100,
            ),
            observed_line_evidence=line(),
            release_relative_position_evidence=RelativePositionEvidence(status=BEHIND_LINE),
            reception_relative_position_evidence=RelativePositionEvidence(status=AHEAD_OF_LINE),
        )

        self.assertEqual(PASS, equal_frames.status)
        self.assertEqual(UNKNOWN, ordered_via_relations.status)
        self.assertEqual("reception_before_release", ordered_via_relations.reason)
        self.assertEqual(PASS, unordered_missing_frame.status)

    def test_mirrored_attacking_direction_preserves_result(self) -> None:
        forward = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(anchor_id="pass-1"),
            observed_line_evidence=ObservedLineEvidence(line_x_m=10.0, attacking_direction=1),
            release_relative_position_evidence=RelativePositionEvidence(entity_position=(8.0, 0.0)),
            reception_relative_position_evidence=RelativePositionEvidence(entity_position=(12.0, 0.0)),
        )
        mirrored = evaluate_controlled_line_break_episode(
            controlled_pass_evidence=ControlledPassEvidence(anchor_id="pass-1"),
            observed_line_evidence=ObservedLineEvidence(line_x_m=-10.0, attacking_direction=-1),
            release_relative_position_evidence=RelativePositionEvidence(entity_position=(-8.0, 0.0)),
            reception_relative_position_evidence=RelativePositionEvidence(entity_position=(-12.0, 0.0)),
        )

        self.assertEqual(PASS, forward.status)
        self.assertEqual(forward.status, mirrored.status)
        self.assertEqual(forward.release_status, mirrored.release_status)
        self.assertEqual(forward.reception_status, mirrored.reception_status)
        self.assertAlmostEqual(forward.release_signed_distance_to_line_m, mirrored.release_signed_distance_to_line_m)
        self.assertAlmostEqual(forward.reception_signed_distance_to_line_m, mirrored.reception_signed_distance_to_line_m)

    def test_relative_evidence_selection_is_deterministic_under_record_order(self) -> None:
        first = evaluate_controlled_line_break_episode(
            controlled_pass_evidence={"anchor_id": "pass-1", "status": PASS},
            observed_line_evidence={"anchor_id": "line-1", "line_x_m": 10.0, "attacking_direction": 1},
            relative_position_evidence=[
                {"phase": "reception", "relative_position_status": AHEAD_OF_LINE, "relation_id": "reception-relation-1"},
                {"phase": "release", "relative_position_status": BEHIND_LINE, "relation_id": "release-relation-1"},
            ],
        )
        second = evaluate_controlled_line_break_episode(
            controlled_pass_evidence={"anchor_id": "pass-1", "status": PASS},
            observed_line_evidence={"anchor_id": "line-1", "line_x_m": 10.0, "attacking_direction": 1},
            relative_position_evidence=[
                {"phase": "release", "relative_position_status": BEHIND_LINE, "relation_id": "release-relation-1"},
                {"phase": "reception", "relative_position_status": AHEAD_OF_LINE, "relation_id": "reception-relation-1"},
            ],
        )

        self.assertEqual(PASS, first.status)
        self.assertEqual(first.to_dict(), second.to_dict())


def line() -> ObservedLineEvidence:
    return ObservedLineEvidence(line_x_m=10.0, attacking_direction=1, anchor_id="line-1")


if __name__ == "__main__":
    unittest.main()
