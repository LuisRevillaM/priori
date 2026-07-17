from __future__ import annotations

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
from tqe.workshop.m1_2 import CapabilityGap, read_json, write_json


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
        "stage_2_minimum_numeric_field": "carry_forward_progression_m",
        "source_records": [
            {"transition_status": "PASS"},
            {"carry_status": "PASS", "carry_forward_progression_m": 11.2},
            {"controlled_pass_status": "PASS"},
        ],
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
            app_service.FILM_ROOM_PREWARM_STATE.clear()
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
            with (
                patch("tqe.workshop.app_service.CACHE_ROOT", cache),
                patch("tqe.workshop.app_service.canonical_match_time_ms", return_value=4_000),
            ):
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
        self.assertEqual(
            [80, 100, 120],
            [
                label["frame_id"]
                for label in item["descriptor"]["evidence_overlay"]["stage_labels"]
            ],
        )
        stage_two = item["descriptor"]["evidence_overlay"]["stage_labels"][1]
        self.assertEqual("at least 8 m", stage_two["label"])
        self.assertEqual(11.2, stage_two["observed_numeric_value"])
        self.assertEqual(4_000, item["descriptor"]["match_time_ms"])

    def test_rebuild_accepts_equivalent_absolute_hydration_plan_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "cache"
            plan_path = app_service.FILM_ROOM_R2_4_PLAN_PATH
            execution = {
                "role": "away",
                "execution": {
                    "execution_id": "exec-path-spelling",
                    "bound_plan_hash": "bound-path-spelling",
                    "results": [
                        {
                            "result_id": "path-spelling",
                            "classification": "PASS",
                            "requested_evidence": {"source_records": [chain_record(700)]},
                        }
                    ],
                },
                "cache_after_execute": {"cache_status": "HIT"},
                "bound_record": {"bound_plan_hash": "bound-path-spelling"},
            }
            with patch("tqe.workshop.app_service.CACHE_ROOT", cache):
                write_film_room_descriptor_fragment(
                    key="counterattack_sequence_rate",
                    role="away",
                    plan_path=plan_path.resolve(),
                    executions=[execution],
                    output_root=root / "runtime",
                )
                summary = write_film_room_descriptor_fragment(
                    key="counterattack_sequence_rate",
                    role="away",
                    plan_path=plan_path,
                    executions=[execution],
                    output_root=root / "runtime",
                )

        self.assertEqual(1, summary["descriptor_count"])

    def test_pressing_map_bundled_population_loads_lazy_descriptors_without_execution(self) -> None:
        table = read_json(app_service.FILM_ROOM_GALLERY_2_TABLE_PATH)
        pressing_spec = next(
            spec for spec in film_room_flagship_specs() if spec["key"] == "pressing_map"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "cache"
            with (
                patch("tqe.workshop.app_service.CACHE_ROOT", cache),
                patch(
                    "tqe.workshop.app_service.film_room_flagship_specs",
                    return_value=[pressing_spec],
                ),
            ):
                for role in ("away", "home"):
                    write_film_room_descriptor_fragment(
                        key="pressing_map",
                        role=role,
                        plan_path=Path(pressing_spec["plan_path"]),
                        executions=[
                            {
                                "role": role,
                                "execution": {
                                    "bound_plan_hash": f"bundled-{role}",
                                    "execution_id": f"bundled-{role}",
                                    "results": [],
                                },
                                "cache_after_execute": {"cache_status": "BUNDLE_BUILD"},
                                "bound_record": {"bound_plan_hash": f"bundled-{role}"},
                            }
                        ],
                        output_root=root / "runtime",
                    )
                index = build_film_room_descriptor_index(output_root=root / "runtime")

            fragments = [
                read_json(
                    cache
                    / app_service.FILM_ROOM_DESCRIPTOR_FRAGMENT_DIR
                    / f"pressing_map-{role}.json"
                )
                for role in ("away", "home")
            ]
            fragment = fragments[0]
            first = fragment["moments"][0]
            hydration = read_json(cache / first["hydration_path"])

        self.assertEqual(
            table["totals"]["population_count"],
            sum(len(item["moments"]) for item in fragments),
        )
        self.assertEqual(table["totals"]["population_count"], index["flagships"]["pressing_map"]["descriptor_count"])
        self.assertEqual("result", first["descriptor"]["source_kind"])
        self.assertEqual("REGAIN_LOCATION", first["descriptor"]["classification"])
        self.assertIn("zone_name", first["descriptor"]["requested_evidence"])
        self.assertNotIn("frames", first["descriptor"])
        self.assertIn("moment_record", hydration)
        self.assertNotIn("frames", hydration)

    def test_missing_pressing_cache_and_invalid_fragile_cache_do_not_take_down_retention(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "old-bundle-cache"
            counter_spec = next(
                spec
                for spec in film_room_flagship_specs()
                if spec["key"] == "counterattack_sequence_rate"
            )
            counter_plan_path = Path(counter_spec["plan_path"])
            counter_plan = read_json(counter_plan_path)
            with patch("tqe.workshop.app_service.CACHE_ROOT", cache):
                for role in ("away", "home"):
                    records = (
                        [chain_record(5000 + index * 100) for index in range(115)]
                        if role == "away"
                        else []
                    )
                    summary = write_film_room_descriptor_fragment(
                        key="counterattack_sequence_rate",
                        role=role,
                        plan_path=counter_plan_path,
                        executions=[
                            {
                                "role": role,
                                "execution": {
                                    "bound_plan_hash": f"retention-{role}",
                                    "execution_id": f"retention-{role}",
                                    "results": (
                                        [
                                            {
                                                "result_id": "retention-population",
                                                "classification": "PASS",
                                                "requested_evidence": {
                                                    "source_records": records
                                                },
                                            }
                                        ]
                                        if records
                                        else []
                                    ),
                                },
                                "cache_after_execute": {"cache_status": "OLD_BUNDLE"},
                                "bound_record": {
                                    "bound_plan_hash": f"retention-{role}"
                                },
                            }
                        ],
                        output_root=root / "runtime",
                    )
                    legacy_fragment = read_json(Path(summary["fragment_path"]))
                    legacy_fragment["schema_version"] = "film_room.descriptor_index.v1"
                    legacy_fragment.pop("code_epoch", None)
                    write_json(Path(summary["fragment_path"]), legacy_fragment)
                fragile_spec = next(
                    spec
                    for spec in film_room_flagship_specs()
                    if spec["key"] == "fragile_retention"
                )
                fragile_plan_path = Path(fragile_spec["plan_path"])
                fragile_plan = read_json(fragile_plan_path)
                for role in sorted(film_room_role_documents(fragile_plan)):
                    write_json(
                        cache
                        / app_service.FILM_ROOM_DESCRIPTOR_FRAGMENT_DIR
                        / f"fragile_retention-{role}.json",
                        {
                            "schema_version": "film_room.descriptor_index.v0",
                            "flagship_key": "fragile_retention",
                            "role": role,
                            "plan_hash": stable_hash(fragile_plan),
                            "plan_path": str(fragile_plan_path),
                            "bound_plan_hash": f"orphaned-{role}",
                            "moments": [],
                        },
                    )
                initialize_film_room_prewarm(
                    output_root=root / "fresh-runtime",
                    execution_enabled=False,
                )
                bootstrap = film_room_bootstrap_response(
                    output_root=root / "fresh-runtime"
                )

        pressing = bootstrap["flagship_responses"]["pressing_map"]
        retention = bootstrap["flagship_responses"]["counterattack_sequence_rate"]
        self.assertEqual("ready", bootstrap["state"])
        self.assertEqual(115, len(retention["answer"]["moments"]))
        self.assertIsNone(pressing["answer"])
        self.assertEqual("understood_but_not_expressible", pressing["outcome"])
        self.assertEqual(
            app_service.FILM_ROOM_BUNDLED_DESCRIPTOR_ABSENT,
            pressing["refusal"]["gap_code"],
        )
        self.assertEqual(
            "prewarmed_descriptor_absence",
            pressing["provider"],
        )
        self.assertEqual(
            "absent",
            next(
                item
                for item in app_service.FILM_ROOM_PREWARM_STATE["items"]
                if item["key"] == "fragile_retention"
            )["execution_status"],
        )

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
                            "code_epoch": app_service.film_room_descriptor_code_epoch(),
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
                patch(
                    "tqe.workshop.app_service.film_room_prewarmed_response"
                ) as full_payload_prewarm,
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
        self.assertEqual("meaning_expression.v0", bootstrap["answer"]["meaning_expression"]["schema_version"])
        self.assertTrue(bootstrap["answer"]["meaning_expression"]["meaning_clauses"])
        self.assertEqual([], bootstrap["answer"]["executions"])
        self.assertTrue(
            all(record.get("execution_performed") is False for record in bootstrap["prewarm_records"])
        )
        descriptor_records = [
            record
            for record in bootstrap["prewarm_records"]
            if record.get("prewarm_kind") == "descriptor_index_load"
        ]
        self.assertEqual(3, len(descriptor_records))
        fragile_record = next(
            record
            for record in bootstrap["prewarm_records"]
            if record.get("key") == "fragile_retention"
            and record.get("prewarm_kind") == "descriptor_index_load"
        )
        self.assertEqual("no_chain_descriptors", fragile_record["reason"])
        self.assertFalse(fragile_record["upgrade_applied"])
        self.assertEqual(2, index["flagships"]["counterattack_sequence_rate"]["descriptor_count"])
        coverage = bootstrap["answer"]["raw_evidence"]["descriptor_index"]["coverage"]
        self.assertEqual("returned_classified_result_source_records", coverage["reason_code"])
        self.assertEqual(2, coverage["shown_count"])
        self.assertGreater(coverage["population_count"], coverage["shown_count"])
        self.assertNotIn(cache / "enormous-execution-cache.json", opened)
        full_payload_prewarm.assert_not_called()
        plan_execution.assert_not_called()

    def test_old_schema_fragments_rebuild_from_disk_execution_caches_and_reach_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "cache"
            for spec_index, spec in enumerate(film_room_flagship_specs()):
                key = str(spec["key"])
                plan_path = Path(spec["plan_path"])
                plan_payload = read_json(plan_path)
                plan_hash = stable_hash(plan_payload)
                for role_index, (role, role_document) in enumerate(
                    sorted(film_room_role_documents(plan_payload).items())
                ):
                    bound_plan_hash = stable_hash(
                        {"fixture": "old-schema", "key": key, "role": role}
                    )
                    rows = []
                    if key == "counterattack_sequence_rate" and role == "away":
                        rows = [
                            {
                                "result_id": "old-result",
                                "classification": "PASS",
                                "requested_evidence": {
                                    "source_records": [chain_record(2400, marker="disk-cache")]
                                },
                            }
                        ]
                    cache_payload = {
                        "schema_version": "1.0",
                        "cache_key": stable_hash({"key": key, "role": role}),
                        "cache_identity": {
                            "bound_plan_hash": bound_plan_hash,
                            "scope": {"perspective_team_role": role},
                        },
                        "execution_record": {
                            "bound_plan_hash": bound_plan_hash,
                            "document": role_document,
                        },
                        "response": {
                            "bound_plan_hash": bound_plan_hash,
                            "execution_id": f"exec-{spec_index}-{role_index}",
                            "results": rows,
                        },
                    }
                    write_json(cache / f"{cache_payload['cache_key']}.json", cache_payload)
                    write_json(
                        cache / f"film-room-descriptor-fragments/{key}-{role}.json",
                        {
                            "schema_version": "film_room.descriptor_index.v0",
                            "flagship_key": key,
                            "role": role,
                            "plan_hash": plan_hash,
                            "plan_path": str(plan_path),
                            "bound_plan_hash": bound_plan_hash,
                            "execution_id": "old-execution",
                            "cache_status": "HIT",
                            "moments": [],
                        },
                    )
            with (
                patch("tqe.workshop.app_service.CACHE_ROOT", cache),
                patch("tqe.workshop.app_service.film_room_execute_document") as plan_execution,
                patch(
                    "tqe.workshop.app_service.film_room_prewarmed_response"
                ) as full_payload_prewarm,
            ):
                initialize_film_room_prewarm(
                    output_root=root / "fresh-runtime",
                    execution_enabled=False,
                )
                bootstrap = film_room_bootstrap_response(output_root=root / "fresh-runtime")
                replay_window_id = bootstrap["answer"]["moments"][0]["replay_window_id"]
                hydrated_marker = read_json(
                    cache / f"film-room-hydration/{replay_window_id}.json"
                )["chain_record"]["large_chain_payload_marker"]

        rebuild_records = [
            record
            for record in bootstrap["prewarm_records"]
            if record.get("prewarm_kind") == "descriptor_fragment_rebuild"
        ]
        self.assertEqual("ready", bootstrap["state"])
        self.assertEqual(1, len(bootstrap["answer"]["moments"]))
        self.assertEqual("disk-cache", hydrated_marker)
        self.assertEqual(4, len(rebuild_records))
        self.assertTrue(
            all("cache-key miss" in record["rebuild_reason"] for record in rebuild_records)
        )
        self.assertEqual(
            "complete_with_absences",
            app_service.FILM_ROOM_PREWARM_STATE["descriptor_rebuild"]["status"],
        )
        self.assertEqual(
            app_service.FILM_ROOM_BUNDLED_DESCRIPTOR_ABSENT,
            bootstrap["flagship_responses"]["pressing_map"]["refusal"]["gap_code"],
        )
        self.assertTrue(all(record["execution_performed"] is False for record in rebuild_records))
        plan_execution.assert_not_called()
        full_payload_prewarm.assert_not_called()

    def test_rebuild_failure_stays_warming_and_names_the_missing_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "empty-cache"
            cache.mkdir()
            with patch("tqe.workshop.app_service.CACHE_ROOT", cache):
                app_service.load_film_room_descriptor_index_safely(
                    output_root=root / "runtime"
                )

        state = app_service.FILM_ROOM_PREWARM_STATE
        self.assertEqual("warming", state["state"])
        self.assertEqual("complete_with_absences", state["descriptor_rebuild"]["status"])
        self.assertEqual(
            {
                "pressing_map",
                "fragile_retention",
                "counterattack_sequence_rate",
            },
            set(state["descriptor_absences"]),
        )
        self.assertIn(
            "found 0",
            state["descriptor_absences"]["fragile_retention"]["message"],
        )
        self.assertEqual(
            "absent",
            state["items"][0]["execution_status"],
        )

    def test_chain_rebuild_refuses_execution_payload_above_memory_guard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "cache"
            plan_path = app_service.FILM_ROOM_R2_4_PLAN_PATH
            role_document = film_room_role_documents(read_json(plan_path))["away"]
            bound_plan_hash = stable_hash({"fixture": "oversized-cache"})
            cache_payload = {
                "cache_identity": {
                    "bound_plan_hash": bound_plan_hash,
                    "scope": {"perspective_team_role": "away"},
                },
                "execution_record": {"document": role_document},
                "response": {"results": []},
            }
            cache_path = cache / "oversized.json"
            write_json(cache_path, cache_payload)
            with (
                patch("tqe.workshop.app_service.CACHE_ROOT", cache),
                patch("tqe.workshop.app_service.FILM_ROOM_REBUILD_MAX_PAYLOAD_BYTES", 1),
            ):
                with self.assertRaisesRegex(CapabilityGap, "bounded-memory limit"):
                    app_service.rebuild_film_room_descriptor_fragment(
                        key="counterattack_sequence_rate",
                        role="away",
                        plan_path=plan_path,
                        output_root=root / "runtime",
                        old_fragment={"bound_plan_hash": bound_plan_hash},
                    )

    def test_production_image_includes_legibility_meaning_expression(self) -> None:
        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
        relative = (
            "delivery/packets/r2-4-flagship/meaning-expressions/"
            "counterattack_initiation_sequence_rate.v0.json"
        )
        self.assertIn(f"COPY {relative} ", dockerfile)

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
