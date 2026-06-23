import unittest
from dataclasses import replace
from pathlib import Path

from tqe.runtime.controlled_pass import ControlledPassOutput, evaluate_controlled_passes
from tqe.runtime.high_bypass_pass import (
    CLASSIFICATION,
    REQUIRED_EVIDENCE_ALIASES,
    HighBypassConfig,
    emit_high_bypass_completed_pass_results,
)
from tqe.runtime.pass_bypass import evaluate_pass_bypass_measurements


EXPECTED_PASS_EPISODE_IDS = [
    "J03WOY:firstHalf:home:188:DFL-OBJ-002G5J:DFL-OBJ-002FXT",
    "J03WOY:firstHalf:away:227:DFL-OBJ-00286X:DFL-OBJ-00019R",
    "J03WOY:firstHalf:home:331:DFL-OBJ-0028FW:DFL-OBJ-002FXT",
    "J03WOY:secondHalf:home:102:DFL-OBJ-002GM9:DFL-OBJ-002FXT",
    "J03WOY:secondHalf:away:172:DFL-OBJ-002FZB:DFL-OBJ-0028IJ",
    "J03WOY:secondHalf:home:356:DFL-OBJ-002GMO:DFL-OBJ-0026RH",
    "J03WOY:secondHalf:away:385:DFL-OBJ-0025BB:DFL-OBJ-0001IG",
]


