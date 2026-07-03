import json
import unittest
from collections import Counter
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from tqe.runtime.binder import bind_document
from tqe.runtime.controlled_pass import (
    ControlledPassConfig,
    ControlledPassOutput,
    PeriodControlContext,
    ReleaseDetection,
    align_event_to_frame,
    candidate_pass_events,
    detect_controlled_reception,
    detect_physical_release,
    evaluate_candidate,
)
from tqe.runtime.executor import (
    PeriodState,
    RuntimeParameters,
    TacticalQueryExecutor,
    runtime_parameters,
)
from tqe.runtime.capabilities.pass_family import (
    primitive_controlled_pass_episode,
    primitive_one_touch_relay_episode,
)
from tqe.runtime.ir import TacticalQueryDocument
from tqe.runtime.one_touch import OneTouchRelayConfig, OneTouchRelayOutput, adjacent_event_linked_passes

from tests.support.canonical_data import requires_canonical_data


class ControlledPassHonestyTest(unittest.TestCase):
    def test_truncated_reception_window_at_period_end_is_unknown(self) -> None:
        context = fixture_context(
            frame_count=10,
            players={"receiver": {frame_id: ("home", 20.0, 0.0) for frame_id in range(10)}},
            config=ControlledPassConfig(reception_search_seconds=0.4),
        )
        release = release_at(9)

        reception = detect_controlled_reception(fixture_event(), context, release)

        self.assertEqual("UNKNOWN", reception.status)
        self.assertEqual("reception_window_truncated", reception.reason)

    def test_truncated_reception_window_near_period_end_is_unknown(self) -> None:
        context = fixture_context(
            frame_count=10,
            players={"receiver": {frame_id: ("home", 20.0, 0.0) for frame_id in range(10)}},
            config=ControlledPassConfig(reception_search_seconds=0.4),
        )
        release = release_at(7)

        reception = detect_controlled_reception(fixture_event(), context, release)

        self.assertEqual("UNKNOWN", reception.status)
        self.assertEqual("reception_window_truncated", reception.reason)

    def test_full_reception_window_with_other_control_stays_fail(self) -> None:
        ball = {frame_id: (5.0, 0.0) for frame_id in range(20)}
        players = {
            "receiver": {frame_id: ("home", 20.0, 0.0) for frame_id in range(20)},
            "opponent": {frame_id: ("away", 5.0, 0.0) for frame_id in range(1, 6)},
        }
        context = fixture_context(
            frame_count=20,
            ball=ball,
            players=players,
            config=ControlledPassConfig(
                reception_search_seconds=0.4,
                minimum_receiver_dwell_seconds=0.08,
            ),
        )

        reception = detect_controlled_reception(fixture_event(), context, release_at(0))

        self.assertEqual("FAIL", reception.status)
        self.assertEqual("possession_definitively_broke", reception.reason)

    def test_sparse_release_tracking_is_unknown(self) -> None:
        ball = {frame_id: (0.0, 0.0) for frame_id in range(50)}
        players = {"passer": {0: ("home", 20.0, 0.0)}}
        context = fixture_context(
            frame_count=50,
            ball=ball,
            players=players,
            config=ControlledPassConfig(
                release_search_before_seconds=0.0,
                release_search_after_seconds=1.96,
                departure_frames=1,
                max_missing_frame_ratio=0.02,
            ),
        )

        release = detect_physical_release(fixture_event(), context)

        self.assertEqual("UNKNOWN", release.status)
        self.assertEqual("missing_tracking", release.reason)

    def test_fully_tracked_release_not_confirmed_is_unknown_not_fail(self) -> None:
        ball = {frame_id: (0.0, 0.0) for frame_id in range(10)}
        players = {"passer": {frame_id: ("home", 20.0, 0.0) for frame_id in range(10)}}
        context = fixture_context(
            frame_count=10,
            ball=ball,
            players=players,
            config=ControlledPassConfig(
                release_search_before_seconds=0.0,
                release_search_after_seconds=0.2,
                departure_frames=1,
            ),
        )

        release = detect_physical_release(fixture_event(), context)

        self.assertEqual("UNKNOWN", release.status)
        self.assertEqual("release_not_confirmed", release.reason)

    def test_release_missing_ratio_boundary_still_allows_valid_release(self) -> None:
        ball = {0: (0.0, 0.0), **{frame_id: (4.0, 0.0) for frame_id in range(1, 50)}}
        players = {
            "passer": {
                frame_id: ("home", 0.0, 0.0)
                for frame_id in range(50)
                if frame_id != 40
            }
        }
        context = fixture_context(
            frame_count=50,
            ball=ball,
            players=players,
            config=ControlledPassConfig(
                release_search_before_seconds=0.0,
                release_search_after_seconds=1.96,
                departure_frames=1,
                max_missing_frame_ratio=0.02,
            ),
        )

        release = detect_physical_release(fixture_event(), context)

        self.assertEqual("PASS", release.status)
        self.assertEqual(0, release.physical_release_frame_id)

    def test_observed_release_transition_survives_sparse_search_window(self) -> None:
        ball = {0: (0.0, 0.0), **{frame_id: (4.0, 0.0) for frame_id in range(1, 50)}}
        players = {
            "passer": {
                frame_id: ("home", 0.0, 0.0)
                for frame_id in range(50)
                if frame_id not in {20, 30}
            }
        }
        context = fixture_context(
            frame_count=50,
            ball=ball,
            players=players,
            config=ControlledPassConfig(
                release_search_before_seconds=0.0,
                release_search_after_seconds=1.96,
                departure_frames=1,
                max_missing_frame_ratio=0.02,
            ),
        )

        release = detect_physical_release(fixture_event(), context)

        self.assertEqual("PASS", release.status)
        self.assertEqual(0, release.physical_release_frame_id)

    def test_truncated_reception_window_with_contradiction_stays_fail(self) -> None:
        ball = {frame_id: (5.0, 0.0) for frame_id in range(10)}
        players = {
            "receiver": {frame_id: ("home", 20.0, 0.0) for frame_id in range(10)},
            "opponent": {frame_id: ("away", 5.0, 0.0) for frame_id in range(8, 10)},
        }
        context = fixture_context(
            frame_count=10,
            ball=ball,
            players=players,
            config=ControlledPassConfig(
                reception_search_seconds=0.4,
                minimum_receiver_dwell_seconds=0.08,
            ),
        )

        reception = detect_controlled_reception(fixture_event(), context, release_at(7))

        self.assertEqual("FAIL", reception.status)
        self.assertEqual("possession_definitively_broke", reception.reason)

    def test_default_event_filter_excludes_restart_passes_from_denominator(self) -> None:
        rows = candidate_pass_events(
            pd.DataFrame(
                [
                    event_row(1, "Play_Pass", "a", "b"),
                    event_row(2, "ThrowIn_Play_Pass", "a", "b"),
                    event_row(3, "FreeKick_Play_Pass", "a", "b"),
                    event_row(4, "GoalKick_Play_Pass", "a", "b"),
                    event_row(5, "KickOff_Play_Pass", "a", "b"),
                ]
            )
        )

        self.assertEqual([1], [row["row_index"] for row in rows])

    def test_widened_event_filter_readmits_restart_passes_with_provenance(self) -> None:
        rows = candidate_pass_events(
            pd.DataFrame(
                [
                    event_row(1, "Play_Pass", "a", "b"),
                    event_row(2, "ThrowIn_Play_Pass", "a", "b"),
                    event_row(3, "FreeKick_Play_Pass", "a", "b"),
                ]
            ),
            event_type_filter=("Play_Pass", "ThrowIn_Play_Pass"),
        )

        self.assertEqual(
            [(1, "Play_Pass"), (2, "ThrowIn_Play_Pass")],
            [(row["row_index"], row["event_type"]) for row in rows],
        )

    def test_empty_event_filter_tuple_fails_closed(self) -> None:
        events = pd.DataFrame(
            [
                event_row(1, "Play_Pass", "a", "b"),
                event_row(2, "Play_Pass", "b", "c"),
            ]
        )

        self.assertEqual([], candidate_pass_events(events, event_type_filter=()))
        self.assertEqual([], adjacent_event_linked_passes(events, config=OneTouchRelayConfig(event_type_filter=())))

    def test_one_touch_default_filter_excludes_restart_pass_pairs(self) -> None:
        events = pd.DataFrame(
            [
                event_row(1, "ThrowIn_Play_Pass", "a", "b", gameclock_seconds=1.0),
                event_row(2, "ThrowIn_Play_Pass", "b", "c", gameclock_seconds=2.0),
            ]
        )

        self.assertEqual([], adjacent_event_linked_passes(events, config=OneTouchRelayConfig()))

    def test_one_touch_widened_filter_readmits_restart_pass_pairs(self) -> None:
        events = pd.DataFrame(
            [
                event_row(1, "ThrowIn_Play_Pass", "a", "b", gameclock_seconds=1.0),
                event_row(2, "ThrowIn_Play_Pass", "b", "c", gameclock_seconds=2.0),
            ]
        )

        pairs = adjacent_event_linked_passes(
            events,
            config=OneTouchRelayConfig(event_type_filter=("ThrowIn_Play_Pass",)),
        )

        self.assertEqual(1, len(pairs))
        self.assertEqual("ThrowIn_Play_Pass", pairs[0][0]["event_type"])

    def test_alignment_uses_declared_tolerance_boundaries(self) -> None:
        frames = fixture_frames(1)
        inside = {**fixture_event(), "event_timestamp": str(frames.loc[0, "_frame_ts_utc"] + timedelta(milliseconds=250))}
        outside = {**fixture_event(), "event_timestamp": str(frames.loc[0, "_frame_ts_utc"] + timedelta(milliseconds=251))}

        self.assertEqual((0, -250.0), align_event_to_frame(inside, frames, max_alignment_ms=250.0))
        self.assertEqual((None, -251.0), align_event_to_frame(outside, frames, max_alignment_ms=250.0))

    def test_alignment_failure_uses_spec_reason(self) -> None:
        frames = fixture_frames(1)
        event = {
            **fixture_event(),
            "event_timestamp": str(frames.loc[0, "_frame_ts_utc"] + timedelta(milliseconds=251)),
        }
        context = fixture_context(
            frame_count=1,
            frames=frames,
            config=ControlledPassConfig(max_release_alignment_ms=250.0),
        )

        _, evaluation = evaluate_candidate(event, context)

        self.assertEqual("UNKNOWN", evaluation["release_detection_status"])
        self.assertEqual("release_frame_alignment_failed", evaluation["release_detection_reason"])


