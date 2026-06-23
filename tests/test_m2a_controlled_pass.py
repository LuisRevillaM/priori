import unittest
from pathlib import Path

from tqe.runtime.controlled_pass import (
    ACCEPTED_MATCH_IDS,
    ControlledPassConfig,
    evaluate_controlled_passes,
)


class M2AControlledPassRuntimeTest(unittest.TestCase):
    def test_j03woy_runtime_emits_explicit_anchor_and_physical_release(self) -> None:
        output = evaluate_controlled_passes(
            canonical_root=Path("data/canonical/v1"),
            match_ids=("J03WOY",),
            periods=("firstHalf",),
            config=ControlledPassConfig(),
        )

        self.assertEqual("m2a.controlled_pass_episode.v1", output.schema_version)
        self.assertGreater(output.summary["episode_count"], 0)
        first = output.episodes[0]
        required_fields = {
            "anchor_id",
            "pass_episode_id",
            "event_anchor_frame_id",
            "physical_release_frame_id",
            "event_to_release_offset_ms",
            "release_detection_status",
            "controlled_pass_status",
            "forward_progression_m",
            "controlled_reception_frame_id",
            "passer_id",
            "receiver_id",
            "evaluation_status",
        }
        self.assertTrue(required_fields.issubset(first))
        self.assertEqual("PASS", first["controlled_pass_status"])
        self.assertIsInstance(first["event_anchor_frame_id"], int)
        self.assertIsInstance(first["physical_release_frame_id"], int)
        self.assertNotEqual(first["event_anchor_frame_id"], first["physical_release_frame_id"])

    def test_anchor_evaluations_include_non_pass_reasons(self) -> None:
        output = evaluate_controlled_passes(
            canonical_root=Path("data/canonical/v1"),
            match_ids=("J03WOY",),
            periods=("firstHalf",),
        )

        statuses = {item["controlled_pass_status"] for item in output.anchor_evaluations}
        self.assertIn("PASS", statuses)
        self.assertIn("FAIL", statuses)
        self.assertIn("UNKNOWN", statuses)
        self.assertTrue(
            any(
                item["release_detection_reason"] or item["controlled_reception_reason"]
                for item in output.anchor_evaluations
                if item["controlled_pass_status"] != "PASS"
            )
        )

    def test_scope_is_fail_closed_to_accepted_match(self) -> None:
        self.assertEqual(("J03WOY",), ACCEPTED_MATCH_IDS)
        with self.assertRaisesRegex(RuntimeError, "accepted only"):
            evaluate_controlled_passes(
                canonical_root=Path("data/canonical/v1"),
                match_ids=("J03WN1",),
                periods=("firstHalf",),
            )


if __name__ == "__main__":
    unittest.main()