class M2AHighBypassPassRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.controlled = evaluate_controlled_passes(
            canonical_root=Path("data/canonical/v1"),
            match_ids=("J03WOY",),
            periods=("firstHalf", "secondHalf"),
        )
        cls.bypass = evaluate_pass_bypass_measurements(
            canonical_root=Path("data/canonical/v1"),
            controlled_passes=cls.controlled,
            match_ids=("J03WOY",),
            periods=("firstHalf", "secondHalf"),
        )
        cls.output = emit_high_bypass_completed_pass_results(
            canonical_root=Path("data/canonical/v1"),
            controlled_passes=cls.controlled,
            bypass_measurements=cls.bypass,
            match_ids=("J03WOY",),
            periods=("firstHalf", "secondHalf"),
        )

    def test_emits_real_high_bypass_results(self) -> None:
        self.assertEqual("m2a.high_bypass_completed_pass.v1", self.output.schema_version)
        self.assertEqual(7, len(self.output.results))
        self.assertEqual(len(self.output.results), self.output.summary["result_count"])
        self.assertEqual({CLASSIFICATION}, {item["classification"] for item in self.output.results})
        self.assertEqual(EXPECTED_PASS_EPISODE_IDS, [item["pass_episode_id"] for item in self.output.results])

    def test_results_have_complete_requested_evidence(self) -> None:
        self.assertEqual(0, self.output.summary["requested_evidence_failure_count"])
        for result in self.output.results:
            evidence = result["requested_evidence"]
            for alias in REQUIRED_EVIDENCE_ALIASES:
                self.assertIn(alias, evidence)
                if alias != "unknown_reason":
                    self.assertIsNotNone(evidence[alias])
            self.assertEqual("PASS", evidence["controlled_pass_status"])
            self.assertEqual("COMPLETE", evidence["evaluation_coverage_status"])
            self.assertGreaterEqual(evidence["forward_progression_m"], 8.0)
            self.assertGreaterEqual(evidence["opponents_bypassed_count"], 5)
            self.assertEqual(10, len(evidence["expected_active_opposition_outfield_ids"]))
            self.assertEqual(10, len(evidence["evaluated_opponent_ids"]))
            self.assertEqual([], evidence["missing_active_opponent_ids"])

    def test_result_ids_and_order_are_deterministic(self) -> None:
        repeat = emit_high_bypass_completed_pass_results(
            canonical_root=Path("data/canonical/v1"),
            controlled_passes=self.controlled,
            bypass_measurements=self.bypass,
            match_ids=("J03WOY",),
            periods=("firstHalf", "secondHalf"),
        )
        self.assertEqual(
            [item["result_id"] for item in self.output.results],
            [item["result_id"] for item in repeat.results],
        )
        self.assertEqual(
            [
                (item["match_id"], item["period"], item["release_frame_id"], item["reception_frame_id"])
                for item in self.output.results
            ],
            sorted(
                (item["match_id"], item["period"], item["release_frame_id"], item["reception_frame_id"])
                for item in self.output.results
            ),
        )

    def test_result_identity_survives_shuffled_source_records(self) -> None:
        shuffled_controlled = replace(
            self.controlled,
            episodes=list(reversed(self.controlled.episodes)),
            anchor_evaluations=list(reversed(self.controlled.anchor_evaluations)),
        )
        shuffled_bypass = replace(
            self.bypass,
            anchor_evaluations=list(reversed(self.bypass.anchor_evaluations)),
        )
        shuffled = emit_high_bypass_completed_pass_results(
            canonical_root=Path("data/canonical/v1"),
            controlled_passes=shuffled_controlled,
            bypass_measurements=shuffled_bypass,
            match_ids=("J03WOY",),
            periods=("firstHalf", "secondHalf"),
        )
        self.assertEqual(
            [item["result_id"] for item in self.output.results],
            [item["result_id"] for item in shuffled.results],
        )
        self.assertEqual(
            [item["anchor_id"] for item in self.output.results],
            [item["anchor_id"] for item in shuffled.results],
        )

    def test_predicate_traces_attach_to_each_result(self) -> None:
        self.assertEqual(len(self.output.results) * 3, len(self.output.predicate_traces))
        result_ids = {item["result_id"] for item in self.output.results}
        trace_ids = {
            item["source_evidence"]["result_id"]
            for item in self.output.predicate_traces
        }
        self.assertEqual(result_ids, trace_ids)
        self.assertTrue(all(item["status"] == "PASS" for item in self.output.predicate_traces))

    def test_thresholds_belong_to_recipe_layer(self) -> None:
        strict = emit_high_bypass_completed_pass_results(
            canonical_root=Path("data/canonical/v1"),
            controlled_passes=self.controlled,
            bypass_measurements=self.bypass,
            match_ids=("J03WOY",),
            periods=("firstHalf", "secondHalf"),
            config=HighBypassConfig(minimum_bypassed_opponents=8),
        )
        self.assertEqual(0, len(strict.results))
        self.assertGreater(
            strict.summary["non_match_reason_counts"].get("opponents_bypassed_below_threshold", 0),
            0,
        )

    def test_scope_can_use_another_canonical_match(self) -> None:
        output = emit_high_bypass_completed_pass_results(
            canonical_root=Path("data/canonical/v1"),
            match_ids=("J03WPY",),
            periods=("firstHalf",),
        )

        self.assertEqual(["J03WPY"], output.accepted_scope["match_ids"])
        self.assertGreater(output.summary["controlled_anchor_evaluation_count"], 0)

    def test_scope_is_fail_closed_for_unsupported_period(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "accepted only"):
            emit_high_bypass_completed_pass_results(
                canonical_root=Path("data/canonical/v1"),
                match_ids=("J03WOY",),
                periods=("thirdHalf",),
            )

    def test_injected_controlled_passes_are_scope_checked(self) -> None:
        injected = ControlledPassOutput(
            schema_version="test",
            capability="controlled_pass_episode",
            capability_version="test",
            status="pass",
            accepted_scope={},
            config={},
            summary={},
            episodes=[],
            anchor_evaluations=[
                {
                    "match_id": "J03WN1",
                    "period": "firstHalf",
                    "controlled_pass_status": "UNKNOWN",
                    "pass_episode_id": "x",
                    "anchor_id": "x",
                    "team_role": "home",
                    "passer_id": "p",
                    "receiver_id": "r",
                    "event_row_index": 1,
                    "event_anchor_frame_id": 10000,
                    "physical_release_frame_id": None,
                    "controlled_reception_frame_id": None,
                    "forward_progression_m": None,
                }
            ],
            non_match_examples=[],
        )
        injected.anchor_evaluations[0]["period"] = "thirdHalf"
        with self.assertRaisesRegex(RuntimeError, "outside M2A-S1B period scope"):
            emit_high_bypass_completed_pass_results(
                canonical_root=Path("data/canonical/v1"),
                controlled_passes=injected,
                match_ids=("J03WOY",),
                periods=("firstHalf",),
            )


if __name__ == "__main__":
    unittest.main()