@requires_canonical_data
class ControlledPassExecutorParameterTest(unittest.TestCase):
    def test_executor_any_filter_restores_widened_distribution(self) -> None:
        records = executor_controlled_pass_candidate_records("any")

        self.assertEqual(639, len(records))
        self.assertEqual(
            {"PASS": 453, "FAIL": 102, "UNKNOWN": 84},
            dict(Counter(str(record["controlled_pass_status"]) for record in records)),
        )
        self.assertEqual(
            {
                "Play_Pass": 563,
                "ThrowIn_Play_Pass": 41,
                "FreeKick_Play_Pass": 17,
                "GoalKick_Play_Pass": 12,
                "KickOff_Play_Pass": 6,
            },
            dict(Counter(str(record["event_type"]) for record in records)),
        )

    def test_executor_throw_in_filter_restores_throw_in_candidates(self) -> None:
        records = executor_controlled_pass_candidate_records("ThrowIn_Play_Pass")

        self.assertEqual(41, len(records))
        self.assertEqual({"ThrowIn_Play_Pass"}, {str(record["event_type"]) for record in records})
        self.assertEqual({"PASS": 27, "FAIL": 10, "UNKNOWN": 4}, dict(Counter(str(record["controlled_pass_status"]) for record in records)))

    def test_executor_passes_declared_controlled_pass_config(self) -> None:
        node = bound_probe_node(
            controlled_pass_probe_document(
                "any",
                max_release_alignment_ms=375.0,
                reception_search_seconds=4.0,
            )
        )
        captured: dict[str, ControlledPassConfig] = {}

        def fake_evaluate_controlled_passes(**kwargs: object) -> ControlledPassOutput:
            captured["config"] = kwargs["config"]  # type: ignore[assignment]
            return ControlledPassOutput(
                schema_version="m2a.controlled_pass_episode.v1",
                capability="controlled_pass_episode",
                capability_version="0.1.0",
                status="pass",
                accepted_scope={},
                config={},
                summary={},
                episodes=[],
                anchor_evaluations=[],
                non_match_examples=[],
            )

        with patch("tqe.runtime.capabilities.pass_family.evaluate_controlled_passes", side_effect=fake_evaluate_controlled_passes):
            primitive_controlled_pass_episode(fake_period_state(), node)

        self.assertEqual(("any",), captured["config"].event_type_filter)
        self.assertEqual(375.0, captured["config"].max_release_alignment_ms)
        self.assertEqual(4.0, captured["config"].reception_search_seconds)

    def test_executor_passes_declared_one_touch_config(self) -> None:
        node = bound_probe_node(
            one_touch_probe_document(
                "FreeKick_Play_Pass",
                max_release_alignment_ms=375.0,
            )
        )
        captured: dict[str, OneTouchRelayConfig] = {}

        def fake_evaluate_one_touch_relays(**kwargs: object) -> OneTouchRelayOutput:
            captured["config"] = kwargs["config"]  # type: ignore[assignment]
            return OneTouchRelayOutput(
                schema_version="afl08.one_touch_relay_episode.v1",
                capability="one_touch_relay_episode",
                capability_version="0.1.0",
                status="pass",
                accepted_scope={},
                config={},
                summary={},
                anchor_evaluations=[],
                episodes=[],
                non_match_examples=[],
            )

        with patch("tqe.runtime.capabilities.pass_family.evaluate_one_touch_relays", side_effect=fake_evaluate_one_touch_relays):
            primitive_one_touch_relay_episode(fake_period_state(), node)

        self.assertEqual(("FreeKick_Play_Pass",), captured["config"].event_type_filter)
        self.assertEqual(375.0, captured["config"].max_release_alignment_ms)


