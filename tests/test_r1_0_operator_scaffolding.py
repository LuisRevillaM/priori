from __future__ import annotations

import json
import re
import unittest
from copy import deepcopy
from pathlib import Path

from tqe.runtime.binder import BindError, Binder, bind_document, bind_error_codes
from tqe.runtime.catalog import default_catalog
from tqe.runtime import binder as binder_module
from tqe.runtime import executor as executor_module
from tqe.runtime.ir import (
    Cardinality,
    CompositionOperatorSignature,
    EntityScope,
    MissingDataSemantics,
    OperatorInputDefinition,
    OperatorOutputDeclaration,
    PayloadType,
    TacticalQueryDocument,
    TemporalContainer,
    TypedValue,
    Unit,
)
from tqe.runtime.operators import (
    OPERATOR_SIGNATURES,
    build_operator_registry,
    declared_operator_signatures,
    registry_completeness_findings,
)


PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")
R1_OPERATOR_NAMES = (
    "typed_join",
    "extremum_over_set",
    "project_onto_axis",
    "delta_across_anchor",
)


def load_payload() -> dict:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def operator_output() -> dict:
    return {
        "name": "joined",
        "temporal_type": "episode_set",
        "payload_type": "boolean",
        "cardinality": "collection",
        "entity_scope": "anchor",
        "missing_data_semantics": "unknown",
    }


def add_operator_node(payload: dict, node: dict) -> dict:
    copy = deepcopy(payload)
    copy["draft_plan"]["nodes"].append(node)
    return copy


def sample_signature() -> CompositionOperatorSignature:
    return CompositionOperatorSignature(
        name="sample_operator",
        version="0.1.0",
        purpose="Synthetic signature for R1-0 binder validation tests.",
        inputs=[
            OperatorInputDefinition(
                name="source",
                temporal_type=TemporalContainer.EPISODE_SET,
                payload_type=PayloadType.BOOLEAN,
                cardinality=Cardinality.COLLECTION,
                entity_scope=EntityScope.POSSESSION,
            )
        ],
        outputs=[
            OperatorOutputDeclaration(
                name="joined",
                temporal_type=TemporalContainer.EPISODE_SET,
                payload_type=PayloadType.BOOLEAN,
                cardinality=Cardinality.COLLECTION,
                entity_scope=EntityScope.ANCHOR,
                missing_data_semantics=MissingDataSemantics.UNKNOWN,
            )
        ],
        coverage_propagation_rule_id="could_change_answer",
        witness_rule_id="selected_input",
    )


def bind_with_signature(payload: dict, signature: CompositionOperatorSignature) -> set[str]:
    document = TacticalQueryDocument.model_validate(payload)
    binder = Binder(
        default_catalog(),
        composition_operator_signatures={(signature.name, signature.version): signature},
        composition_operator_registry={},
    )
    try:
        binder.bind(
            recipe=document.recipe,
            invocation=document.default_invocation,
            draft_plan=document.draft_plan,
        )
    except BindError as error:
        return bind_error_codes(error)
    raise AssertionError("expected operator bind failure")


class R10OperatorScaffoldingTests(unittest.TestCase):
    def test_operator_registry_is_explicit_and_complete(self) -> None:
        self.assertEqual(("project_onto_axis",), tuple(signature.name for signature in OPERATOR_SIGNATURES))
        self.assertEqual({("project_onto_axis", "0.1.0")}, set(declared_operator_signatures()))
        self.assertEqual({("project_onto_axis", "0.1.0")}, set(build_operator_registry({})))
        self.assertEqual([], registry_completeness_findings())
        self.assertEqual({("project_onto_axis", "0.1.0")}, set(executor_module.TacticalQueryExecutor().operators))

    def test_r1_operator_names_do_not_leak_into_shared_runtime_code(self) -> None:
        for module in (binder_module, executor_module):
            source = Path(module.__file__).resolve().read_text(encoding="utf-8")
            for name in R1_OPERATOR_NAMES:
                pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")
                self.assertIsNone(pattern.search(source), f"{name} leaked into {module.__name__}")

    def test_existing_plan_hashes_are_unchanged_by_operator_scaffolding(self) -> None:
        bound = bind_document(TacticalQueryDocument.model_validate(load_payload()))

        self.assertEqual("6ffa2ed7df43e999183f1b9135f0d64382dd01b00f044394a67ebccdd6c647c9", bound.plan_hash)
        self.assertEqual("4a5a1dabc168ffcc511923700ddb28af67393fb13c7caccd7b92689289d8b4ce", bound.bound_plan_hash)

    def test_operator_node_rejects_with_empty_registry(self) -> None:
        payload = add_operator_node(
            load_payload(),
            {
                "kind": "operator",
                "node_id": "future_operator",
                "operator": {"name": "future_operator", "version": "0.1.0"},
                "inputs": {},
                "outputs": [operator_output()],
            },
        )

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn("operator_not_implemented", bind_error_codes(raised.exception))

    def test_operator_signature_validation_reports_missing_input_and_unknown_parameter(self) -> None:
        signature = sample_signature()
        payload = add_operator_node(
            load_payload(),
            {
                "kind": "operator",
                "node_id": "future_operator",
                "operator": {"name": signature.name, "version": signature.version},
                "inputs": {},
                "parameters": {
                    "extra_parameter": {"payload_type": "number", "unit": "count", "value": 1}
                },
                "outputs": [operator_output()],
            },
        )

        codes = bind_with_signature(payload, signature)

        self.assertIn("missing_operator_input", codes)
        self.assertIn("unknown_operator_parameter", codes)
        self.assertIn("operator_not_implemented", codes)

    def test_operator_signature_validation_reports_channel_mismatch(self) -> None:
        signature = sample_signature()
        payload = add_operator_node(
            load_payload(),
            {
                "kind": "operator",
                "node_id": "future_operator",
                "operator": {"name": signature.name, "version": signature.version},
                "inputs": {
                    "source": {"source_node_id": "possession", "output_name": "anchors"}
                },
                "outputs": [operator_output()],
            },
        )

        codes = bind_with_signature(payload, signature)

        self.assertIn("operator_input_payload_mismatch", codes)
        self.assertIn("operator_input_entity_scope_mismatch", codes)
        self.assertIn("operator_not_implemented", codes)


if __name__ == "__main__":
    unittest.main()
