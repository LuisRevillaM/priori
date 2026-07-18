from __future__ import annotations

import copy
import json
import unittest

from scripts.packets.hermes2_evidence import (
    BASELINE_PATH,
    compare_to_baseline,
    failure_attribution,
)


class Hermes2EvidenceTests(unittest.TestCase):
    def test_access_failure_is_not_misreported_as_a_genuine_gap(self) -> None:
        verdict = {
            "status": "FAIL",
            "observations": [
                {
                    "outcome": "exception",
                    "exception_type": "HermesNLAccessError",
                    "exception": "Hermes model invocation failed: no final response",
                }
            ],
        }

        self.assertEqual("model_access_failure", failure_attribution(verdict))

    def test_access_failure_invalidates_the_model_comparison_gate(self) -> None:
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        candidate = copy.deepcopy(baseline)
        passing = next(row for row in candidate["verdicts"] if row["status"] == "PASS")
        passing["status"] = "FAIL"
        passing["failures"] = ["HermesNLAccessError: no final response"]
        passing["observations"] = [
            {
                "outcome": "exception",
                "exception_type": "HermesNLAccessError",
                "exception": "Hermes model invocation failed: no final response",
            }
        ]
        candidate["summary"] = {"total": 15, "pass": 6, "fail": 9}

        comparison = compare_to_baseline(candidate)

        self.assertFalse(comparison["run_valid_for_model_comparison"])
        self.assertEqual([passing["case_id"]], comparison["model_access_failure_cases"])
        self.assertFalse(comparison["flip_gate"]["model_access_closed"])
        self.assertFalse(comparison["flip_gate"]["pass_count_at_least_historical_baseline"])


if __name__ == "__main__":
    unittest.main()