def fixture_context(
    *,
    frame_count: int,
    frames: pd.DataFrame | None = None,
    ball: dict[int, tuple[float, float]] | None = None,
    players: dict[str, dict[int, tuple[str, float, float]]] | None = None,
    config: ControlledPassConfig,
) -> PeriodControlContext:
    frames = frames if frames is not None else fixture_frames(frame_count)
    ball = ball if ball is not None else {frame_id: (0.0, 0.0) for frame_id in range(frame_count)}
    players = players if players is not None else {}
    rows: list[dict[str, object]] = []
    for frame_id, xy in ball.items():
        rows.append(
            {
                "frame_id": frame_id,
                "team_role": None,
                "entity_id": "DFL-OBJ-0000XT",
                "entity_type": "ball",
                "x_m": xy[0],
                "y_m": xy[1],
            }
        )
    for entity_id, by_frame in players.items():
        for frame_id, (team_role, x_m, y_m) in by_frame.items():
            rows.append(
                {
                    "frame_id": frame_id,
                    "team_role": team_role,
                    "entity_id": entity_id,
                    "entity_type": "player",
                    "x_m": x_m,
                    "y_m": y_m,
                }
            )
    return PeriodControlContext(
        match_id="fixture",
        period="firstHalf",
        frames=frames,
        positions=pd.DataFrame(rows),
        attack_x_sign_by_role={"home": 1, "away": -1},
        config=config,
    )


