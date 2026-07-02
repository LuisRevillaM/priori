import tempfile
import unittest
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from tqe.runtime.binder import bind_document
from tqe.runtime.bypass import BypassConfig, PlayerPosition, evaluate_opponents_bypassed_by_action
from tqe.runtime.executor import PeriodState, RuntimeParameters, TacticalQueryExecutor
from tqe.runtime.ir import TacticalQueryDocument
from tqe.runtime.relations import (
    CorridorConfig,
    anchor_evaluation_for_result,
    episodes_from_states,
    evaluate_geometric_progressive_corridors,
    evaluate_result_window,
)
from tqe.runtime.values import canonical_anchor_record_id, runtime_value_from_raw


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


class CorridorEpisodeHonestyTest(unittest.TestCase):
    def test_dropout_inside_episode_does_not_bridge_continuity(self) -> None:
        episodes = episodes_from_states(
            fixture_result(outcome_frame_id=120),
            "target",
            [
                pass_state(100),
                pass_state(105),
                unknown_state(110),
                pass_state(115),
                pass_state(120),
            ],
            CorridorConfig(open_after_frames=2, close_after_frames=2, analysis_rate_hz=5),
        )

        self.assertEqual(2, len(episodes))
        self.assertEqual((100, 105), (episodes[0]["open_frame_id"], episodes[0]["close_frame_id"]))
        self.assertEqual("closed_on_missing_evidence", episodes[0]["close_reason"])
        self.assertEqual((115, 120), (episodes[1]["open_frame_id"], episodes[1]["close_frame_id"]))
        self.assertEqual("window_end", episodes[1]["close_reason"])

    def test_dropout_at_open_boundary_does_not_fabricate_episode(self) -> None:
        episodes = episodes_from_states(
            fixture_result(outcome_frame_id=115),
            "target",
            [pass_state(100), unknown_state(105), pass_state(110), pass_state(115)],
            CorridorConfig(open_after_frames=2, close_after_frames=2, analysis_rate_hz=5),
        )

        self.assertEqual(1, len(episodes))
        self.assertEqual((110, 115), (episodes[0]["open_frame_id"], episodes[0]["close_frame_id"]))

    def test_unknown_frames_do_not_close_as_failures(self) -> None:
        episodes = episodes_from_states(
            fixture_result(outcome_frame_id=115),
            "target",
            [pass_state(100), pass_state(105), unknown_state(110), unknown_state(115)],
            CorridorConfig(open_after_frames=2, close_after_frames=2, analysis_rate_hz=5),
        )

        self.assertEqual(1, len(episodes))
        self.assertEqual("closed_on_missing_evidence", episodes[0]["close_reason"])

    def test_two_observed_failures_close_as_failures(self) -> None:
        episodes = episodes_from_states(
            fixture_result(outcome_frame_id=115),
            "target",
            [pass_state(100), pass_state(105), fail_state(110), fail_state(115)],
            CorridorConfig(open_after_frames=2, close_after_frames=2, analysis_rate_hz=5),
        )

        self.assertEqual(1, len(episodes))
        self.assertEqual("closed_after_failures", episodes[0]["close_reason"])

    def test_duration_uses_elapsed_span_at_five_hz(self) -> None:
        episodes = episodes_from_states(
            fixture_result(outcome_frame_id=105),
            "target",
            [pass_state(100), pass_state(105)],
            CorridorConfig(open_after_frames=2, close_after_frames=2, analysis_rate_hz=5),
        )

        self.assertEqual(0.2, episodes[0]["duration_seconds"])
        self.assertEqual(2, episodes[0]["pass_frame_count"])

    def test_duration_uses_elapsed_span_at_twenty_five_hz(self) -> None:
        episodes = episodes_from_states(
            fixture_result(anchor_frame_id=100, outcome_frame_id=101),
            "target",
            [pass_state(100), pass_state(101)],
            CorridorConfig(open_after_frames=2, close_after_frames=2, analysis_rate_hz=25),
        )

        self.assertEqual(0.04, episodes[0]["duration_seconds"])
        self.assertEqual(2, episodes[0]["pass_frame_count"])

    def test_flicker_duration_is_elapsed_span_not_pass_frame_count(self) -> None:
        episodes = episodes_from_states(
            fixture_result(outcome_frame_id=120),
            "target",
            [pass_state(100), fail_state(105), pass_state(110), fail_state(115), fail_state(120)],
            CorridorConfig(open_after_frames=1, close_after_frames=2, analysis_rate_hz=5),
        )

        self.assertEqual(1, len(episodes))
        self.assertEqual((100, 110), (episodes[0]["open_frame_id"], episodes[0]["close_frame_id"]))
        self.assertEqual(0.4, episodes[0]["duration_seconds"])
        self.assertEqual(2, episodes[0]["pass_frame_count"])

    def test_anchor_evaluation_is_unknown_when_coverage_could_change_answer(self) -> None:
        evaluation = anchor_evaluation_for_result(
            fixture_result(),
            [],
            Counter({"PASS": 2, "UNKNOWN": 1}),
        )

        self.assertEqual("UNKNOWN", evaluation["evaluation_status"])
        self.assertEqual("mixed_relation_evidence_unavailable", evaluation["unknown_reason"])
        self.assertEqual(3, evaluation["total_state_count"])
        self.assertEqual(1, evaluation["unknown_state_count"])
        self.assertEqual("UNKNOWN", evaluation["coverage_status"])

    def test_missing_orientation_routes_to_unknown_anchor_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_minimal_canonical(root, include_orientation=False)

            report = evaluate_geometric_progressive_corridors(
                results=[fixture_result(match_id="fixture")],
                canonical_root=root,
                config=CorridorConfig(open_after_frames=2, close_after_frames=2),
            )

        self.assertEqual([], report["episodes"])
        self.assertEqual("UNKNOWN", report["anchor_evaluations"][0]["evaluation_status"])
        self.assertEqual("orientation_unavailable", report["anchor_evaluations"][0]["unknown_reason"])
        self.assertEqual("UNKNOWN", report["anchor_evaluations"][0]["coverage_status"])

    def test_evaluate_window_emits_unknown_state_for_missing_tracking_frame(self) -> None:
        positions = fixture_positions([100, 105, 115, 120])

        episodes, _negatives, counts = evaluate_result_window(
            result=fixture_result(outcome_frame_id=120),
            positions=positions,
            attack_x_sign=1,
            attacking_outfield={"target"},
            defending_outfield={"defender"},
            config=CorridorConfig(open_after_frames=2, close_after_frames=2, analysis_rate_hz=5),
        )

        self.assertEqual(1, counts["UNKNOWN"])
        self.assertEqual(2, len(episodes))
        self.assertEqual("closed_on_missing_evidence", episodes[0]["close_reason"])

    def test_executor_relation_node_preserves_missing_evidence_close_reason(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_minimal_canonical(root, include_orientation=True, frames=[100, 105, 115, 120])
            bound = bind_document(TacticalQueryDocument.model_validate(corridor_probe_document()))
            source_node = bound.nodes[0]
            relation_node = bound.nodes[1]
            source_output = next(output for output in source_node.outputs if output.name == "anchor_evaluations")
            state = fake_period_state(root)
            anchor = fixture_result(match_id="fixture", outcome_frame_id=120)
            state.runtime_values["source"] = {
                "anchor_evaluations": runtime_value_from_raw(
                    node_id="source",
                    output=source_output,
                    raw_value=[anchor],
                    frame_ids=[100, 105, 110, 115, 120],
                    records=[anchor],
                )
            }

            TacticalQueryExecutor(enable_node_cache=False)._execute_node(state=state, node=relation_node)

        episodes = state.signals["corridor"]["episodes"]
        self.assertEqual(2, len(episodes))
        self.assertEqual("closed_on_missing_evidence", episodes[0]["close_reason"])


def fixture_result(
    *,
    match_id: str = "fixture",
    anchor_frame_id: int = 100,
    outcome_frame_id: int = 120,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "result_id": "result_1",
        "match_id": match_id,
        "period": "firstHalf",
        "perspective_team_role": "home",
        "defending_team_role": "away",
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": anchor_frame_id,
        "end_frame_id": outcome_frame_id,
        "entity_refs": ["target"],
        "outcome_frame_id": outcome_frame_id,
    }
    payload["anchor_id"] = canonical_anchor_record_id(payload)
    return payload


def pass_state(frame_id: int) -> dict[str, object]:
    return {
        **fixture_result(anchor_frame_id=100, outcome_frame_id=max(120, frame_id)),
        "frame_id": frame_id,
        "target_player_id": "target",
        "status": "PASS",
        "source_point": {"x_m": 0.0, "y_m": 0.0},
        "target_point": {"x_m": 12.0, "y_m": 0.0},
        "forward_progression_m": 12.0,
        "segment_length_m": 12.0,
        "minimum_clearance_m": 8.0,
        "limiting_defender_id": "defender",
        "destination_side": "central",
        "destination_lane": "central",
        "destination_region": "central_central",
        "destination_region_type": "side_lane_band",
        "destination_region_bounds": {"min_y_m": -11.22, "max_y_m": 11.22},
    }


def fail_state(frame_id: int) -> dict[str, object]:
    return {
        **pass_state(frame_id),
        "status": "FAIL",
        "failure_reason": "clearance_below_threshold",
    }


def unknown_state(frame_id: int) -> dict[str, object]:
    return {
        **fixture_result(anchor_frame_id=100, outcome_frame_id=max(120, frame_id)),
        "frame_id": frame_id,
        "target_player_id": "target",
        "status": "UNKNOWN",
        "reason": "tracking_frame_unavailable",
    }


def fixture_positions(frames: list[int]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for frame_id in frames:
        rows.extend(
            [
                position_row(frame_id, None, "DFL-OBJ-0000XT", "ball", 0.0, 0.0),
                position_row(frame_id, "home", "target", "player", 12.0, 0.0),
                position_row(frame_id, "away", "defender", "player", 6.0, 10.0),
            ]
        )
    return pd.DataFrame(rows)


def position_row(
    frame_id: int,
    team_role: str | None,
    entity_id: str,
    entity_type: str,
    x_m: float,
    y_m: float,
) -> dict[str, object]:
    return {
        "frame_id": frame_id,
        "team_role": team_role,
        "entity_id": entity_id,
        "entity_type": entity_type,
        "x_m": x_m,
        "y_m": y_m,
    }


def write_minimal_canonical(
    root: Path,
    *,
    include_orientation: bool,
    frames: list[int] | None = None,
) -> None:
    orientation_rows = (
        [{"match_id": "fixture", "period": "firstHalf", "team_role": "home", "attack_x_sign": 1}]
        if include_orientation
        else []
    )
    pd.DataFrame(
        orientation_rows,
        columns=["match_id", "period", "team_role", "attack_x_sign"],
    ).to_parquet(root / "orientation.parquet")
    pd.DataFrame(
        [
            {"match_id": "fixture", "team_role": "home", "player_id": "target", "is_goalkeeper": False},
            {"match_id": "fixture", "team_role": "away", "player_id": "defender", "is_goalkeeper": False},
        ]
    ).to_parquet(root / "players.parquet")
    positions_path = root / "positions" / "match_id=fixture"
    positions_path.mkdir(parents=True)
    fixture_positions(frames or [100, 105, 110, 115, 120]).to_parquet(positions_path / "period=firstHalf.parquet")


def fake_period_state(canonical_root: Path) -> PeriodState:
    return PeriodState(
        match_id="fixture",
        period="firstHalf",
        params=RuntimeParameters(
            values={
                "analysis_rate_hz": 5,
                "maximum_analysis_gap_ms": 250,
                "minimum_outfield_players_per_team": 1,
            }
        ),
        recipe_id="corridor_probe_v1",
        recipe_version="0.0.0-test",
        perspective_team_role="home",
        perspective_team_id="home",
        defending_team_role="away",
        defending_team_id="away",
        canonical_root=canonical_root,
        raw_tracking=canonical_root / "unused.xml",
        positions=pd.DataFrame(),
        frame_ids=np.array([100, 105, 110, 115, 120], dtype=int),
        ball_y=np.array([], dtype=float),
        possession_role=np.array([], dtype=object),
        ball_alive=np.array([], dtype=bool),
        defender_count=pd.Series(dtype=int),
        defender_centroid_y=pd.Series(dtype=float),
    )


def corridor_probe_document() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": "corridor_probe_v1",
            "recipe_version": "0.0.0-test",
            "display_name": "Corridor Probe",
            "description": "Test-only corridor relation executor probe.",
            "default_unknown_evidence_policy": "include_with_warning",
            "allowed_claims": [],
            "disallowed_claims": [],
            "limitations": [],
            "output_classifications": ["CORRIDOR_PASS"],
            "parameters": [],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": "corridor_probe",
            "match_ids": ["fixture"],
            "periods": ["firstHalf"],
            "perspective_team_role": "home",
            "parameters": {},
            "max_results": 100,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": "corridor_probe",
            "plan_version": "0.0.0-test",
            "recipe_id": "corridor_probe_v1",
            "recipe_version": "0.0.0-test",
            "status": "experimental",
            "unknown_evidence_policy": "include_with_warning",
            "classification_mode": "partial_declared",
            "nodes": [
                {
                    "kind": "primitive",
                    "node_id": "source",
                    "catalog_ref": "action_event_anchor",
                    "version": "0.1.0",
                    "parameters": {},
                },
                {
                    "kind": "relation",
                    "node_id": "corridor",
                    "catalog_ref": "geometric_progressive_corridor_from_anchor_set",
                    "version": "0.1.0",
                    "inputs": {"anchors": {"source_node_id": "source", "output_name": "anchor_evaluations"}},
                    "parameters": {
                        "max_window_seconds": {"payload_type": "number", "unit": "second", "value": 0.8},
                        "minimum_progression_m": {"payload_type": "number", "unit": "metre", "value": 8.0},
                        "minimum_segment_length_m": {"payload_type": "number", "unit": "metre", "value": 8.0},
                        "maximum_segment_length_m": {"payload_type": "number", "unit": "metre", "value": 45.0},
                        "minimum_clearance_m": {"payload_type": "number", "unit": "metre", "value": 5.0},
                        "open_after_frames": {"payload_type": "number", "unit": "count", "value": 2},
                        "close_after_frames": {"payload_type": "number", "unit": "count", "value": 2},
                        "minimum_duration_seconds": {"payload_type": "number", "unit": "second", "value": 0.0},
                        "side_filter": {"payload_type": "enum", "unit": "none", "value": "any"},
                    },
                },
                {
                    "kind": "predicate",
                    "node_id": "corridor_pass",
                    "input": {"source_node_id": "corridor", "output_name": "anchor_evaluations"},
                    "operator": {"name": "exists", "version": "1.0.0"},
                },
            ],
            "classification_rules": [
                {"label": "CORRIDOR_PASS", "predicate_ids": ["corridor_pass"], "description": "Corridor exists."}
            ],
            "anchor_source": {"source_node_id": "source", "output_name": "anchor_evaluations"},
            "requested_evidence": [],
        },
    }


if __name__ == "__main__":
    unittest.main()
