from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tqe.runtime.ir import stable_hash
from tqe.workshop import app_service
from tqe.workshop.app_service import (
    FILM_ROOM_DESCRIPTOR_INDEX_SCHEMA,
    FILM_ROOM_HYDRATION_SCHEMA,
    FilmRoomMomentResponse,
    build_film_room_descriptor_index,
    film_room_bootstrap_response,
    film_room_flagship_specs,
    film_room_replay_window_response,
    film_room_role_documents,
    initialize_film_room_prewarm,
    write_film_room_descriptor_fragment,
)
from tqe.workshop.m1_2 import read_json, write_json


def chain_record(anchor: int, *, marker: str = "full-payload") -> dict[str, object]:
    return {
        "chain_id": f"chain-{anchor}",
        "chain_status": "PASS",
        "chain_reason": "observed three-stage chain",
        "match_id": "J03WOH",
        "period": "firstHalf",
        "anchor_frame_id": anchor,
        "start_frame_id": anchor - 20,
        "end_frame_id": anchor + 20,
        "stage_1_status": "PASS",
        "stage_1_frame_id": anchor - 20,
        "stage_1_player_id": "p1",
        "stage_2_status": "PASS",
        "stage_2_frame_id": anchor,
        "stage_2_start_frame_id": anchor - 5,
        "stage_2_end_frame_id": anchor + 5,
        "stage_2_player_id": "p2",
        "stage_2_minimum_numeric_value": 8.0,
        "stage_3_status": "PASS",
        "stage_3_frame_id": anchor + 20,
        "stage_3_player_id": "p3",
        "large_chain_payload_marker": marker,
    }


def descriptor(anchor: int, replay_window_id: str) -> dict[str, object]:
    record = chain_record(anchor)
    evidence = app_service.film_room_descriptor_evidence(record, role="away")
    return FilmRoomMomentResponse.model_validate(
        {
            "result_id": f"chain-{anchor}",
            "source_kind": "chain_record",
            "classification": "PASS",
            "match_id": "J03WOH",
            "period": "firstHalf",
            "anchor_frame_id": anchor,
            "start_frame_id": anchor - 20,
            "end_frame_id": anchor + 20,
            "requested_evidence": evidence,
            "replay_window_id": replay_window_id,
            "replay_start_frame_id": anchor - 50,
            "replay_end_frame_id": anchor + 50,
            "evidence_row": evidence,
            "chain_status": "PASS",
            "chain_reason": "observed three-stage chain",
            "evidence_overlay": app_service.film_room_evidence_overlay(record),
        }
    ).model_dump(mode="json")


