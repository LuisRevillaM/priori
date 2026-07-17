from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from tqe.adapters.canonical_tracking_json import adapt_exchange
from tqe.evidence.observation_manifest import ObservationManifestDocument
from tqe.runtime.catalog import default_catalog
from tqe.runtime.capabilities.possession_family import primitive_transition_anchor
from tqe.runtime.executor import RuntimeParameters, stream_canonical_frame_state
from tqe.runtime.ir import TypedValue


def exchange_payload() -> dict[str, object]:
    return {
        "schema_version": "canonical_tracking_exchange.v1",
        "source_adapter": "test.adapter",
        "matches": [
            {
                "match_id": "TST",
                "period": "firstHalf",
                "frame_rate_hz": 25,
                "pitch_length_m": 105.0,
                "pitch_width_m": 68.0,
                "teams": [
                    {"team_id": "TST-home", "team_name": "Home", "team_role": "home"},
                    {"team_id": "TST-away", "team_name": "Away", "team_role": "away"},
                ],
                "entities": [
                    {"entity_id": "p1", "team_role": "home", "is_goalkeeper": False},
                ],
                "frames": [
                    {
                        "frame_id": 1,
                        "timestamp_utc": "2026-01-01T00:00:00Z",
                        "position_evidence": "KNOWN",
                        "position_gate_reasons": [],
                        "positions": [{"entity_id": "p1", "x_m": 1.0, "y_m": 2.0}],
                        "possession_team_role": None,
                        "possession_evidence": "UNKNOWN",
                        "ball_alive": None,
                        "ball_evidence": "UNKNOWN",
                    },
                    {
                        "frame_id": 2,
                        "timestamp_utc": "2026-01-01T00:00:00.040000Z",
                        "position_evidence": "UNKNOWN",
                        "position_gate_reasons": ["physics_player_speed_violation"],
                        "positions": [],
                        "possession_team_role": None,
                        "possession_evidence": "UNKNOWN",
                        "ball_alive": None,
                        "ball_evidence": "UNKNOWN",
                    },
                ],
            }
        ],
    }


class CanonicalTrackingAdapterTests(unittest.TestCase):
    def test_adapter_preserves_unknown_state_and_withholds_gated_positions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "exchange.json"
            source.write_text(json.dumps(exchange_payload()), encoding="utf-8")
            canonical = root / "canonical"

            summary = adapt_exchange(source, canonical)

            self.assertEqual(1, len(summary["matches"]))
            positions = pq.ParquetFile(
                canonical / "positions" / "match_id=TST" / "period=firstHalf.parquet"
            ).read().to_pylist()
            self.assertEqual([1], [row["frame_id"] for row in positions])
            state = stream_canonical_frame_state(
                canonical / "frame_state" / "match_id=TST" / "period=firstHalf.parquet"
            )
            self.assertEqual([None, None], state.possession_team_role.tolist())
            self.assertEqual([None, None], state.ball_alive.tolist())
            observation_manifest = ObservationManifestDocument.model_validate_json(
                (canonical / "observation-manifest.json").read_text(encoding="utf-8")
            )
            status_by_modality = {
                row.modality.value: row.status for row in observation_manifest.rows
            }
            self.assertEqual("UNCERTIFIED", status_by_modality["event"])
            self.assertEqual("UNCERTIFIED", status_by_modality["ball"])
            self.assertEqual("UNCERTIFIED", status_by_modality["possession"])
            self.assertEqual("UNCERTIFIED", status_by_modality["player_track"])

    def test_unknown_transition_boundaries_are_emitted_instead_of_dropped(self) -> None:
        catalog_entry = next(item for item in default_catalog().primitives if item.name == "transition_anchor")
        node = SimpleNamespace(
            node_id="transition",
            outputs=catalog_entry.outputs,
            resolved_parameters={
                "transition_type": TypedValue(payload_type="enum", value="regain"),
                "minimum_prior_possession_seconds": TypedValue(
                    payload_type="number", unit="second", value=0.4
                ),
                "zone_filter": TypedValue(payload_type="enum", value="any"),
                "zone_boundary_buffer_m": TypedValue(
                    payload_type="number", unit="metre", value=0.5
                ),
            },
        )
        state = SimpleNamespace(
            match_id="TST",
            period="firstHalf",
            params=RuntimeParameters(values={"analysis_rate_hz": 5}),
            perspective_team_role="home",
            perspective_team_id="TST-home",
            defending_team_role="away",
            defending_team_id="TST-away",
            canonical_root=Path("unused"),
            positions=pd.DataFrame(
                columns=["frame_id", "team_id", "team_role", "entity_id", "entity_type", "x_m", "y_m"]
            ),
            frame_ids=np.asarray([1, 6, 11]),
            possession_role=np.asarray([None, None, None], dtype=object),
            ball_alive=np.asarray([None, None, None], dtype=object),
            lookup_cache={},
            signals={},
        )
        orientation = pd.DataFrame(
            [{"match_id": "TST", "period": "firstHalf", "team_role": "home", "attack_x_sign": 1}]
        )

        with mock.patch(
            "tqe.runtime.capabilities.possession_family.parquet_rows", return_value=orientation
        ):
            primitive_transition_anchor(state, node)

        records = state.signals["transition"]["anchor_evaluations"]
        self.assertEqual(2, len(records))
        self.assertEqual({"UNKNOWN"}, {record["transition_status"] for record in records})
        self.assertEqual(
            {"possession_or_ball_evidence_unknown"},
            {record["transition_reason"] for record in records},
        )

if __name__ == "__main__":
    unittest.main()
