from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import yaml

from tqe.workshop import app_service
from tqe.workshop.app_service import (
    film_room_answer_from_document,
    film_room_bootstrap_response,
    initialize_film_room_prewarm,
    prewarm_film_room_flagships_from_certified_tables,
    prewarm_film_room_flagships_safely,
)
from tqe.workshop.m1_2 import replay_window_from_canonical


class _FakeArrowTable:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def to_pandas(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)

    def to_pylist(self) -> list[dict[str, object]]:
        return self.rows


class Deploy1CGalleryFromTablesTests(unittest.TestCase):
    def setUp(self) -> None:
        with app_service.FILM_ROOM_PREWARM_LOCK:
            app_service.FILM_ROOM_PREWARMED_RESPONSES.clear()
            app_service.FILM_ROOM_PREWARM_RECORDS.clear()
            app_service.FILM_ROOM_REPLAY_INDEX.clear()
            app_service.FILM_ROOM_PREWARM_STATE.update(
                {
                    "state": "warming",
                    "started_at": None,
                    "completed_at": None,
                    "items": [],
                    "last_error": None,
                }
            )

    def test_certified_table_prewarm_is_ready_without_execution_or_replay_reads(self) -> None:
        with (
            patch("tqe.workshop.app_service.film_room_execute_document") as execute,
            patch("tqe.workshop.app_service.ensure_film_room_replay_payload") as replay,
        ):
            prewarm_film_room_flagships_from_certified_tables()
            bootstrap = film_room_bootstrap_response(output_root=Path("/unused"))

        self.assertEqual("ready", bootstrap["state"])
        self.assertEqual("prewarmed_certified_table", bootstrap["prewarmed_response"]["provider"])
        self.assertEqual("certified", bootstrap["answer"]["evidence_rows_kind"])
        self.assertEqual([], bootstrap["answer"]["executions"])
        self.assertIsNone(bootstrap["answer"]["replay"])
        self.assertGreater(len(bootstrap["answer"]["moments"]), 0)
        self.assertEqual(
            "certified_table_partition",
            bootstrap["answer"]["moments"][0]["source_kind"],
        )
        self.assertTrue(bootstrap["answer"]["moments"][0]["replay_window_id"])
        self.assertTrue(
            all(record["execution_performed"] is False for record in bootstrap["prewarm_records"])
        )
        metric = bootstrap["answer"]["interval_metric"]
        self.assertIsNotNone(metric["observed"])
        self.assertIsNotNone(metric["lower"])
        self.assertIsNotNone(metric["unknown_count"])
        self.assertEqual("certified", metric["source"]["evidence_kind"])
        execute.assert_not_called()
        replay.assert_not_called()

    def test_execution_answers_register_windows_but_do_not_materialize_them(self) -> None:
        execution_record = {
            "role": "home",
            "submit": {},
            "validation": {},
            "confirmation": {},
            "cache_before": {},
            "execution": {
                "bound_plan_hash": "bound-plan",
                "results": [
                    {
                        "result_id": "result-1",
                        "classification": "PASS",
                        "match_id": "J03WOY",
                        "period": "firstHalf",
                        "anchor_frame_id": 100,
                        "requested_evidence": {},
                    }
                ],
            },
            "runtime_evidence_sources": [],
            "cache_after_execute": {},
            "draft_record": {},
            "bound_record": {"bound_plan_hash": "bound-plan"},
        }
        document = {
            "schema_version": "test.v1",
            "default_invocation": {"perspective_team_role": "home"},
            "draft_plan": {"nodes": []},
        }
        with (
            patch(
                "tqe.workshop.app_service.film_room_execute_document",
                return_value=[execution_record],
            ),
            patch("tqe.workshop.app_service.ensure_film_room_replay_payload") as replay,
        ):
            answer = film_room_answer_from_document(
                document,
                expression_payload=None,
                expression_hash=None,
                synthesized_document_hash="document",
                output_root=Path("/unused"),
            )

        self.assertIsNone(answer["replay"])
        self.assertTrue(answer["moments"][0]["replay_window_id"])
        replay.assert_not_called()

    def test_flag_controls_only_execution_upgrade(self) -> None:
        with (
            patch(
                "tqe.workshop.app_service.prewarm_film_room_flagships_from_certified_tables"
            ) as table,
            patch("tqe.workshop.app_service.start_film_room_prewarm_thread") as execution,
        ):
            initialize_film_room_prewarm(output_root=Path("/unused"), execution_enabled=False)
        table.assert_called_once_with()
        execution.assert_not_called()

        with (
            patch(
                "tqe.workshop.app_service.prewarm_film_room_flagships_from_certified_tables"
            ) as table,
            patch("tqe.workshop.app_service.start_film_room_prewarm_thread") as execution,
        ):
            initialize_film_room_prewarm(output_root=Path("/runtime"), execution_enabled=True)
        table.assert_called_once_with()
        execution.assert_called_once_with(output_root=Path("/runtime"))

    def test_render_explicitly_disables_execution_prewarm(self) -> None:
        blueprint = yaml.safe_load(Path("render.yaml").read_text(encoding="utf-8"))
        env = {
            item["key"]: item.get("value")
            for item in blueprint["services"][0]["envVars"]
        }
        self.assertEqual("0", env["WORKBENCH_PREWARM_FILM_ROOM"])

    def test_failed_execution_upgrade_preserves_ready_table_answer(self) -> None:
        prewarm_film_room_flagships_from_certified_tables()
        with patch(
            "tqe.workshop.app_service.film_room_prewarmed_response",
            side_effect=RuntimeError("execution disabled in proof"),
        ):
            prewarm_film_room_flagships_safely(output_root=Path("/unused"))

        bootstrap = film_room_bootstrap_response(output_root=Path("/unused"))
        self.assertEqual("ready", bootstrap["state"])
        self.assertEqual("prewarmed_certified_table", bootstrap["prewarmed_response"]["provider"])

    def test_empty_execution_result_does_not_replace_servable_table_answer(self) -> None:
        prewarm_film_room_flagships_from_certified_tables()
        table_response = deepcopy(
            app_service.FILM_ROOM_PREWARMED_RESPONSES["counterattack_sequence_rate"]
        )
        empty_execution_response = deepcopy(table_response)
        empty_execution_response["provider"] = "prewarmed_committed_plan"
        empty_execution_response["answer"]["moments"] = []
        empty_execution_response["answer"]["moment_total_count"] = 0
        empty_execution_response["answer"]["visible_moment_count"] = 0
        with patch(
            "tqe.workshop.app_service.film_room_prewarmed_response",
            return_value=empty_execution_response,
        ):
            app_service.prewarm_film_room_flagships(output_root=Path("/unused"))

        bootstrap = film_room_bootstrap_response(output_root=Path("/unused"))
        self.assertEqual("ready", bootstrap["state"])
        self.assertEqual("prewarmed_certified_table", bootstrap["prewarmed_response"]["provider"])
        execution_records = [
            record
            for record in bootstrap["prewarm_records"]
            if record.get("prewarm_kind") == "execution_upgrade"
        ]
        self.assertTrue(execution_records)
        self.assertTrue(all(record["upgrade_applied"] is False for record in execution_records))

    def test_lazy_replay_parquet_reads_are_window_filtered(self) -> None:
        reads: list[dict[str, object]] = []

        def fake_read_table(path: Path, **kwargs: object) -> _FakeArrowTable:
            reads.append({"path": str(path), **kwargs})
            path_text = str(path)
            if "/frames/" in path_text:
                return _FakeArrowTable(
                    [
                        {"frame_id": 50, "timestamp_utc": "t0"},
                        {"frame_id": 100, "timestamp_utc": "t1"},
                        {"frame_id": 150, "timestamp_utc": "t2"},
                    ]
                )
            if "/positions/" in path_text:
                return _FakeArrowTable(
                    [
                        {
                            "frame_id": 100,
                            "team_id": "team",
                            "team_role": "home",
                            "entity_id": "player",
                            "entity_type": "player",
                            "x_m": 1.0,
                            "y_m": 2.0,
                        }
                    ]
                )
            return _FakeArrowTable(
                [{"match_id": "J03WOY", "pitch_length_m": 105.0, "pitch_width_m": 68.0}]
            )

        with patch("tqe.workshop.m1_2.pq.read_table", side_effect=fake_read_table):
            replay = replay_window_from_canonical(
                replay_window_id="replay-test",
                plan_path=Path("plan.json"),
                source_id="source",
                source_kind="result",
                match_id="J03WOY",
                period="firstHalf",
                anchor_frame_id=100,
                padding_seconds=2.0,
            )

        self.assertEqual(3, len(reads))
        for read in reads[:2]:
            self.assertEqual([("frame_id", ">=", 50), ("frame_id", "<=", 150)], read["filters"])
            self.assertIsNone(read["partitioning"])
        self.assertEqual([("match_id", "=", "J03WOY")], reads[2]["filters"])
        self.assertEqual(50, replay["start_frame_id"])
        self.assertEqual(150, replay["end_frame_id"])


if __name__ == "__main__":
    unittest.main()