def fixture_frames(frame_count: int) -> pd.DataFrame:
    start = pd.Timestamp("2026-01-01T00:00:00Z")
    frames = pd.DataFrame(
        {
            "frame_id": list(range(frame_count)),
            "timestamp_utc": [start + timedelta(milliseconds=40 * frame_id) for frame_id in range(frame_count)],
            "analysis_rate_hz": [25.0] * frame_count,
        }
    )
    frames["_frame_ts_utc"] = pd.to_datetime(frames["timestamp_utc"], utc=True)
    return frames


def fixture_event() -> dict[str, object]:
    return {
        "match_id": "fixture",
        "period": "firstHalf",
        "row_index": 1,
        "event_type": "Play_Pass",
        "event_timestamp": "2026-01-01 00:00:00+00:00",
        "gameclock_seconds": 0.0,
        "team_role": "home",
        "passer_id": "passer",
        "receiver_id": "receiver",
        "event_anchor_frame_id": 0,
        "event_frame_offset_ms": 0.0,
    }


def release_at(frame_id: int) -> ReleaseDetection:
    return ReleaseDetection(
        status="PASS",
        reason=None,
        event_anchor_frame_id=frame_id,
        physical_release_frame_id=frame_id,
        event_to_release_offset_ms=0.0,
        release_ball_xy=(0.0, 0.0),
        release_player_xy=(0.0, 0.0),
        release_ball_distance_m=0.0,
    )


def event_row(
    row_index: int,
    event_type: str,
    player: str,
    recipient: str,
    *,
    gameclock_seconds: float = 1.0,
) -> dict[str, object]:
    return {
        "match_id": "fixture",
        "period": "firstHalf",
        "team_role": "home",
        "row_index": row_index,
        "event_type": event_type,
        "gameclock_seconds": gameclock_seconds,
        "player_id": player,
        "timestamp": "2026-01-01 00:00:00+00:00",
        "qualifier_json": json.dumps(
            {
                "Evaluation": "successfullyCompleted",
                "Player": player,
                "Recipient": recipient,
            }
        ),
    }


def executor_controlled_pass_candidate_records(event_type_filter: str) -> list[dict[str, object]]:
    bound = bind_document(TacticalQueryDocument.model_validate(controlled_pass_probe_document(event_type_filter)))
    params = runtime_parameters(bound)
    executor = TacticalQueryExecutor(enable_node_cache=False)
    records: list[dict[str, object]] = []
    for period in bound.periods:
        state = executor._execute_period(
            bound_plan=bound,
            match_id="J03WOY",
            period=period,
            params=params,
        )
        records.extend(state.signals["controlled"]["candidate_evaluations_records"])
    return records


