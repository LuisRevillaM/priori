from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.audits import r1_5_population_audit
from scripts.coverage_map import compiler_search_reachability as search


def coverage_row() -> dict[str, object]:
    return {
        "concept": "support_depth",
        "classification": "supported",
        "composition_maturity": "handwired",
        "composition_maturity_applicable": True,
    }


def reachable_result() -> dict[str, object]:
    return {
        "target_id": "r1_1_goalward_axis_projection_v0",
        "concept": "support_depth",
        "held_out": True,
        "result": "compiler_reachable",
        "result_count": 40,
        "honest_zero": False,
        "plan_path": "generated/compiler-search-v0/plans/r1_1_goalward_axis_projection_v0.json",
        "document_hash": "abc123",
        "semantic_correspondence": {
            "coverage_row": "support_depth",
            "meaning": "Longitudinal support depth.",
        },
    }


class R1CCheckpointTests(unittest.TestCase):
    def test_update_coverage_rows_records_certified_plan_reference(self) -> None:
        rows = [coverage_row()]

        search.update_coverage_rows(rows, [reachable_result()])

        self.assertEqual("compiler_reachable", rows[0]["composition_maturity"])
        evidence = rows[0]["compiler_reachability_evidence"]
        self.assertEqual("generated/compiler-search-v0/plans/r1_1_goalward_axis_projection_v0.json", evidence["plan_path"])
        self.assertEqual("abc123", evidence["document_hash"])
        self.assertEqual("support_depth", evidence["semantic_correspondence"]["coverage_row"])

    def test_update_coverage_rows_rejects_missing_semantic_correspondence(self) -> None:
        result = reachable_result()
        result.pop("semantic_correspondence")

        with self.assertRaisesRegex(ValueError, "semantic_correspondence"):
            search.update_coverage_rows([coverage_row()], [result])

    def test_update_coverage_rows_rejects_missing_certified_plan_reference(self) -> None:
        result = reachable_result()
        result.pop("plan_path")

        with self.assertRaisesRegex(ValueError, "certified plan reference"):
            search.update_coverage_rows([coverage_row()], [result])

    def test_update_coverage_rows_rejects_missing_document_hash(self) -> None:
        result = reachable_result()
        result.pop("document_hash")

        with self.assertRaisesRegex(ValueError, "certified plan reference"):
            search.update_coverage_rows([coverage_row()], [result])

    def test_update_coverage_rows_ignores_non_reachable_result(self) -> None:
        result = copy.deepcopy(reachable_result())
        result["result"] = "not_compiler_reachable"
        result.pop("semantic_correspondence")
        rows = [coverage_row()]

        search.update_coverage_rows(rows, [result])

        self.assertEqual("handwired", rows[0]["composition_maturity"])

    def test_r1_5_population_audit_markdown_regenerates_from_json(self) -> None:
        audit_path = Path("delivery/packets/r1-5-population-audit/audit.json")
        expected = Path("delivery/packets/r1-5-population-audit/audit.md").read_text(encoding="utf-8")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))

        self.assertEqual(expected, r1_5_population_audit.render_markdown(audit))


if __name__ == "__main__":
    unittest.main()
