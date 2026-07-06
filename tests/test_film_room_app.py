from __future__ import annotations

import unittest

from tqe.workshop.app_service import film_room_evidence_overlay


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


if __name__ == "__main__":
    unittest.main()
