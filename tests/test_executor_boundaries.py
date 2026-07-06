from __future__ import annotations

import ast
import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

from tqe.runtime import executor
from tqe.runtime.capabilities import (
    PRIMITIVE_IMPLEMENTATION_NAMES,
    RELOCATED_IMPLEMENTATION_MODULES,
    RELATION_IMPLEMENTATION_NAMES,
    build_primitive_registry,
    build_relation_registry,
)
from tqe.runtime.catalog import default_catalog
from tqe.runtime.ir import (
    BoundCatalogNode,
    BoundQueryPlan,
    Cardinality,
    CatalogOutput,
    ClassificationMode,
    ComplexityLimits,
    CoverageDeclaration,
    EntityScope,
    ExecutionMode,
    MissingDataSemantics,
    NodeKind,
    PayloadType,
    PlanStatus,
    TemporalContainer,
    Unit,
    UnknownEvidencePolicy,
)
from tqe.runtime.values import FrameSignal, RuntimeValue


def write_data_manifest(path: Path, files: list[Path]) -> None:
    payload = {
        "schema_version": "entrelineas_data_manifest.v1",
        "files": [
            {
                "path": file_path.as_posix(),
                "size": file_path.stat().st_size,
                "sha256": executor.sha256_path(file_path),
            }
            for file_path in files
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class ExecutorRegistryBoundaryTests(unittest.TestCase):
    def test_capability_registry_matches_catalog_without_legacy_noop_debt(self) -> None:
        catalog = default_catalog()
        catalog_primitives = {entry.name for entry in catalog.primitives}
        catalog_relations = {entry.name for entry in catalog.relations}
        primitive_names = [name for name, _ in PRIMITIVE_IMPLEMENTATION_NAMES]
        relation_names = [name for name, _ in RELATION_IMPLEMENTATION_NAMES]

        self.assertEqual(len(primitive_names), len(set(primitive_names)))
        self.assertEqual(len(relation_names), len(set(relation_names)))
        self.assertEqual(catalog_primitives, set(primitive_names))
        self.assertEqual(catalog_relations, set(relation_names))
        self.assertEqual(set(), set(primitive_names) - catalog_primitives)

        primitive_registry = build_primitive_registry(vars(executor))
        relation_registry = build_relation_registry(vars(executor))

        self.assertEqual(set(primitive_names), set(primitive_registry))
        self.assertEqual(set(relation_names), set(relation_registry))
        self.assertEqual(
            {operator.name for operator in catalog.operators},
            set(executor.SUPPORTED_PREDICATE_OPERATORS),
        )

    def test_shared_executor_capability_name_leaks_are_frozen(self) -> None:
        observed = shared_executor_capability_mentions()

        self.assertEqual(EXPECTED_SHARED_CAPABILITY_MENTIONS, observed)

    def test_non_catalog_shared_helper_leaks_are_frozen(self) -> None:
        observed = shared_executor_helper_mentions(EXPECTED_SHARED_HELPER_MENTION_COUNTS)

        self.assertEqual(EXPECTED_SHARED_HELPER_MENTION_COUNTS, observed)

    def test_node_parameter_reads_are_catalog_declared(self) -> None:
        observed = node_parameter_reads_by_capability()
        catalog_parameters = {
            entry.name: {parameter.name for parameter in entry.parameters}
            for entry in default_catalog().primitives + default_catalog().relations
        }

        undeclared = {
            capability: sorted(parameters - catalog_parameters[capability])
            for capability, parameters in observed.items()
            if parameters - catalog_parameters[capability]
        }

        self.assertEqual({}, undeclared)

    def test_node_parameter_read_requires_bound_catalog_parameter(self) -> None:
        node = BoundCatalogNode(
            kind=NodeKind.PRIMITIVE,
            node_id="sample_node",
            catalog_ref="sample_capability",
            version="0.1.0",
            outputs=[],
            resolved_parameters={},
        )

        with self.assertRaisesRegex(
            executor.UndeclaredNodeParameterError,
            "sample_capability.sample_node read undeclared parameter missing_parameter",
        ):
            executor.node_parameter_number(node, "missing_parameter")

    def test_witness_selection_requires_exact_anchor_id_not_same_frame(self) -> None:
        catalog = default_catalog()
        anchor_output = next(
            output
            for entry in catalog.relations
            if entry.name == "geometric_progressive_corridor"
            for output in entry.outputs
            if output.name == "anchor_evaluations"
        )
        state = SimpleNamespace(
            runtime_values={
                "progressive_corridor": {
                    "anchor_evaluations": RuntimeValue(
                        output=anchor_output,
                        value=[
                            {
                                "anchor_id": "other_anchor",
                                "anchor_frame_id": 100,
                                "evaluation_status": "PASS",
                                "relation_count": 1,
                                "witness_relation_id": "wrong_relation",
                            }
                        ],
                    )
                }
            }
        )
        anchor = executor.RuntimeAnchor(
            anchor_id="wanted_anchor",
            semantic_key="wanted_anchor",
            match_id="synthetic",
            period="firstHalf",
            anchor_frame_id=100,
            source_node_id="anchors",
            output_name="anchor_evaluations",
            start_frame_id=100,
            end_frame_id=100,
            attributes={"anchor_id": "wanted_anchor", "anchor_frame_id": 100},
        )

        self.assertIsNone(
            executor.selected_relation_id_for_anchor(
                state=state,
                anchor=anchor,
                source_node_id="progressive_corridor",
            )
        )

    def test_anchor_evaluation_counts_obey_relation_complexity_limit(self) -> None:
        output = CatalogOutput(
            name="anchor_evaluations",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ENUM,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=["evaluation_status", "relation_count"],
            coverage=CoverageDeclaration(
                status_field="evaluation_status",
                count_field="relation_count",
            ),
        )
        node = BoundCatalogNode(
            kind=NodeKind.RELATION,
            node_id="corridor_relation",
            catalog_ref="geometric_progressive_corridor",
            version="0.1.0",
            outputs=[output],
            resolved_parameters={},
        )
        state = SimpleNamespace(
            runtime_values={
                "corridor_relation": {
                    "anchor_evaluations": RuntimeValue(
                        output=output,
                        value=[
                            {
                                "anchor_id": "anchor-1",
                                "evaluation_status": "PASS",
                                "relation_count": 2,
                            }
                        ],
                    )
                }
            }
        )

        with self.assertRaisesRegex(RuntimeError, "max_relations_per_anchor=1"):
            executor.enforce_runtime_complexity_limits(
                state=state,
                node=node,
                bound_plan=minimal_bound_plan(max_relations_per_anchor=1),
            )

    def test_perf1_cache_key_mutates_for_every_director_component(self) -> None:
        node = BoundCatalogNode(
            kind=NodeKind.PRIMITIVE,
            node_id="sample_node",
            catalog_ref="sample_capability",
            version="0.1.0",
            outputs=[],
            resolved_parameters={"threshold": {"payload_type": "number", "value": 1.0, "unit": "metre"}},
        )
        state = SimpleNamespace(
            match_id="J03WOH",
            period="firstHalf",
            params=executor.RuntimeParameters(values={"analysis_rate_hz": 5}),
            data_scope_manifest_entries=[
                {"path": "positions/match_id=J03WOH/period=firstHalf.parquet", "size": 10, "sha256": "a"}
            ],
            perspective_team_role="home",
            perspective_team_id="home-id",
            defending_team_role="away",
            defending_team_id="away-id",
        )
        upstream = [{"input_name": "source", "source_node_id": "source_node", "output_name": "anchors", "cache_key": "upstream-a"}]
        base = executor.derive_node_cache_key(
            node=node,
            state=state,
            upstream_lineage=upstream,
            code_epoch="epoch-a",
        )["cache_key"]
        node_with_resolved_value_change = BoundCatalogNode(
            kind=NodeKind.PRIMITIVE,
            node_id="sample_node",
            catalog_ref="sample_capability",
            version="0.1.0",
            outputs=[],
            resolved_parameters={"threshold": {"payload_type": "number", "value": 2.0, "unit": "metre"}},
        )

        cases = [
            executor.derive_node_cache_key(
                node=node,
                state=state,
                upstream_lineage=upstream,
                cache_schema_version="perf1_node_cache_key.v2",
                code_epoch="epoch-a",
            )["cache_key"],
            executor.derive_node_cache_key(
                node=node,
                state=state,
                upstream_lineage=upstream,
                code_epoch="epoch-b",
            )["cache_key"],
            executor.derive_node_cache_key(
                node=node.model_copy(update={"version": "0.2.0"}),
                state=state,
                upstream_lineage=upstream,
                code_epoch="epoch-a",
            )["cache_key"],
            executor.derive_node_cache_key(
                node=node_with_resolved_value_change,
                state=state,
                upstream_lineage=upstream,
                code_epoch="epoch-a",
            )["cache_key"],
            executor.derive_node_cache_key(
                node=node,
                state=state,
                upstream_lineage=[{**upstream[0], "cache_key": "upstream-b"}],
                code_epoch="epoch-a",
            )["cache_key"],
            executor.derive_node_cache_key(
                node=node,
                state=SimpleNamespace(
                    **{
                        **state.__dict__,
                        "data_scope_manifest_entries": [
                            {
                                "path": "positions/match_id=J03WOH/period=firstHalf.parquet",
                                "size": 10,
                                "sha256": "b",
                            }
                        ],
                    }
                ),
                upstream_lineage=upstream,
                code_epoch="epoch-a",
            )["cache_key"],
            executor.derive_node_cache_key(
                node=node,
                state=SimpleNamespace(**{**state.__dict__, "match_id": "J03WOY"}),
                upstream_lineage=upstream,
                code_epoch="epoch-a",
            )["cache_key"],
            executor.derive_node_cache_key(
                node=node,
                state=SimpleNamespace(**{**state.__dict__, "period": "secondHalf"}),
                upstream_lineage=upstream,
                code_epoch="epoch-a",
            )["cache_key"],
            executor.derive_node_cache_key(
                node=node,
                state=SimpleNamespace(
                    **{
                        **state.__dict__,
                        "params": executor.RuntimeParameters(values={"analysis_rate_hz": 10}),
                    }
                ),
                upstream_lineage=upstream,
                code_epoch="epoch-a",
            )["cache_key"],
            executor.derive_node_cache_key(
                node=node,
                state=SimpleNamespace(**{**state.__dict__, "perspective_team_role": "away"}),
                upstream_lineage=upstream,
                code_epoch="epoch-a",
            )["cache_key"],
        ]

        self.assertEqual(len(cases), len(set(cases)))
        self.assertTrue(all(item != base for item in cases))

    def test_perf1_cache_key_canonicalizes_expanded_defaults(self) -> None:
        first = BoundCatalogNode(
            kind=NodeKind.PRIMITIVE,
            node_id="node_a",
            catalog_ref="sample_capability",
            version="0.1.0",
            outputs=[],
            resolved_parameters={
                "zeta": {"payload_type": "number", "value": 2.0, "unit": "metre"},
                "alpha": {"payload_type": "number", "value": 1.0, "unit": "metre"},
            },
        )
        second = BoundCatalogNode(
            kind=NodeKind.PRIMITIVE,
            node_id="node_b",
            catalog_ref="sample_capability",
            version="0.1.0",
            outputs=[],
            resolved_parameters={
                "alpha": {"payload_type": "number", "value": 1.0, "unit": "metre"},
                "zeta": {"payload_type": "number", "value": 2.0, "unit": "metre"},
            },
        )
        state = SimpleNamespace(
            match_id="J03WOH",
            period="firstHalf",
            params=executor.RuntimeParameters(values={"b": 2, "a": 1}),
            data_scope_manifest_entries=[],
            perspective_team_role="home",
            perspective_team_id="home-id",
            defending_team_role="away",
            defending_team_id="away-id",
        )

        self.assertEqual(
            executor.derive_node_cache_key(node=first, state=state, upstream_lineage=[], code_epoch="epoch")[
                "cache_key"
            ],
            executor.derive_node_cache_key(node=second, state=state, upstream_lineage=[], code_epoch="epoch")[
                "cache_key"
            ],
        )

    def test_perf1_persistent_cache_detects_corrupt_output_without_serving(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = executor.PersistentNodeOutputCache(Path(directory))
            preimage = {
                "cache_schema_version": executor.CACHE_SCHEMA_VERSION,
                "code_epoch": "epoch",
                "node_semantic_identity": {"catalog_ref": "sample"},
                "upstream_lineage": [],
                "data_scope": {"match_id": "J03WOH", "period": "firstHalf", "manifest_entries": []},
                "perspective_bindings": {"perspective_team_role": "home"},
            }
            key = executor.stable_hash(preimage)
            cache.store(key=key, preimage=preimage, output={"records": [{"value": 1}]})
            path = cache.path_for(key)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["output"]["records"][0]["value"] = 2
            path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

            output, status = cache.load(key=key, preimage=preimage)

        self.assertIsNone(output)
        self.assertEqual("detected_never_served", status)

    def test_perf1_persistent_cache_detects_corrupt_preimage_without_serving(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = executor.PersistentNodeOutputCache(Path(directory))
            preimage = {
                "cache_schema_version": executor.CACHE_SCHEMA_VERSION,
                "code_epoch": "epoch",
                "node_semantic_identity": {"catalog_ref": "sample"},
                "upstream_lineage": [],
                "data_scope": {"match_id": "J03WOH", "period": "firstHalf", "manifest_entries": []},
                "perspective_bindings": {"perspective_team_role": "home"},
            }
            key = executor.stable_hash(preimage)
            cache.store(key=key, preimage=preimage, output={"records": [{"value": 1}]})
            path = cache.path_for(key)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["key_preimage"]["data_scope"]["period"] = "secondHalf"
            path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

            output, status = cache.load(key=key, preimage=preimage)

        self.assertIsNone(output)
        self.assertEqual("detected_never_served", status)

    def test_perf1_persistent_cache_round_trips_frame_signal_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = executor.PersistentNodeOutputCache(Path(directory))
            preimage = {
                "cache_schema_version": executor.CACHE_SCHEMA_VERSION,
                "code_epoch": "epoch",
                "node_semantic_identity": {"catalog_ref": "sample"},
                "upstream_lineage": [],
                "data_scope": {"match_id": "J03WOH", "period": "firstHalf", "manifest_entries": []},
                "perspective_bindings": {"perspective_team_role": "home"},
            }
            key = executor.stable_hash(preimage)
            frame_signal = FrameSignal(
                frame_ids=[10, 20],
                values=["PASS", None],
                unknown_mask=[False, True],
                unit=Unit.NONE,
                entity_scope=EntityScope.ANCHOR,
            )
            cache.store(key=key, preimage=preimage, output={"status": frame_signal})

            output, status = cache.load(key=key, preimage=preimage)

        self.assertEqual("persistent_hit", status)
        self.assertIsInstance(output["status"], FrameSignal)
        self.assertEqual(frame_signal, output["status"])

    def test_perf1_encode_cache_output_rejects_ambiguous_containers(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "tuple"):
            executor.encode_cache_output({"value": (1, 2)})
        with self.assertRaisesRegex(RuntimeError, "ndarray"):
            executor.encode_cache_output({"value": np.array([1, 2])})

    def test_perf1_parallel_pool_falls_back_when_process_pool_is_unavailable(self) -> None:
        with mock.patch.object(
            executor.concurrent.futures,
            "ProcessPoolExecutor",
            side_effect=PermissionError("sysconf denied"),
        ):
            pool, backend = executor.period_worker_pool(2)
        try:
            self.assertEqual("thread_fallback_process_pool_unavailable", backend)
            self.assertIsInstance(pool, executor.concurrent.futures.ThreadPoolExecutor)
        finally:
            pool.shutdown(wait=True)

    def test_canonical_data_manifest_uses_manifest_hash_without_default_content_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "canonical"
            root.mkdir()
            data_file = root / "sample.parquet"
            data_file.write_text("one", encoding="utf-8")
            manifest = Path(directory) / "manifest.json"
            write_data_manifest(manifest, [data_file])

            with mock.patch.dict("os.environ", {"TQE_DATA_MANIFEST_PATH": str(manifest)}, clear=False):
                with mock.patch.object(executor, "sha256_path", side_effect=AssertionError("deep hash used")):
                    observed = executor.canonical_data_manifest_hash(root)
            expected = executor.file_content_hash(manifest, schema_version="canonical_data_manifest_file.v1")

        self.assertEqual(
            expected,
            observed,
        )

    def test_canonical_data_manifest_default_detects_size_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "canonical"
            root.mkdir()
            data_file = root / "sample.parquet"
            data_file.write_text("one", encoding="utf-8")
            manifest = Path(directory) / "manifest.json"
            write_data_manifest(manifest, [data_file])
            data_file.write_text("longer", encoding="utf-8")

            with mock.patch.dict("os.environ", {"TQE_DATA_MANIFEST_PATH": str(manifest)}, clear=False):
                with self.assertRaisesRegex(RuntimeError, "size mismatch"):
                    executor.canonical_data_manifest_hash(root)

    def test_canonical_data_manifest_deep_verify_detects_sha_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "canonical"
            root.mkdir()
            data_file = root / "sample.parquet"
            data_file.write_text("one", encoding="utf-8")
            manifest = Path(directory) / "manifest.json"
            write_data_manifest(manifest, [data_file])
            data_file.write_text("two", encoding="utf-8")

            with mock.patch.dict(
                "os.environ",
                {"TQE_DATA_MANIFEST_PATH": str(manifest), "TQE_DEEP_VERIFY": "1"},
                clear=False,
            ):
                with self.assertRaisesRegex(RuntimeError, "sha256 mismatch"):
                    executor.canonical_data_manifest_hash(root)

    def test_pass_family_relocation_is_registry_only(self) -> None:
        source = Path(executor.__file__).resolve().read_text(encoding="utf-8")
        self.assertNotIn("pass_family", source)

        primitive_registry = build_primitive_registry(vars(executor))
        relation_registry = build_relation_registry(vars(executor))
        relocated_capabilities = {
            "action_event_anchor": primitive_registry["action_event_anchor"],
            "controlled_pass_episode": primitive_registry["controlled_pass_episode"],
            "one_touch_relay_episode": primitive_registry["one_touch_relay_episode"],
            "opponents_bypassed_by_action": relation_registry["opponents_bypassed_by_action"],
        }

        for implementation_name in RELOCATED_IMPLEMENTATION_MODULES:
            self.assertFalse(hasattr(executor, implementation_name), implementation_name)
        for implementation in relocated_capabilities.values():
            self.assertEqual("tqe.runtime.capabilities.pass_family", implementation.__module__)


    def test_corridor_family_relocation_is_registry_only(self) -> None:
        source = Path(executor.__file__).resolve().read_text(encoding="utf-8")
        self.assertNotIn("corridor_family", source)

        primitive_registry = build_primitive_registry(vars(executor))
        relation_registry = build_relation_registry(vars(executor))
        relocated_capabilities = {
            "geometric_progressive_corridor": relation_registry["geometric_progressive_corridor"],
            "geometric_progressive_corridor_from_anchor_set": relation_registry[
                "geometric_progressive_corridor_from_anchor_set"
            ],
            "relation_destination_entry": primitive_registry["relation_destination_entry"],
            "relation_destination_entry_classification": primitive_registry[
                "relation_destination_entry_classification"
            ],
        }

        for implementation_name in (
            "relation_geometric_progressive_corridor",
            "primitive_relation_destination_entry_classification",
        ):
            self.assertFalse(hasattr(executor, implementation_name), implementation_name)
        for implementation in relocated_capabilities.values():
            self.assertEqual("tqe.runtime.capabilities.corridor_family", implementation.__module__)


    def test_lines_family_relocation_is_registry_only(self) -> None:
        source = Path(executor.__file__).resolve().read_text(encoding="utf-8")
        self.assertNotIn("lines_family", source)

        primitive_registry = build_primitive_registry(vars(executor))
        relocated_capabilities = {
            "defensive_line_model": primitive_registry["defensive_line_model"],
            "multi_line_model": primitive_registry["multi_line_model"],
            "relative_position_to_line": primitive_registry["relative_position_to_line"],
            "receiver_line_transition_during_pass_leg": primitive_registry[
                "receiver_line_transition_during_pass_leg"
            ],
            "controlled_line_break_episode": primitive_registry["controlled_line_break_episode"],
        }

        for implementation_name in (
            "primitive_defensive_line_model",
            "primitive_multi_line_model",
            "primitive_relative_position_to_line",
            "primitive_receiver_line_transition_during_pass_leg",
            "primitive_controlled_line_break_episode",
        ):
            self.assertFalse(hasattr(executor, implementation_name), implementation_name)
        for implementation in relocated_capabilities.values():
            self.assertEqual("tqe.runtime.capabilities.lines_family", implementation.__module__)


    def test_offball_family_relocation_is_registry_only(self) -> None:
        source = Path(executor.__file__).resolve().read_text(encoding="utf-8")
        self.assertNotIn("offball_family", source)

        primitive_registry = build_primitive_registry(vars(executor))
        relation_registry = build_relation_registry(vars(executor))
        relocated_capabilities = {
            "marking": primitive_registry["marking"],
            "off_ball_run": primitive_registry["off_ball_run"],
            "off_ball_run_type": primitive_registry["off_ball_run_type"],
            "time_to_arrival": primitive_registry["time_to_arrival"],
            "support_arrival_relation": relation_registry["support_arrival_relation"],
        }

        for implementation_name in (
            "primitive_marking",
            "primitive_off_ball_run",
            "primitive_off_ball_run_type",
            "primitive_time_to_arrival",
            "relation_support_arrival",
        ):
            self.assertFalse(hasattr(executor, implementation_name), implementation_name)
        for implementation in relocated_capabilities.values():
            self.assertEqual("tqe.runtime.capabilities.offball_family", implementation.__module__)


    def test_teamshape_family_relocation_is_registry_only(self) -> None:
        source = Path(executor.__file__).resolve().read_text(encoding="utf-8")
        self.assertNotIn("teamshape_family", source)

        primitive_registry = build_primitive_registry(vars(executor))
        relation_registry = build_relation_registry(vars(executor))
        relocated_capabilities = {
            "team_compactness": primitive_registry["team_compactness"],
            "change_across_anchor": primitive_registry["change_across_anchor"],
            "cover_shadow": primitive_registry["cover_shadow"],
            "ball_lateral_fraction": primitive_registry["ball_lateral_fraction"],
            "defensive_outfield_centroid": primitive_registry["defensive_outfield_centroid"],
            "signed_lateral_shift": primitive_registry["signed_lateral_shift"],
            "pressure_on_carrier": relation_registry["pressure_on_carrier"],
            "team_press": relation_registry["team_press"],
            "local_number_relation": relation_registry["local_number_relation"],
        }

        for implementation_name in (
            "primitive_team_compactness",
            "primitive_change_across_anchor",
            "primitive_cover_shadow",
            "primitive_ball_lateral_fraction",
            "primitive_defensive_outfield_centroid",
            "primitive_signed_lateral_shift",
            "relation_pressure_on_carrier",
            "relation_team_press",
            "relation_local_number",
        ):
            self.assertFalse(hasattr(executor, implementation_name), implementation_name)
        for implementation in relocated_capabilities.values():
            self.assertEqual("tqe.runtime.capabilities.teamshape_family", implementation.__module__)


    def test_final_sweep_leaves_no_registered_inline_capability_implementations(self) -> None:
        primitive_registry = build_primitive_registry(vars(executor))
        relation_registry = build_relation_registry(vars(executor))
        relocated_names = set(RELOCATED_IMPLEMENTATION_MODULES)

        inline_primitives = {
            implementation_name
            for capability_name, implementation_name in PRIMITIVE_IMPLEMENTATION_NAMES
            if implementation_name not in relocated_names
        }
        inline_relations = {
            implementation_name
            for _capability_name, implementation_name in RELATION_IMPLEMENTATION_NAMES
            if implementation_name not in relocated_names
        }

        self.assertEqual(set(), inline_primitives)
        self.assertEqual(set(), inline_relations)
        for capability_name, implementation in primitive_registry.items():
            self.assertNotEqual("tqe.runtime.executor", implementation.__module__, capability_name)
        for capability_name, implementation in relation_registry.items():
            self.assertNotEqual("tqe.runtime.executor", implementation.__module__, capability_name)


EXPECTED_SHARED_CAPABILITY_MENTIONS = {}


EXPECTED_SHARED_HELPER_MENTION_COUNTS = {}


def minimal_bound_plan(*, max_relations_per_anchor: int) -> BoundQueryPlan:
    return BoundQueryPlan(
        plan_id="synthetic_plan",
        plan_version="1.0.0",
        plan_status=PlanStatus.EXPERIMENTAL,
        recipe_id="synthetic_recipe",
        recipe_version="1.0.0",
        invocation_id="synthetic_invocation",
        match_ids=["synthetic"],
        periods=["firstHalf"],
        perspective_team_role="home",
        max_results=1,
        execution_mode=ExecutionMode.EXECUTE,
        unknown_evidence_policy=UnknownEvidencePolicy.EXCLUDE_CANDIDATE,
        classification_mode=ClassificationMode.PARTIAL_DECLARED,
        classification_rules=[],
        requested_evidence=[],
        complexity_limits=ComplexityLimits(max_relations_per_anchor=max_relations_per_anchor),
        resolved_parameters=[],
        nodes=[],
        plan_hash="synthetic-plan-hash",
        bound_plan_hash="synthetic-bound-plan-hash",
    )


def shared_executor_capability_mentions() -> dict[str, set[str]]:
    source, lines, shared_source = shared_executor_source()
    del source
    capability_names = {
        entry.name for entry in default_catalog().primitives + default_catalog().relations
    }
    observed: dict[str, set[str]] = {}
    for name in sorted(capability_names):
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")
        for match in pattern.finditer(shared_source):
            line_number = shared_source[: match.start()].count("\n") + 1
            observed.setdefault(name, set()).add(lines[line_number - 1].strip())
    return observed


def shared_executor_helper_mentions(expected: dict[str, int]) -> dict[str, int]:
    _source, _lines, shared_source = shared_executor_source()
    return {needle: shared_source.count(needle) for needle in expected}


def shared_executor_source() -> tuple[str, list[str], str]:
    source_path = Path(executor.__file__).resolve()
    source = source_path.read_text(encoding="utf-8")
    lines = source.splitlines()
    module = ast.parse(source)
    implementation_lines: set[int] = set()
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and (
            node.name.startswith("primitive_") or node.name.startswith("relation_")
        ):
            implementation_lines.update(range(node.lineno, node.end_lineno + 1))

    shared_source = "\n".join(
        "" if line_number in implementation_lines else line
        for line_number, line in enumerate(lines, start=1)
    )
    return source, lines, shared_source


def node_parameter_reads_by_capability() -> dict[str, set[str]]:
    capabilities_for_implementation: dict[str, set[str]] = {}
    for capability_name, implementation_name in (
        *PRIMITIVE_IMPLEMENTATION_NAMES,
        *RELATION_IMPLEMENTATION_NAMES,
    ):
        capabilities_for_implementation.setdefault(implementation_name, set()).add(capability_name)
    implementation_spans: dict[str, ast.FunctionDef] = {}
    for module_path in implementation_source_paths():
        module = ast.parse(module_path.read_text(encoding="utf-8"))
        implementation_spans.update(
            {
                node.name: node
                for node in module.body
                if isinstance(node, ast.FunctionDef) and node.name in capabilities_for_implementation
            }
        )
    reads: dict[str, set[str]] = {}
    for implementation_name, function_node in implementation_spans.items():
        capability_names = capabilities_for_implementation[implementation_name]
        for node in ast.walk(function_node):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id == "node_parameter_event_type_filter":
                for capability_name in capability_names:
                    reads.setdefault(capability_name, set()).add("event_type_filter")
                continue
            if node.func.id not in {"node_parameter_number", "node_parameter_integer", "node_parameter_text"}:
                continue
            if len(node.args) != 2:
                for capability_name in capability_names:
                    reads.setdefault(capability_name, set()).add(
                        f"invalid_call_arity_at_line_{node.lineno}"
                    )
                continue
            name_arg = node.args[1]
            if not isinstance(name_arg, ast.Constant) or not isinstance(name_arg.value, str):
                for capability_name in capability_names:
                    reads.setdefault(capability_name, set()).add(
                        f"dynamic_parameter_name_at_line_{node.lineno}"
                    )
                continue
            for capability_name in capability_names:
                reads.setdefault(capability_name, set()).add(name_arg.value)
    return reads


def implementation_source_paths() -> tuple[Path, ...]:
    return (
        Path(executor.__file__).resolve(),
        Path(executor.__file__).resolve().parent / "capabilities" / "pass_family.py",
        Path(executor.__file__).resolve().parent / "capabilities" / "corridor_family.py",
        Path(executor.__file__).resolve().parent / "capabilities" / "lines_family.py",
        Path(executor.__file__).resolve().parent / "capabilities" / "offball_family.py",
        Path(executor.__file__).resolve().parent / "capabilities" / "teamshape_family.py",
        Path(executor.__file__).resolve().parent / "capabilities" / "possession_family.py",
        Path(executor.__file__).resolve().parent / "capabilities" / "sequence_family.py",
        Path(executor.__file__).resolve().parent / "capabilities" / "kinematics_family.py",
    )
