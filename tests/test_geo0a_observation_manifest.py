from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from tqe.evidence.observation_manifest import (
    ObservationCoverage,
    ObservationCoverageRow,
    ObservationManifestDocument,
    ObservationModality,
    ObservationWindow,
    gate_absence_status,
)
from tqe.runtime.capabilities.corridor_family import (
    ball_entry_evaluation_into_destination_region,
)


def coverage(*, status: str, modality: ObservationModality = ObservationModality.BALL) -> ObservationCoverage:
    document = ObservationManifestDocument(
        schema_version="tqe.observation_manifest.v1",
        manifest_id=f"test-{status.lower()}",
        producer="test",
        rows=(
            ObservationCoverageRow(
                row_id=f"TST:firstHalf:{modality.value}",
                modality=modality,
                match_id="TST",
                period="firstHalf",
                window=ObservationWindow(start_frame_id=10, end_frame_id=20),
                status=status,
                reason="test coverage declaration",
                provenance_token="test:TST:firstHalf",
            ),
        ),
    )
    return ObservationCoverage(document, manifest_path=None)


def destination_state(observation_coverage: ObservationCoverage) -> SimpleNamespace:
    return SimpleNamespace(
        match_id="TST",
        period="firstHalf",
        frame_ids=np.asarray([10, 11], dtype=np.int64),
        positions=pd.DataFrame(
            [
                {
                    "frame_id": frame_id,
                    "entity_type": "ball",
                    "x_m": 0.0,
                    "y_m": 0.0,
                }
                for frame_id in (10, 11)
            ]
        ),
        observation_coverage=observation_coverage,
    )


def destination_episode() -> dict[str, object]:
    return {
        "open_frame_id": 10,
        "destination_side": "RIGHT",
        "destination_lane": "wide",
        "destination_region": "RIGHT:wide",
        "destination_region_bounds": {"min_y_m": 20.0, "max_y_m": 30.0},
    }


class ObservationManifestLawTests(unittest.TestCase):
    def test_certified_ball_absence_can_remain_fail(self) -> None:
        result = ball_entry_evaluation_into_destination_region(
            state=destination_state(coverage(status="CERTIFIED")),
            episode=destination_episode(),
            horizon_seconds=0.04,
        )

        self.assertEqual("FAIL", result["entry_status"])
        self.assertEqual("NOT_ENTERED", result["entry_mode"])

    def test_uncertified_ball_absence_is_forced_unknown(self) -> None:
        result = ball_entry_evaluation_into_destination_region(
            state=destination_state(coverage(status="UNCERTIFIED")),
            episode=destination_episode(),
            horizon_seconds=0.04,
        )

        self.assertEqual("UNKNOWN", result["entry_status"])
        self.assertEqual("UNKNOWN", result["entry_mode"])
        self.assertIn("uncertified_observation_coverage[ball:", result["unknown_reason"])

    def test_absent_manifest_is_uncertified_fail_closed(self) -> None:
        decision = gate_absence_status(
            coverage=ObservationCoverage.from_path(None),
            match_id="TST",
            period="firstHalf",
            start_frame_id=10,
            end_frame_id=20,
            modalities=(ObservationModality.EVENT,),
            status="FAIL",
            reason="event_not_observed",
        )

        self.assertEqual("UNKNOWN", decision.status)
        self.assertIn("event:observation_manifest_absent", decision.reason)

    def test_coverage_must_span_the_entire_requested_window(self) -> None:
        decision = coverage(status="CERTIFIED").decision(
            modality=ObservationModality.BALL,
            match_id="TST",
            period="firstHalf",
            window=ObservationWindow(start_frame_id=10, end_frame_id=21),
        )

        self.assertFalse(decision.certified)
        self.assertEqual("observation_coverage_window_not_certified", decision.reason)

    def test_demo_manifest_is_integrity_locked_and_deployed(self) -> None:
        path = Path("data/canonical/v1/observation-manifest.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        document = ObservationManifestDocument.model_validate(payload)
        self.assertEqual(56, len(document.rows))
        self.assertEqual({"CERTIFIED"}, {row.status for row in document.rows})
        self.assertEqual(
            {"event", "ball", "possession", "player_track"},
            {row.modality.value for row in document.rows},
        )

        data_manifest = json.loads(Path("data/manifest.json").read_text(encoding="utf-8"))
        entry = next(
            item
            for item in data_manifest["files"]
            if item["path"] == "data/canonical/v1/observation-manifest.json"
        )
        self.assertEqual(path.stat().st_size, entry["size"])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"])
        deploy_manifest = json.loads(
            Path("config/deploy/demo-data-manifest.json").read_text(encoding="utf-8")
        )
        self.assertIn("observation-manifest.json", deploy_manifest["required_paths"])


if __name__ == "__main__":
    unittest.main()
