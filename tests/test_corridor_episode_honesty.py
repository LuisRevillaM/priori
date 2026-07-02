import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import pandas as pd

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument
from tqe.runtime.relations import (
    CorridorConfig,
    anchor_evaluation_for_result,
    episodes_from_states,
    evaluate_geometric_progressive_corridors,
    evaluate_result_window,
)
from tqe.runtime.values import canonical_anchor_record_id


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

    def test_missing_orientation_routes_to_unknown_without_synthetic_state_count(self) -> None:
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
        self.assertEqual(0, report["anchor_evaluations"][0]["total_state_count"])
        self.assertEqual({}, report["summary"]["state_counts"])

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

    def test_missing_target_inside_available_frame_does_not_bridge_continuity(self) -> None:
        positions = fixture_positions([100, 105, 110, 115, 120], missing_target_frames={110})

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
        self.assertEqual((100, 105), (episodes[0]["open_frame_id"], episodes[0]["close_frame_id"]))
        self.assertEqual("closed_on_missing_evidence", episodes[0]["close_reason"])
        self.assertEqual((115, 120), (episodes[1]["open_frame_id"], episodes[1]["close_frame_id"]))
        self.assertEqual(0.2, episodes[0]["duration_seconds"])
        self.assertEqual(0.2, episodes[1]["duration_seconds"])

    def test_missing_ball_inside_available_frame_does_not_bridge_continuity(self) -> None:
        positions = fixture_positions([100, 105, 110, 115, 120], missing_ball_frames={110})

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

    def test_missing_target_at_window_boundaries_does_not_count_as_pass(self) -> None:
        positions = fixture_positions([100, 105, 110, 115], missing_target_frames={100, 115})

        episodes, _negatives, counts = evaluate_result_window(
            result=fixture_result(outcome_frame_id=115),
            positions=positions,
            attack_x_sign=1,
            attacking_outfield={"target"},
            defending_outfield={"defender"},
            config=CorridorConfig(open_after_frames=2, close_after_frames=2, analysis_rate_hz=5),
        )

        self.assertEqual(2, counts["UNKNOWN"])
        self.assertEqual(1, len(episodes))
        self.assertEqual((105, 110), (episodes[0]["open_frame_id"], episodes[0]["close_frame_id"]))
        self.assertEqual("closed_on_missing_evidence", episodes[0]["close_reason"])

    def test_executor_execute_path_projects_missing_evidence_close_reason(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "canonical"
            raw_root = Path(directory) / "raw"
            source_frames = list(range(100, 121))
            write_minimal_canonical(
                root,
                include_orientation=True,
                frames=source_frames,
                missing_target_frames={110},
            )
            write_minimal_raw_tracking(raw_root, frames=source_frames)
            bound = bind_document(TacticalQueryDocument.model_validate(corridor_probe_document()))

            execution = TacticalQueryExecutor(
                canonical_root=root,
                raw_root=raw_root,
                enable_node_cache=False,
            ).execute(bound)

        rows = execution_result_rows(execution)
        self.assertEqual(ExecutionStatus.PASS, execution.status)
        self.assertEqual(1, len(rows))
        self.assertEqual("closed_on_missing_evidence", rows[0]["requested_evidence"]["close_reason"])
        self.assertEqual(0, execution.provenance["requested_evidence_failure_count"])


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
        "destination_region_bounds": {"min_y_m": -6.8, "max_y_m": 6.8},
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


def fixture_positions(
    frames: list[int],
    *,
    missing_ball_frames: set[int] | None = None,
    missing_target_frames: set[int] | None = None,
) -> pd.DataFrame:
    missing_ball_frames = missing_ball_frames or set()
    missing_target_frames = missing_target_frames or set()
    rows: list[dict[str, object]] = []
    for frame_id in frames:
        if frame_id not in missing_ball_frames:
            rows.append(position_row(frame_id, None, None, "DFL-OBJ-0000XT", "ball", 0.0, 0.0))
        rows.append(position_row(frame_id, "home-id", "home", "passer", "player", 0.0, -10.0))
        if frame_id not in missing_target_frames:
            rows.append(position_row(frame_id, "home-id", "home", "target", "player", 12.0, 0.0))
        rows.append(position_row(frame_id, "away-id", "away", "defender", "player", 6.0, 10.0))
    return pd.DataFrame(rows)


def position_row(
    frame_id: int,
    team_id: str | None,
    team_role: str | None,
    entity_id: str,
    entity_type: str,
    x_m: float,
    y_m: float,
) -> dict[str, object]:
    return {
        "frame_id": frame_id,
        "team_id": team_id,
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
    missing_target_frames: set[int] | None = None,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
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
            {"match_id": "fixture", "team_role": "home", "team_id": "home-id"},
            {"match_id": "fixture", "team_role": "away", "team_id": "away-id"},
        ]
    ).to_parquet(root / "teams.parquet")
    pd.DataFrame(
        [
            {"match_id": "fixture", "team_role": "home", "team_id": "home-id", "player_id": "passer", "is_goalkeeper": False},
            {"match_id": "fixture", "team_role": "home", "team_id": "home-id", "player_id": "target", "is_goalkeeper": False},
            {"match_id": "fixture", "team_role": "away", "team_id": "away-id", "player_id": "defender", "is_goalkeeper": False},
        ]
    ).to_parquet(root / "players.parquet")
    frame_ids = frames or [100, 105, 110, 115, 120]
    positions_path = root / "positions" / "match_id=fixture"
    positions_path.mkdir(parents=True)
    fixture_positions(frame_ids, missing_target_frames=missing_target_frames).to_parquet(
        positions_path / "period=firstHalf.parquet"
    )
    frames_path = root / "frames" / "match_id=fixture"
    frames_path.mkdir(parents=True)
    pd.DataFrame(
        [
            {"frame_id": frame_id, "timestamp_utc": timestamp_for_frame(frame_id), "analysis_rate_hz": 25}
            for frame_id in frame_ids
        ]
    ).to_parquet(frames_path / "period=firstHalf.parquet")
    events_path = root / "events"
    events_path.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "match_id": "fixture",
                "period": "firstHalf",
                "team_role": "home",
                "row_index": 1,
                "event_type": "Play_Pass",
                "gameclock_seconds": 4.0,
                "player_id": "passer",
                "timestamp": timestamp_for_frame(100),
                "qualifier_json": json.dumps(
                    {"Evaluation": "successfullyCompleted", "Player": "passer", "Recipient": "target"},
                    sort_keys=True,
                ),
            }
        ]
    ).to_parquet(events_path / "match_id=fixture.parquet")


