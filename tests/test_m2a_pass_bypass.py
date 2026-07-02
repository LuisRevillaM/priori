import unittest
from pathlib import Path

import pandas as pd

from tqe.runtime.controlled_pass import ControlledPassOutput
from tqe.runtime.pass_bypass import (
    ActiveInterval,
    PassBypassConfig,
    evaluate_episode,
    evaluate_pass_bypass_measurements,
)

from tests.support.canonical_data import requires_canonical_data


@requires_canonical_data
class M2APassBypassRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.output = evaluate_pass_bypass_measurements(
            canonical_root=Path("data/canonical/v1"),
            match_ids=("J03WOY",),
            periods=("firstHalf", "secondHalf"),
        )

    def test_bypass_measurements_match_controlled_pass_anchors(self) -> None:
        summary = self.output.summary
        self.assertEqual(639, summary["controlled_anchor_evaluation_count"])
        self.assertEqual(453, summary["evaluation_status_counts"].get("PASS", 0))
        self.assertEqual(186, summary["evaluation_status_counts"].get("UNKNOWN", 0))
        self.assertEqual(
            summary["controlled_anchor_evaluation_count"],
            summary["bypass_anchor_evaluation_count"],
        )
        self.assertGreater(summary["evaluation_status_counts"].get("PASS", 0), 0)
        self.assertGreaterEqual(summary["max_opponents_bypassed_count"], 5)

    def test_complete_measurements_use_ten_defending_outfield_players(self) -> None:
        pass_rows = [
            item
            for item in self.output.anchor_evaluations
            if item["evaluation_status"] == "PASS"
        ]
        self.assertTrue(pass_rows)
        self.assertTrue(all(len(item["expected_active_opponent_ids"]) == 10 for item in pass_rows))
        self.assertTrue(all(len(item["evaluated_opponent_ids"]) == 10 for item in pass_rows))
        self.assertTrue(all(item["missing_active_opponent_ids"] == () for item in pass_rows))

    def test_unknown_rows_are_not_silent_zero_counts(self) -> None:
        unknown = [
            item
            for item in self.output.anchor_evaluations
            if item["evaluation_status"] == "UNKNOWN"
        ]
        self.assertTrue(unknown)
        self.assertTrue(all(item["failure_reason"] for item in unknown))
        self.assertIn("controlled_pass_not_proven", {item["failure_reason"] for item in unknown})

    def test_measurement_does_not_emit_high_bypass_classification(self) -> None:
        serialized = str(self.output.summary) + str(self.output.anchor_evaluations[:10])
        self.assertNotIn("HIGH_BYPASS_COMPLETED_PASS", serialized)
        self.assertNotIn("classification", serialized.lower())
        self.assertNotIn("gte_5", serialized.lower())

    def test_scope_can_use_another_canonical_match(self) -> None:
        output = evaluate_pass_bypass_measurements(
            canonical_root=Path("data/canonical/v1"),
            match_ids=("J03WPY",),
            periods=("firstHalf",),
        )

        self.assertEqual(["J03WPY"], output.accepted_scope["match_ids"])
        self.assertGreater(output.summary["controlled_anchor_evaluation_count"], 0)

    def test_scope_is_fail_closed_to_accepted_period(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "accepted only"):
            evaluate_pass_bypass_measurements(
                canonical_root=Path("data/canonical/v1"),
                match_ids=("J03WOY",),
                periods=("thirdHalf",),
            )

    def test_injected_controlled_passes_are_scope_checked(self) -> None:
        injected = ControlledPassOutput(
            schema_version="test",
            capability="controlled_pass_episode",
            capability_version="test",
            status="pass",
            accepted_scope={},
            config={},
            summary={},
            episodes=[],
            anchor_evaluations=[
                {
                    "match_id": "J03WN1",
                    "period": "firstHalf",
                    "controlled_pass_status": "UNKNOWN",
                    "pass_episode_id": "x",
                    "anchor_id": "x",
                    "team_role": "home",
                    "passer_id": "p",
                    "receiver_id": "r",
                    "event_row_index": 1,
                    "event_anchor_frame_id": 10000,
                    "physical_release_frame_id": None,
                    "controlled_reception_frame_id": None,
                    "forward_progression_m": None,
                }
            ],
            non_match_examples=[],
        )
        injected.anchor_evaluations[0]["period"] = "thirdHalf"
        with self.assertRaisesRegex(RuntimeError, "outside M2A-S1B period scope"):
            evaluate_pass_bypass_measurements(
                canonical_root=Path("data/canonical/v1"),
                controlled_passes=injected,
                match_ids=("J03WOY",),
                periods=("firstHalf",),
            )

    def test_missing_expected_active_opponent_stays_unknown(self) -> None:
        evaluation = evaluate_episode(
            episode=fixture_episode(),
            positions=fixture_positions(player_ids=("def1",)),
            active_timeline=[
                ActiveInterval("away", "def1", False, 10, 30),
                ActiveInterval("away", "def2", False, 10, 30),
            ],
            orientation=fixture_orientation(),
            config=PassBypassConfig(),
        )

        self.assertEqual("UNKNOWN", evaluation["evaluation_status"])
        self.assertEqual("expected_active_opponent_tracking_missing", evaluation["failure_reason"])
        self.assertEqual(("def2",), evaluation["missing_active_opponent_ids"])

    def test_active_change_inside_window_stays_unknown_even_when_endpoints_match(self) -> None:
        evaluation = evaluate_episode(
            episode=fixture_episode(),
            positions=fixture_positions(player_ids=("def1", "def2")),
            active_timeline=[
                ActiveInterval("away", "def1", False, 10, 30),
                ActiveInterval("away", "def2", False, 10, 30),
                ActiveInterval("home", "att_sub", False, 15, 30),
            ],
            orientation=fixture_orientation(),
            config=PassBypassConfig(),
        )

        self.assertEqual("UNKNOWN", evaluation["evaluation_status"])
        self.assertEqual("active_player_set_changed_during_pass", evaluation["failure_reason"])
        self.assertTrue(evaluation["active_changes_inside_window"])

    def test_unknown_goalkeeper_metadata_stays_unknown(self) -> None:
        evaluation = evaluate_episode(
            episode=fixture_episode(),
            positions=fixture_positions(player_ids=("def1", "def2")),
            active_timeline=[
                ActiveInterval("away", "def1", False, 10, 30),
                ActiveInterval("away", "def2", None, 10, 30),
            ],
            orientation=fixture_orientation(),
            config=PassBypassConfig(),
        )

        self.assertEqual("UNKNOWN", evaluation["evaluation_status"])
        self.assertEqual("goalkeeper_metadata_missing", evaluation["failure_reason"])