class Deploy2LazyHydrationTests(unittest.TestCase):
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

    def test_role_fragment_separates_descriptor_from_chain_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_path = root / "plan.json"
            write_json(
                plan_path,
                {
                    "schema_version": "test.v1",
                    "default_invocation": {"perspective_team_role": "home"},
                    "draft_plan": {"nodes": []},
                },
            )
            execution = {
                "role": "home",
                "execution": {
                    "execution_id": "exec-test",
                    "bound_plan_hash": "bound-test",
                    "results": [
                        {
                            "result_id": "result-test",
                            "classification": "PASS",
                            "requested_evidence": {"source_records": [chain_record(100)]},
                        }
                    ],
                },
                "cache_after_execute": {"cache_status": "MISS"},
                "bound_record": {"bound_plan_hash": "bound-test"},
            }
            cache = root / "cache"
            with patch("tqe.workshop.app_service.CACHE_ROOT", cache):
                summary = write_film_room_descriptor_fragment(
                    key="test_flagship",
                    role="home",
                    plan_path=plan_path,
                    executions=[execution],
                    output_root=root / "runtime",
                )

            fragment = read_json(Path(summary["fragment_path"]))
            item = fragment["moments"][0]
            shard = read_json(cache / item["hydration_path"])

        self.assertEqual(1, summary["descriptor_count"])
        self.assertNotIn("large_chain_payload_marker", item["descriptor"]["requested_evidence"])
        self.assertEqual("full-payload", shard["chain_record"]["large_chain_payload_marker"])
        self.assertEqual(3, len(item["descriptor"]["evidence_overlay"]["stage_labels"]))

    def test_prewarm_off_startup_loads_metadata_without_execution_or_full_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "cache"
            for spec_index, spec in enumerate(film_room_flagship_specs()):
                key = str(spec["key"])
                plan_path = Path(spec["plan_path"])
                plan_payload = read_json(plan_path)
                plan_hash = stable_hash(plan_payload)
                for role_index, role in enumerate(sorted(film_room_role_documents(plan_payload))):
                    anchor = 1000 + spec_index * 100 + role_index * 10
                    replay_id = f"replay-{key}-{role}"
                    hydration_relative = f"film-room-hydration/{replay_id}.json"
                    hydration_path = cache / hydration_relative
                    moments = []
                    if key == "counterattack_sequence_rate":
                        write_json(
                            hydration_path,
                            {
                                "schema_version": FILM_ROOM_HYDRATION_SCHEMA,
                                "replay_window_id": replay_id,
                                "plan_hash": plan_hash,
                                "plan_path": str(plan_path),
                                "source_id": f"chain-{anchor}",
                                "source_kind": "chain_record",
                                "match_id": "J03WOH",
                                "period": "firstHalf",
                                "anchor_frame_id": anchor,
                                "padding_seconds": 2.0,
                                "chain_record": chain_record(anchor),
                            },
                        )
                        moments = [
                            {
                                "descriptor": descriptor(anchor, replay_id),
                                "hydration_path": hydration_relative,
                                "hydration_sha256": app_service.file_sha256(hydration_path),
                            }
                        ]
                    write_json(
                        cache / f"film-room-descriptor-fragments/{key}-{role}.json",
                        {
                            "schema_version": FILM_ROOM_DESCRIPTOR_INDEX_SCHEMA,
                            "flagship_key": key,
                            "role": role,
                            "plan_hash": plan_hash,
                            "plan_path": str(plan_path),
                            "bound_plan_hash": f"bound-{role}",
                            "execution_id": f"exec-{role}",
                            "cache_status": "MISS",
                            "moments": moments,
                        },
                    )
            (cache / "enormous-execution-cache.json").write_text("must not be opened", encoding="utf-8")
            opened: list[Path] = []
            original_read_json = app_service.read_json

            def tracked_read_json(path: Path) -> object:
                opened.append(Path(path))
                return original_read_json(path)

            with (
                patch("tqe.workshop.app_service.CACHE_ROOT", cache),
                patch("tqe.workshop.app_service.read_json", side_effect=tracked_read_json),
                patch("tqe.workshop.app_service.film_room_prewarmed_response") as full_payload_prewarm,
                patch("tqe.workshop.app_service.film_room_execute_document") as plan_execution,
            ):
                thread = initialize_film_room_prewarm(
                    output_root=root / "runtime",
                    execution_enabled=False,
                )
                bootstrap = film_room_bootstrap_response(output_root=root / "runtime")
                index = build_film_room_descriptor_index(output_root=root / "runtime")

        self.assertEqual("ready", bootstrap["state"])
        self.assertIsNone(thread)
        self.assertEqual("prewarmed_descriptor_index", bootstrap["prewarmed_response"]["provider"])
        self.assertTrue(bootstrap["answer"]["moments"])
        self.assertTrue(all(item["source_kind"] == "chain_record" for item in bootstrap["answer"]["moments"]))
        self.assertEqual([], bootstrap["answer"]["executions"])
        self.assertTrue(
            all(record.get("execution_performed") is False for record in bootstrap["prewarm_records"])
        )
        descriptor_records = [
            record
            for record in bootstrap["prewarm_records"]
            if record.get("prewarm_kind") == "descriptor_index_load"
        ]
        self.assertEqual(2, len(descriptor_records))
        fragile_record = next(
            record
            for record in bootstrap["prewarm_records"]
            if record.get("key") == "fragile_retention"
            and record.get("prewarm_kind") == "descriptor_index_load"
        )
        self.assertEqual("no_chain_descriptors", fragile_record["reason"])
        self.assertFalse(fragile_record["upgrade_applied"])
        self.assertEqual(2, index["flagships"]["counterattack_sequence_rate"]["descriptor_count"])
        self.assertNotIn(cache / "enormous-execution-cache.json", opened)
        full_payload_prewarm.assert_not_called()
        plan_execution.assert_not_called()

    def test_hydration_reads_one_verified_shard_and_returns_stage_overlays(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "cache"
            replay_id = "replay_0123456789abcdef"
            hydration_relative = f"film-room-hydration/{replay_id}.json"
            hydration_path = cache / hydration_relative
            plan_hash = "plan-hash"
            write_json(
                hydration_path,
                {
                    "schema_version": FILM_ROOM_HYDRATION_SCHEMA,
                    "replay_window_id": replay_id,
                    "plan_hash": plan_hash,
                    "plan_path": "plan.json",
                    "source_id": "chain-200",
                    "source_kind": "chain_record",
                    "match_id": "J03WOH",
                    "period": "firstHalf",
                    "anchor_frame_id": 200,
                    "padding_seconds": 2.0,
                    "chain_record": chain_record(200),
                },
            )
            app_service.FILM_ROOM_REPLAY_INDEX[replay_id] = {
                "replay_window_id": replay_id,
                "plan_hash": plan_hash,
                "plan_path": "plan.json",
                "source_id": "chain-200",
                "source_kind": "chain_record",
                "match_id": "J03WOH",
                "period": "firstHalf",
                "anchor_frame_id": 200,
                "padding_seconds": 2.0,
                "hydration_path": hydration_relative,
                "hydration_sha256": app_service.file_sha256(hydration_path),
            }
            replay = {
                "schema_version": "1.0",
                "replay_window_id": replay_id,
                "source_kind": "chain_record",
                "source_id": "chain-200",
                "match_id": "J03WOH",
                "period": "firstHalf",
                "frame_rate_hz": 25.0,
                "start_frame_id": 150,
                "end_frame_id": 250,
                "anchor_frame_id": 200,
                "generated_at": "deterministic",
                "canonical_sources": {},
                "pitch": {"length_m": 105.0, "width_m": 68.0, "coordinate_contract": "centered_metres"},
                "frames": [],
            }
            with (
                patch("tqe.workshop.app_service.CACHE_ROOT", cache),
                patch("tqe.workshop.app_service.replay_window_from_canonical", return_value=replay),
            ):
                response = film_room_replay_window_response(
                    {"replay_window_id": replay_id},
                    output_root=root / "runtime",
                )

        self.assertEqual(3, len(response["replay"]["overlays"]["stages"]))
        self.assertEqual("regain", response["replay"]["overlays"]["stages"][0]["label"])
        self.assertTrue(response["replay"]["overlays"]["carry_trails"])


if __name__ == "__main__":
    unittest.main()