def write_minimal_raw_tracking(raw_root: Path, *, frames: list[int]) -> None:
    match_path = raw_root / "fixture"
    match_path.mkdir(parents=True)
    frame_xml = "\n".join(
        f'<Frame N="{frame_id}" T="{timestamp_for_frame(frame_id)}" BallPossession="1" BallStatus="1" />'
        for frame_id in frames
    )
    (match_path / "tracking.xml").write_text(
        f'<Root><FrameSet TeamId="BALL" GameSection="firstHalf">{frame_xml}</FrameSet></Root>',
        encoding="utf-8",
    )


def timestamp_for_frame(frame_id: int) -> str:
    seconds = frame_id / 25.0
    whole_seconds = int(seconds)
    millis = int(round((seconds - whole_seconds) * 1000))
    return f"2026-01-01T00:00:{whole_seconds:02d}.{millis:03d}Z"


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
            "parameters": {
                "minimum_possession_seconds": {"payload_type": "number", "unit": "second", "value": 0.8}
            },
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
                    "catalog_ref": "possession_segment",
                    "version": "0.1.0",
                    "parameters": {},
                },
                {
                    "kind": "relation",
                    "node_id": "corridor",
                    "catalog_ref": "geometric_progressive_corridor_from_anchor_set",
                    "version": "0.1.0",
                    "inputs": {"anchors": {"source_node_id": "source", "output_name": "anchors"}},
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
            "anchor_source": {"source_node_id": "source", "output_name": "anchors"},
            "requested_evidence": [
                {
                    "source": {"source_node_id": "corridor", "output_name": "episodes"},
                    "field": "close_reason",
                    "alias": "close_reason",
                    "required": True,
                }
            ],
        },
    }


if __name__ == "__main__":
    unittest.main()