def fixture_episode() -> dict[str, object]:
    return {
        "anchor_id": "anchor",
        "pass_episode_id": "episode",
        "match_id": "fixture",
        "period": "firstHalf",
        "team_role": "home",
        "passer_id": "passer",
        "receiver_id": "receiver",
        "event_row_index": 1,
        "event_anchor_frame_id": 10,
        "physical_release_frame_id": 10,
        "controlled_reception_frame_id": 20,
        "release_ball_x_m": 0.0,
        "release_ball_y_m": 0.0,
        "reception_ball_x_m": 10.0,
        "reception_ball_y_m": 0.0,
        "forward_progression_m": 10.0,
    }


def fixture_positions(*, player_ids: tuple[str, ...]) -> pd.DataFrame:
    rows = []
    for frame_id, x_m in ((10, 5.0), (20, 0.0)):
        for player_id in player_ids:
            rows.append(
                {
                    "match_id": "fixture",
                    "period": "firstHalf",
                    "frame_id": frame_id,
                    "team_role": "away",
                    "entity_id": player_id,
                    "entity_type": "player",
                    "x_m": x_m,
                    "y_m": 0.0,
                }
            )
    return pd.DataFrame(rows)


def fixture_orientation() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "match_id": "fixture",
                "period": "firstHalf",
                "team_role": "home",
                "attack_x_sign": 1,
            }
        ]
    )


if __name__ == "__main__":
    unittest.main()
