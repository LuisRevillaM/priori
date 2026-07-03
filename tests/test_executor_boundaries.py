from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

from tqe.runtime import executor
from tqe.runtime.capabilities import (
    LEGACY_NOOP_CAPABILITIES,
    PREDICATE_IMPLEMENTATION_NAMES,
    PRIMITIVE_IMPLEMENTATION_NAMES,
    RELOCATED_IMPLEMENTATION_MODULES,
    RELATION_IMPLEMENTATION_NAMES,
    build_predicate_registry,
    build_primitive_registry,
    build_relation_registry,
)
from tqe.runtime.catalog import default_catalog
from tqe.runtime.ir import BoundCatalogNode, NodeKind


class ExecutorRegistryBoundaryTests(unittest.TestCase):
    def test_capability_registry_matches_catalog_with_legacy_noop_debt(self) -> None:
        catalog = default_catalog()
        catalog_primitives = {entry.name for entry in catalog.primitives}
        catalog_relations = {entry.name for entry in catalog.relations}
        primitive_names = [name for name, _ in PRIMITIVE_IMPLEMENTATION_NAMES]
        relation_names = [name for name, _ in RELATION_IMPLEMENTATION_NAMES]

        self.assertEqual(len(primitive_names), len(set(primitive_names)))
        self.assertEqual(len(relation_names), len(set(relation_names)))
        self.assertEqual(catalog_primitives, set(primitive_names) - LEGACY_NOOP_CAPABILITIES)
        self.assertEqual(catalog_relations, set(relation_names))
        self.assertEqual(LEGACY_NOOP_CAPABILITIES, set(primitive_names) - catalog_primitives)

        primitive_registry = build_primitive_registry(vars(executor))
        relation_registry = build_relation_registry(vars(executor))
        predicate_registry = build_predicate_registry(vars(executor))

        self.assertEqual(set(primitive_names), set(primitive_registry))
        self.assertEqual(set(relation_names), set(relation_registry))
        self.assertEqual({name for name, _ in PREDICATE_IMPLEMENTATION_NAMES}, set(predicate_registry))

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


# This is the F2-0 freeze line, not a cleanup.  Destination-entry lines are the
# V8/V10 audit leaks named in ADR 0012; the import/helper lines are existing
# capability-family code still outside primitive_/relation_ bodies until later
# extraction packets move those families out of executor.py.  This guard only
# sees catalog identifiers; non-catalog helper leaks are frozen separately below.
EXPECTED_SHARED_CAPABILITY_MENTIONS = {
    "acceleration": {
        '"UNKNOWN if either velocity window lacks tracking endpoints or if observed speed/acceleration "',
        "acceleration = delta_speed / dt_seconds",
        "if abs(acceleration) > maximum_abs_acceleration_mps2:",
        '\"acceleration_mps2\": round(float(acceleration), 3),',
        "if abs(delta_speed) < minimum_abs_delta_speed_mps or abs(acceleration) < minimum_abs_acceleration_mps2:",
    },
    "join_episode_sets": {
        'raise RuntimeError(f"Unsupported join_episode_sets temporal_relation={temporal_relation}")',
    },
    "lane_occupancy": {
        "from tqe.runtime.lane_occupancy import LaneOccupancyConfig, evaluate_lane_occupancy",
    },
    "local_number_relation": {
        "from tqe.runtime.local_number_relation import (",
    },
    "marking": {
        '"no routine, role, marking scheme, planned play, intent, quality, or causation claim."',
    },
    "relation_destination_entry": {
        'if node.catalog_ref != "relation_destination_entry":',
    },
    "time_to_arrival": {
        'raise RuntimeError(f"Unsupported time_to_arrival candidate_scope: {candidate_scope}")',
    },
    "velocity": {
        '"UNKNOWN if either velocity window lacks tracking endpoints or if observed speed/acceleration "',
    },
}


EXPECTED_SHARED_HELPER_MENTION_COUNTS = {
    # V8-style frame-id fallback inside eq/neq predicate traces.
    'frame_id=optional_int(record.get("destination_entry_frame_id"))': 1,
    'or optional_int(record.get("outcome_frame_id"))': 1,
    'or optional_int(record.get("anchor_frame_id"))': 1,
    # Experimental trace fabricator body.
    # select_proof_results selection labels.
    "def select_proof_results": 1,
    '"proof_selected": True': 1,
    '"SWITCHED"': 2,
    '"RETAINED_NO_SWITCH"': 2,
    '"LOST_BEFORE_SWITCH"': 3,
}


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
    )
