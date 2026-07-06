from __future__ import annotations

import unittest

from tqe.workshop.app_service import (
    film_room_evidence_overlay,
    film_room_register_replay_window,
    film_room_source_kind,
    public_canonical_sources,
)


class FilmRoomAppTests(unittest.TestCase):
    def test_anchor_only_moment_gets_observed_overlay_marker(self) -> None:
        overlay = film_room_evidence_overlay(
            {
                "anchor_frame_id": 121915,
                "classification": "COUNTERATTACK_INITIATION_SEQUENCE_RATE",
            }
        )

        self.assertEqual(
            [
                {
                    "stage": 0,
                    "label": "observed anchor",
                    "frame_id": 121915,
                    "status": "COUNTERATTACK_INITIATION_SEQUENCE_RATE",
                    "player_id": None,
                }
            ],
            overlay["stage_labels"],
        )
        self.assertEqual(
            [
                {
                    "stage": 0,
                    "frame_id": 121915,
                    "status": "COUNTERATTACK_INITIATION_SEQUENCE_RATE",
                    "player_id": None,
                }
            ],
            overlay["anchor_markers"],
        )
        self.assertEqual([], overlay["carry_trails"])

    def test_chain_record_overlay_uses_stage_witnesses_and_unknown_slate(self) -> None:
        overlay = film_room_evidence_overlay(
            {
                "chain_id": "chain-1",
                "anchor_frame_id": 100,
                "chain_status": "UNKNOWN",
                "chain_reason": "stage_3_window_truncated",
                "stage_1_frame_id": 100,
                "stage_1_status": "PASS",
                "stage_2_frame_id": 130,
                "stage_2_start_frame_id": 130,
                "stage_2_end_frame_id": 155,
                "stage_2_status": "PASS",
                "stage_2_player_id": "p7",
                "stage_2_minimum_numeric_value": 3.0,
                "stage_3_frame_id": 190,
                "stage_3_status": "UNKNOWN",
            }
        )

        self.assertEqual(["regain", "carry >= 3m", "pass"], [item["label"] for item in overlay["stage_labels"]])
        self.assertEqual(
            [{"start_frame_id": 130, "end_frame_id": 155, "player_id": "p7", "status": "PASS"}],
            overlay["carry_trails"],
        )
        self.assertEqual({"is_unknown": True, "reason": "stage_3_window_truncated"}, overlay["unknown"])

    def test_source_kind_is_derived_from_record_shape(self) -> None:
        self.assertEqual("chain_record", film_room_source_kind({"chain_id": "chain-1"}, fallback={}))
        self.assertEqual("chain_record", film_room_source_kind({"stage_1_frame_id": 100}, fallback={}))
        self.assertEqual("target", film_room_source_kind({"target_id": "target-1"}, fallback={}))
        self.assertEqual("result", film_room_source_kind({"result_id": "result-1"}, fallback={}))

    def test_replay_window_padding_is_derived_from_witness_frames(self) -> None:
        meta = film_room_register_replay_window(
            {
                "chain_id": "chain-1",
                "match_id": "J03WOY",
                "period": "secondHalf",
                "anchor_frame_id": 100,
                "stage_1_frame_id": 100,
                "stage_2_end_frame_id": 165,
                "stage_3_frame_id": 220,
            },
            plan_hash="plan",
            fallback_result_id="result-1",
            source_kind="chain_record",
        )

        self.assertEqual(0, meta["replay_start_frame_id"])
        self.assertEqual(245, meta["replay_end_frame_id"])

    def test_canonical_source_ids_are_idempotent(self) -> None:
        first = public_canonical_sources({"frames": "/canonical/frames.parquet"})
        second = public_canonical_sources(first)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
