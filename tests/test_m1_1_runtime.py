from __future__ import annotations

import ast
import json
import unittest
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import (
    LEGACY_M1_PARITY_PROFILE,
    PeriodState,
    TacticalQueryExecutor,
    ball_entry_evaluation_into_destination_region,
    execute_legacy_m1_plan_from_path,
    execute_plan_from_path,
    execution_result_rows,
    execute_default_plan,
    runtime_parameters,
    select_proof_results,
)
from tqe.runtime.ir import EvaluationTarget, ExecutionMode, ExecutionStatus, PlanStatus, TacticalQueryDocument
from tqe.runtime.relations import evaluate_geometric_progressive_corridors

from tests.support.canonical_data import requires_canonical_data


@requires_canonical_data
class M11RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bound, cls.execution = execute_default_plan()
        cls.experimental_bound, cls.experimental_execution = execute_legacy_m1_plan_from_path(
            Path("config/query-plans/opposite_corridor_after_shift.experimental.v1.json")
        )

    def test_runtime_selected_results_match_frozen_baseline(self) -> None:
        rows = execution_result_rows(self.execution)
        selected = select_proof_results(rows, runtime_parameters(self.bound))
        baseline = json.loads(
            Path("delivery/m1/baseline/m1-baseline-manifest.json").read_text(encoding="utf-8")
        )

        self.assertEqual(180, len(rows))
        self.assertEqual("execute", self.execution.provenance["execution_mode"])
        self.assertGreater(self.execution.provenance["runtime_value_count"], 0)
        self.assertEqual(
            baseline["legacy_result_manifest"]["selected_result_ids"],
            [item["result_id"] for item in selected],
        )
        self.assertTrue(self.execution.provenance["runtime_trace_hash"])

    def test_invocation_modes_are_operational(self) -> None:
        executor = TacticalQueryExecutor()
        bind_only = executor.execute(
            self.bound.model_copy(update={"execution_mode": ExecutionMode.BIND_ONLY})
        )
        dry_run = executor.execute(
            self.bound.model_copy(update={"execution_mode": ExecutionMode.DRY_RUN})
        )

        self.assertEqual(ExecutionStatus.NOT_STARTED, bind_only.status)
        self.assertEqual([], bind_only.results)
        self.assertEqual("bind_only", bind_only.provenance["execution_mode"])
        self.assertEqual(ExecutionStatus.PASS, dry_run.status)
        self.assertEqual([], dry_run.results)
        self.assertEqual("dry_run", dry_run.provenance["execution_mode"])

    def test_plan_path_helper_defaults_to_generic_execution(self) -> None:
        _bound, execution = execute_plan_from_path(
            Path("config/query-plans/opposite_corridor_after_shift.experimental.v1.json")
        )
        rows = execution_result_rows(execution)

        self.assertEqual("generic", execution.provenance["compatibility_profile"])
        self.assertGreater(len(rows), 0)
        self.assertEqual(
            {"CORRIDOR_PERSISTED_NO_DESTINATION_ENTRY", "DESTINATION_ENTERED"},
            {row["classification"] for row in rows},
        )
        self.assertFalse(
            {"block_shift_score", "wide_entry_frame_id", "signed_shift_metres"}.intersection(rows[0])
        )

    def test_max_results_is_honored_deterministically(self) -> None:
        executor = TacticalQueryExecutor(compatibility_profile=LEGACY_M1_PARITY_PROFILE)
        limited_bound = self.bound.model_copy(update={"max_results": 1})
        first = executor.execute(limited_bound)
        second = executor.execute(limited_bound)

        self.assertEqual(1, len(first.results))
        self.assertEqual(
            [result.result_id for result in first.results],
            [result.result_id for result in second.results],
        )
        self.assertEqual(first.execution_id, second.execution_id)

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
        executor = TacticalQueryExecutor(compatibility_profile=LEGACY_M1_PARITY_PROFILE)
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

    def test_relation_destination_entry_supports_possession_anchor_sources(self) -> None:
        payload = n1_possession_corridor_destination_entry_payload()
        bound = bind_document(TacticalQueryDocument.model_validate(payload))
        execution = TacticalQueryExecutor().execute(bound)
        rows = execution_result_rows(execution)

        self.assertEqual(ExecutionStatus.PASS, execution.status)
        self.assertEqual("generic", execution.provenance["compatibility_profile"])
        self.assertGreater(len(rows), 0)
        self.assertEqual({"DESTINATION_ENTERED"}, {row["classification"] for row in rows})
        self.assertTrue(all(row["matched_classification_rules"] == ["DESTINATION_ENTERED"] for row in rows))
        self.assertTrue(all(row["provenance"]["anchor_source"] == "possession.anchors" for row in rows))
        self.assertTrue(all(row["requested_evidence"]["destination_entry_status"] == "PASS" for row in rows))
        self.assertTrue(all(row["requested_evidence"]["destination_entry_frame_id"] is not None for row in rows))
        self.assertFalse(
            {"block_shift_score", "wide_entry_frame_id", "signed_shift_metres"}.intersection(rows[0])
        )
        destination_entry_node = next(
            node
            for node in payload["draft_plan"]["nodes"]
            if node["node_id"] == "destination_entry"
        )
        self.assertEqual("relation_destination_entry", destination_entry_node["catalog_ref"])

    def test_relation_destination_entry_evaluates_pass_fail_and_unknown(self) -> None:
        episode = destination_entry_fixture_episode()
        passing = ball_entry_evaluation_into_destination_region(
            state=destination_entry_fixture_state(
                frame_ids=range(100, 111),
                ball_points={frame_id: 40.0 for frame_id in range(100, 103)}
                | {103: 8.0}
                | {frame_id: 40.0 for frame_id in range(104, 111)},
            ),
            episode=episode,
            horizon_seconds=0.4,
        )
        failing = ball_entry_evaluation_into_destination_region(
            state=destination_entry_fixture_state(
                frame_ids=range(100, 111),
                ball_points={frame_id: 40.0 for frame_id in range(100, 111)},
            ),
            episode=episode,
            horizon_seconds=0.4,
        )
        unknown = ball_entry_evaluation_into_destination_region(
            state=destination_entry_fixture_state(
                frame_ids=range(100, 111),
                ball_points={frame_id: 40.0 for frame_id in range(100, 111) if frame_id != 105},
            ),
            episode=episode,
            horizon_seconds=0.4,
        )
        passing_before_gap = ball_entry_evaluation_into_destination_region(
            state=destination_entry_fixture_state(
                frame_ids=range(100, 111),
                ball_points={100: 8.0}
                | {frame_id: 40.0 for frame_id in range(101, 111) if frame_id != 105},
            ),
            episode=episode,
            horizon_seconds=0.4,
        )

        self.assertEqual("PASS", passing["entry_status"])
        self.assertEqual(103, passing["entry"]["frame_id"])
        self.assertEqual("ENTERED_AFTER_OPEN", passing["entry_mode"])
        self.assertEqual("FAIL", failing["entry_status"])
        self.assertEqual("NOT_ENTERED", failing["entry_mode"])
        self.assertEqual("UNKNOWN", unknown["entry_status"])
        self.assertEqual("UNKNOWN", unknown["entry_mode"])
        self.assertIn("missing_ball_frames", unknown["unknown_reason"])
        self.assertEqual("PASS", passing_before_gap["entry_status"])
        self.assertEqual("PRESENT_AT_OPEN", passing_before_gap["entry_mode"])

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


