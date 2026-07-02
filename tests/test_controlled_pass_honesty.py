import json
import unittest
from datetime import timedelta

import pandas as pd

from tqe.runtime.controlled_pass import (
    ControlledPassConfig,
    PeriodControlContext,
    ReleaseDetection,
    align_event_to_frame,
    candidate_pass_events,
    detect_controlled_reception,
    detect_physical_release,
    evaluate_candidate,
)
from tqe.runtime.one_touch import OneTouchRelayConfig, adjacent_event_linked_passes


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


if __name__ == "__main__":
    unittest.main()
