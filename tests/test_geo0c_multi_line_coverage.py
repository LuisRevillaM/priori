from __future__ import annotations

import unittest
from types import SimpleNamespace

import pandas as pd

from tqe.evidence.observation_manifest import (
    ObservationCoverage,
    ObservationCoverageRow,
    ObservationManifestDocument,
    ObservationModality,
    ObservationWindow,
)
from tqe.runtime.capabilities.lines_family import multi_line_anchor_record


FRAME_ID = 10


def observation_coverage(status: str) -> ObservationCoverage:
    document = ObservationManifestDocument(
        schema_version="tqe.observation_manifest.v1",
        manifest_id=f"geo0c-{status.lower()}",
        producer="geo0c-test",
        rows=(
            ObservationCoverageRow(
                row_id="TST:firstHalf:player_track",
                modality=ObservationModality.PLAYER_TRACK,
                match_id="TST",
                period="firstHalf",
                window=ObservationWindow(start_frame_id=FRAME_ID, end_frame_id=FRAME_ID),
                status=status,
                reason="test player-track coverage",
                provenance_token="geo0c:TST:firstHalf",
            ),
        ),
    )
    return ObservationCoverage(document, manifest_path=None)


def period_state(
    defenders: list[tuple[str, float | None, float | None]],
    *,
    coverage_status: str,
) -> SimpleNamespace:
    rows: list[dict[str, object]] = [
        {
            "frame_id": FRAME_ID,
            "entity_type": "ball",
            "entity_id": "ball",
            "team_id": None,
            "team_role": None,
            "x_m": 0.0,
            "y_m": 0.0,
        }
    ]
    rows.extend(
        {
            "frame_id": FRAME_ID,
            "entity_type": "player",
            "entity_id": player_id,
            "team_id": "away-team",
            "team_role": "away",
            "x_m": x_m,
            "y_m": y_m,
        }
        for player_id, x_m, y_m in defenders
    )
    return SimpleNamespace(
        match_id="TST",
        period="firstHalf",
        defending_team_role="away",
        positions=pd.DataFrame(rows),
        lookup_cache={},
        observation_coverage=observation_coverage(coverage_status),
    )


def evaluate(
    defenders: list[tuple[str, float | None, float | None]],
    *,
    coverage_status: str = "CERTIFIED",
    known_outfield_ids: set[str] | None = None,
) -> dict[str, object]:
    resolved_ids = (
        {player_id for player_id, _x_m, _y_m in defenders}
        if known_outfield_ids is None
        else known_outfield_ids
    )
    result = multi_line_anchor_record(
        state=period_state(defenders, coverage_status=coverage_status),
        anchor={"anchor_id": "anchor-10", "anchor_frame_id": FRAME_ID},
        anchor_frame_field="anchor_frame_id",
        goal_side_buffer_m=1.0,
        line_band_width_m=0.5,
        minimum_line_defenders=3,
        target_line_rank=2,
        attack_x_sign=1,
        known_outfield_ids=resolved_ids,
    )
    assert result is not None
    return result


def spread_defenders(count: int = 6) -> list[tuple[str, float, float]]:
    return [
        (f"d{index}", 2.0 + index * 3.0, float(index))
        for index in range(1, count + 1)
    ]


class MultiLineCoverageCorrectionTests(unittest.TestCase):
    def test_adequately_observed_absence_of_declared_pair_can_fail(self) -> None:
        result = evaluate(spread_defenders())

        self.assertEqual("FAIL", result["multi_line_status"])
        self.assertEqual("no_observed_lines", result["multi_line_reason"])
        self.assertEqual("ADEQUATE", result["defender_observation_status"])
        self.assertEqual(6, result["valid_observed_outfield_defender_count"])
        self.assertEqual(6, result["required_observed_outfield_defender_count"])
        self.assertEqual("CERTIFIED", result["player_track_coverage_status"])

    def test_uncertified_defender_absence_is_forced_unknown(self) -> None:
        result = evaluate(spread_defenders(), coverage_status="UNCERTIFIED")

        self.assertEqual("UNKNOWN", result["multi_line_status"])
        self.assertEqual("UNCERTIFIED", result["defender_observation_status"])
        self.assertIn(
            "uncertified_observation_coverage[player_track:",
            str(result["multi_line_reason"]),
        )
        self.assertEqual(
            ["TST:firstHalf:player_track"],
            result["player_track_coverage_row_ids"],
        )

    def test_insufficient_defender_observation_is_forced_unknown(self) -> None:
        result = evaluate(spread_defenders(count=5))

        self.assertEqual("UNKNOWN", result["multi_line_status"])
        self.assertEqual("INSUFFICIENT", result["defender_observation_status"])
        self.assertEqual(
            "insufficient_observed_outfield_defenders",
            result["multi_line_reason"],
        )
        self.assertEqual(5, result["valid_observed_outfield_defender_count"])
        self.assertEqual(6, result["required_observed_outfield_defender_count"])

    def test_invalid_observed_defender_coordinate_is_ambiguous(self) -> None:
        defenders = spread_defenders()
        defenders[-1] = (defenders[-1][0], defenders[-1][1], None)

        result = evaluate(defenders)

        self.assertEqual("UNKNOWN", result["multi_line_status"])
        self.assertEqual("AMBIGUOUS", result["defender_observation_status"])
        self.assertEqual("defender_positions_ambiguous", result["multi_line_reason"])
        self.assertEqual(["d6"], result["invalid_observed_outfield_defender_ids"])

    def test_unknown_outfield_population_is_ambiguous(self) -> None:
        result = evaluate(spread_defenders(), known_outfield_ids=set())

        self.assertEqual("UNKNOWN", result["multi_line_status"])
        self.assertEqual("AMBIGUOUS", result["defender_observation_status"])
        self.assertEqual(
            "defending_outfield_population_unknown",
            result["multi_line_reason"],
        )

    def test_adequately_observed_declared_pair_still_passes(self) -> None:
        defenders = [
            ("d1", 5.0, -10.0),
            ("d2", 5.1, 0.0),
            ("d3", 5.2, 10.0),
            ("d4", 10.0, -10.0),
            ("d5", 10.1, 0.0),
            ("d6", 10.2, 10.0),
        ]

        result = evaluate(defenders)

        self.assertEqual("PASS", result["multi_line_status"])
        self.assertEqual("target_line_rank_observed", result["multi_line_reason"])
        self.assertEqual(2, result["observed_line_count"])
        self.assertEqual(2, result["selected_line"]["line_rank"])


if __name__ == "__main__":
    unittest.main()