def n1_possession_corridor_destination_entry_payload() -> dict:
    base = json.loads(
        Path("config/query-plans/possession_corridor_availability.experimental.v1.json").read_text(
            encoding="utf-8"
        )
    )
    opposite = json.loads(
        Path("config/query-plans/opposite_corridor_after_shift.experimental.v1.json").read_text(
            encoding="utf-8"
        )
    )
    payload = deepcopy(base)
    payload["recipe"]["recipe_id"] = "n1_test_possession_corridor_destination_entry_v1"
    payload["recipe"]["recipe_version"] = "0.0.0-test"
    payload["recipe"]["display_name"] = "N1 Test Possession Corridor Destination Entry"
    payload["recipe"]["output_classifications"] = ["DESTINATION_ENTERED"]
    payload["recipe"]["parameters"] = deepcopy(base["recipe"]["parameters"])
    for parameter in opposite["recipe"]["parameters"]:
        if parameter["name"] not in {"result_id_seed_hash", "destination_entry_horizon_seconds"}:
            continue
        copied = deepcopy(parameter)
        if copied["name"] == "result_id_seed_hash":
            copied["default"]["value"] = "n1_test_possession_corridor_destination_entry_v1"
        elif copied["name"] == "destination_entry_horizon_seconds":
            copied["default"]["value"] = 5.0
        payload["recipe"]["parameters"].append(copied)
    for parameter in payload["recipe"]["parameters"]:
        if parameter["name"] == "corridor_max_window_seconds":
            parameter["default"]["value"] = 4.0
        elif parameter["name"] == "corridor_minimum_duration_seconds":
            parameter["default"]["value"] = 0.8
    payload["default_invocation"]["invocation_id"] = "n1_test_local_only"
    payload["default_invocation"]["match_ids"] = ["J03WOY"]
    payload["default_invocation"]["max_results"] = 3
    payload["draft_plan"]["plan_id"] = "n1_test_possession_corridor_destination_entry_v1"
    payload["draft_plan"]["recipe_id"] = payload["recipe"]["recipe_id"]
    payload["draft_plan"]["recipe_version"] = payload["recipe"]["recipe_version"]

    for node in opposite["draft_plan"]["nodes"]:
        if node["node_id"] == "destination_entry":
            destination_entry = deepcopy(node)
            destination_entry["catalog_ref"] = "relation_destination_entry"
            destination_entry["inputs"]["relation_episodes"] = {
                "source_node_id": "progressive_corridor",
                "output_name": "episodes",
            }
            destination_entry["parameters"]["episode_selection"] = {
                "payload_type": "enum",
                "unit": "none",
                "value": "entry_first_then_progression",
            }
        elif node["node_id"] == "destination_region_entered":
            destination_predicate = deepcopy(node)
            destination_predicate["input"] = {
                "source_node_id": "destination_entry",
                "output_name": "entry_status",
            }
            destination_predicate["operator"] = {"name": "eq", "version": "1.0.0"}
            destination_predicate["compare"] = {
                "payload_type": "enum",
                "unit": "none",
                "value": "PASS",
            }

    payload["draft_plan"]["nodes"] = deepcopy(base["draft_plan"]["nodes"]) + [
        destination_entry,
        destination_predicate,
    ]
    payload["draft_plan"]["classification_rules"] = [
        {
            "label": "DESTINATION_ENTERED",
            "predicate_ids": ["has_progressive_corridor", "destination_region_entered"],
            "description": (
                "A possession-anchored progressive corridor persisted and the ball entered "
                "its destination region within the configured horizon."
            ),
        }
    ]
    payload["draft_plan"]["requested_evidence"] = deepcopy(base["draft_plan"]["requested_evidence"]) + [
        {
            "source": {"source_node_id": "destination_entry", "output_name": "entry_status"},
            "field": "entry_status",
            "alias": "destination_entry_status",
        },
        {
            "source": {"source_node_id": "destination_entry", "output_name": "entry_status"},
            "field": "destination_entry_frame_id",
            "alias": "destination_entry_frame_id",
            "required": False,
        },
    ]
    payload["draft_plan"]["anchor_source"] = {"source_node_id": "possession", "output_name": "anchors"}
    return payload


