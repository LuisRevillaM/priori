from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

from tqe.runtime.executor import (
    TacticalQueryExecutor,
    execute_plan_from_path,
    execution_result_rows,
    execute_default_plan,
    runtime_parameters,
    select_proof_results,
)
from tqe.runtime.ir import EvaluationTarget, PlanStatus
from tqe.runtime.relations import evaluate_geometric_progressive_corridors


class M11RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bound, cls.execution = execute_default_plan()
        cls.experimental_bound, cls.experimental_execution = execute_plan_from_path(
            Path("config/query-plans/opposite_corridor_after_shift.experimental.v1.json")
        )

    def test_runtime_selected_results_match_frozen_baseline(self) -> None:
        rows = execution_result_rows(self.execution)
        selected = select_proof_results(rows, runtime_parameters(self.bound))
        baseline = json.loads(
            Path("delivery/m1/baseline/m1-baseline-manifest.json").read_text(encoding="utf-8")
        )

        self.assertEqual(180, len(rows))
        self.assertEqual(
            baseline["legacy_result_manifest"]["selected_result_ids"],
            [item["result_id"] for item in selected],
        )
        self.assertTrue(self.execution.provenance["runtime_trace_hash"])

    def test_runtime_emits_full_predicate_traces_for_results(self) -> None:
        result_ids = {result.result_id for result in self.execution.results}
        expected_predicates = {
            "wide_entry_threshold",
            "wide_entry_persists",
            "shift_threshold",
            "shift_persists",
            "not_stoppage",
        }
        by_result: dict[str, set[str]] = {result_id: set() for result_id in result_ids}
        for trace in self.execution.predicate_traces:
            self.assertEqual("PASS", trace.status)
            self.assertIsNotNone(trace.value)
            self.assertIsNotNone(trace.threshold)
            result_id = str(trace.source_evidence["result_id"])
            by_result[result_id].add(trace.predicate_id)

        self.assertEqual(
            len(result_ids) * len(expected_predicates),
            len(self.execution.predicate_traces),
        )
        self.assertTrue(result_ids)
        for predicates in by_result.values():
            self.assertEqual(expected_predicates, predicates)

    def test_evaluation_target_returns_failures_and_no_anchor(self) -> None:
        executor = TacticalQueryExecutor()
        threshold = executor.evaluate_target(
            self.bound,
            EvaluationTarget(
                target_id="threshold_near_miss_j03woy_48010",
                match_id="J03WOY",
                period="firstHalf",
                approximate_time_ms=int(round(48010 / 25.0 * 1000.0)),
                search_radius_ms=1000,
            ),
        )
        quiet = executor.evaluate_target(
            self.bound,
            EvaluationTarget(
                target_id="quiet_opening_j03woy_first_half",
                match_id="J03WOY",
                period="firstHalf",
                approximate_time_ms=int(round(10000 / 25.0 * 1000.0)),
                search_radius_ms=1000,
            ),
        )

        self.assertEqual("NON_MATCH", threshold["status"])
        self.assertEqual(
            "FAIL",
            {item["predicate_id"]: item for item in threshold["failed_predicates"]}[
                "shift_persists"
            ]["status"],
        )
        self.assertEqual("NO_COMPATIBLE_ANCHOR", quiet["status"])

    def test_geometric_progressive_corridor_relation_has_real_episode_breadth(self) -> None:
        report = evaluate_geometric_progressive_corridors(
            results=execution_result_rows(self.execution)
        )

        self.assertGreaterEqual(report["summary"]["episode_count"], 20)
        self.assertGreaterEqual(report["summary"]["match_count_with_episode"], 3)
        self.assertIn("UNKNOWN", {item["state"]["status"] for item in report["unknown_invalid_controls"]})
        self.assertIn("INVALID", {item["state"]["status"] for item in report["unknown_invalid_controls"]})
        self.assertTrue(
            {
                "positive",
                "negative",
                "flicker_boundary",
            }.issubset({item["case_type"] for item in report["visual_review_cases"]})
        )

    def test_experimental_plan_executes_from_external_file(self) -> None:
        rows = execution_result_rows(self.experimental_execution)
        classifications = {row["classification"] for row in rows}
        matches = {row["match_id"] for row in rows}

        self.assertEqual(PlanStatus.EXPERIMENTAL, self.experimental_bound.plan_status)
        self.assertEqual("experimental", self.experimental_execution.provenance["plan_status"])
        self.assertGreaterEqual(len(rows), 20)
        self.assertGreaterEqual(len(matches), 3)
        self.assertTrue(
            {
                "DESTINATION_ENTERED",
                "CORRIDOR_PERSISTED_NO_DESTINATION_ENTRY",
            }.issubset(classifications)
        )
        self.assertTrue(all(row["plan_status"] == "experimental" for row in rows))
        self.assertTrue(all(row["destination_side"] != row["ball_side"] for row in rows))
        self.assertTrue(all(float(row["relation_duration_seconds"]) >= 0.8 for row in rows))

    def test_executor_does_not_branch_on_query_recipe_or_plan_identity(self) -> None:
        tree = ast.parse(Path("src/tqe/runtime/executor.py").read_text(encoding="utf-8"))
        guarded_names = {"query_id", "recipe_id", "plan_id"}
        hits = []
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                names = {child.id for child in ast.walk(node.test) if isinstance(child, ast.Name)}
                attrs = {child.attr for child in ast.walk(node.test) if isinstance(child, ast.Attribute)}
                hit = sorted((names | attrs) & guarded_names)
                if hit:
                    hits.append((node.lineno, hit))

        self.assertEqual([], hits)

    def test_executor_does_not_import_recipe_modules(self) -> None:
        tree = ast.parse(Path("src/tqe/runtime/executor.py").read_text(encoding="utf-8"))
        hits = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("tqe.query"):
                        hits.append((node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("tqe.query"):
                    hits.append((node.lineno, module))

        self.assertEqual([], hits)


if __name__ == "__main__":
    unittest.main()
