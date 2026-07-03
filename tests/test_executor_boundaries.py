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
    RELATION_IMPLEMENTATION_NAMES,
    build_predicate_registry,
    build_primitive_registry,
    build_relation_registry,
)
from tqe.runtime.catalog import default_catalog


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


# This is the F2-0 freeze line, not a cleanup.  Destination-entry lines are the
# V8/V10 audit leaks named in ADR 0012; the import/helper lines are existing
# capability-family code still outside primitive_/relation_ bodies until later
# extraction packets move those families out of executor.py.
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
        '"Observed nearest-opposition proximity only; no marking assignment, defensive scheme, "',
        '"no routine, role, marking scheme, planned play, intent, quality, or causation claim."',
    },
    "relation_destination_entry": {
        'if node.catalog_ref != "relation_destination_entry":',
    },
    "relation_destination_entry_classification": {
        '"source_node_id": "relation_destination_entry_classification",',
    },
    "relative_position_to_line": {
        "from tqe.runtime.relative_position_to_line import (",
    },
    "time_to_arrival": {
        'raise RuntimeError(f"Unsupported time_to_arrival candidate_scope: {candidate_scope}")',
    },
    "velocity": {
        '"UNKNOWN if either velocity window lacks tracking endpoints or if observed speed/acceleration "',
    },
}


def shared_executor_capability_mentions() -> dict[str, set[str]]:
    source_path = Path("src/tqe/runtime/executor.py")
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