def destination_entry_fixture_state(
    *,
    frame_ids: range,
    ball_points: dict[int, float],
) -> PeriodState:
    frame_id_list = list(frame_ids)
    positions = pd.DataFrame(
        [
            {
                "frame_id": frame_id,
                "entity_type": "ball",
                "entity_id": "ball",
                "team_id": "BALL",
                "team_role": "ball",
                "x_m": 0.0,
                "y_m": y_m,
            }
            for frame_id, y_m in sorted(ball_points.items())
        ]
    )
    return PeriodState(
        match_id="FIXTURE",
        period="firstHalf",
        params=runtime_parameters(
            bind_document(TacticalQueryDocument.model_validate(n1_possession_corridor_destination_entry_payload()))
        ),
        recipe_id="fixture",
        recipe_version="0.0.0",
        perspective_team_role="home",
        perspective_team_id="home",
        defending_team_role="away",
        defending_team_id="away",
        canonical_root=Path("unused"),
        raw_tracking=Path("unused"),
        positions=positions,
        frame_ids=np.array(frame_id_list),
        ball_y=np.array([ball_points.get(frame_id, np.nan) for frame_id in frame_id_list]),
        possession_role=np.array(["home" for _ in frame_id_list]),
        ball_alive=np.array([True for _ in frame_id_list]),
        defender_count=pd.Series(dtype="int64"),
        defender_centroid_y=pd.Series(dtype="float64"),
    )


def destination_entry_fixture_episode() -> dict:
    return {
        "relation_id": "fixture_relation",
        "relation_version": "0.1.0",
        "open_frame_id": 100,
        "open_confirm_frame_id": 101,
        "close_frame_id": 110,
        "duration_seconds": 0.4,
        "target_player_id": "target",
        "minimum_clearance_m": 3.0,
        "limiting_defender_id": "defender",
        "destination_side": "left",
        "destination_lane": "wide",
        "destination_region": "left_wide",
        "destination_region_type": "side_lane_band",
        "destination_region_bounds": {"min_y_m": 0.0, "max_y_m": 10.0},
        "source_open_point": {"x_m": 0.0, "y_m": 30.0},
        "target_open_point": {"x_m": 12.0, "y_m": 5.0},
        "source_close_point": {"x_m": 0.0, "y_m": 30.0},
        "target_close_point": {"x_m": 12.0, "y_m": 5.0},
    }


if __name__ == "__main__":
    unittest.main()
