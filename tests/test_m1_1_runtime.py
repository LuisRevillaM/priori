from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

from tqe.runtime.executor import execution_result_rows, execute_default_plan, runtime_parameters, select_proof_results


class M11RuntimeTests(unittest.TestCase):
    def test_runtime_selected_results_match_frozen_baseline(self) -> None:
        bound, execution = execute_default_plan()
        rows = execution_result_rows(execution)
        selected = select_proof_results(rows, runtime_parameters(bound))
        baseline = json.loads(
            Path("delivery/m1/baseline/m1-baseline-manifest.json").read_text(encoding="utf-8")
        )

        self.assertEqual(180, len(rows))
        self.assertEqual(
            baseline["legacy_result_manifest"]["selected_result_ids"],
            [item["result_id"] for item in selected],
        )
        self.assertTrue(execution.provenance["runtime_trace_hash"])

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


if __name__ == "__main__":
    unittest.main()