def bound_probe_node(payload: dict[str, object]):
    bound = bind_document(TacticalQueryDocument.model_validate(payload))
    return bound.nodes[0]


def controlled_pass_probe_document(
    event_type_filter: str,
    *,
    max_release_alignment_ms: float | None = None,
    reception_search_seconds: float | None = None,
) -> dict[str, object]:
    parameters: dict[str, dict[str, object]] = {
        "event_type_filter": {"payload_type": "enum", "unit": "none", "value": event_type_filter},
    }
    if max_release_alignment_ms is not None:
        parameters["max_release_alignment_ms"] = {
            "payload_type": "number",
            "unit": "millisecond",
            "value": max_release_alignment_ms,
        }
    if reception_search_seconds is not None:
        parameters["reception_search_seconds"] = {
            "payload_type": "number",
            "unit": "second",
            "value": reception_search_seconds,
        }
    return single_primitive_probe_document(
        catalog_ref="controlled_pass_episode",
        node_id="controlled",
        status_output="controlled_pass_status",
        anchor_output="anchors",
        parameters=parameters,
    )


def one_touch_probe_document(
    event_type_filter: str,
    *,
    max_release_alignment_ms: float | None = None,
) -> dict[str, object]:
    parameters: dict[str, dict[str, object]] = {
        "event_type_filter": {"payload_type": "enum", "unit": "none", "value": event_type_filter},
    }
    if max_release_alignment_ms is not None:
        parameters["max_release_alignment_ms"] = {
            "payload_type": "number",
            "unit": "millisecond",
            "value": max_release_alignment_ms,
        }
    return single_primitive_probe_document(
        catalog_ref="one_touch_relay_episode",
        node_id="relay",
        status_output="one_touch_relay_status",
        anchor_output="anchor_evaluations",
        parameters=parameters,
    )


def single_primitive_probe_document(
    *,
    catalog_ref: str,
    node_id: str,
    status_output: str,
    anchor_output: str,
    parameters: dict[str, dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": "executor_parameter_probe_v1",
            "recipe_version": "0.0.0-test",
            "display_name": "Executor Parameter Probe",
            "description": "Test-only executor parameter probe.",
            "default_unknown_evidence_policy": "include_with_warning",
            "allowed_claims": [],
            "disallowed_claims": [],
            "limitations": [],
            "output_classifications": ["STATUS_PASS"],
            "parameters": [],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": "executor_parameter_probe",
            "match_ids": ["J03WOY"],
            "periods": ["firstHalf", "secondHalf"],
            "perspective_team_role": "home",
            "parameters": {},
            "max_results": 100,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": "executor_parameter_probe",
            "plan_version": "0.0.0-test",
            "recipe_id": "executor_parameter_probe_v1",
            "recipe_version": "0.0.0-test",
            "status": "experimental",
            "unknown_evidence_policy": "include_with_warning",
            "classification_mode": "partial_declared",
            "nodes": [
                {
                    "kind": "primitive",
                    "node_id": node_id,
                    "catalog_ref": catalog_ref,
                    "version": "0.1.0",
                    "parameters": parameters,
                },
                {
                    "kind": "predicate",
                    "node_id": "status_pass",
                    "input": {"source_node_id": node_id, "output_name": status_output},
                    "operator": {"name": "eq", "version": "1.0.0"},
                    "compare": {"payload_type": "enum", "unit": "none", "value": "PASS"},
                },
            ],
            "classification_rules": [
                {"label": "STATUS_PASS", "predicate_ids": ["status_pass"], "description": "Status is PASS."}
            ],
            "anchor_source": {"source_node_id": node_id, "output_name": anchor_output},
            "requested_evidence": [],
        },
    }


def fake_period_state() -> PeriodState:
    return PeriodState(
        match_id="J03WOY",
        period="firstHalf",
        params=RuntimeParameters(values={}),
        recipe_id="executor_parameter_probe_v1",
        recipe_version="0.0.0-test",
        perspective_team_role="home",
        perspective_team_id="home",
        defending_team_role="away",
        defending_team_id="away",
        canonical_root=Path("data/canonical/v1"),
        raw_tracking=Path("data/raw"),
        positions=pd.DataFrame(),
        frame_ids=np.array([], dtype=int),
        ball_y=np.array([], dtype=float),
        possession_role=np.array([], dtype=object),
        ball_alive=np.array([], dtype=bool),
        defender_count=pd.Series(dtype=int),
        defender_centroid_y=pd.Series(dtype=float),
    )


if __name__ == "__main__":
    unittest.main()
