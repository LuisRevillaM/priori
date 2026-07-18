from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from tqe.runtime.binder import BindError, bind_document
from tqe.runtime.catalog import default_catalog
from tqe.runtime.ir import (
    FieldReferenceKind,
    PayloadType,
    TacticalQueryDocument,
    TypedValue,
    Unit,
    field_reference_name,
)
from tqe.runtime.operators import declared_operator_signatures


ROOT = Path(__file__).resolve().parents[1]
LEGACY_PLAN = ROOT / "config" / "query-plans" / "q5_own_half_regain_settled.experimental.v1.json"
LEGACY_PLAN_HASH = "618ce9961bc04d6d4fefb2e1d58f4a8ed24ae2bac0435c751cc141675f928d30"
LEGACY_BOUND_PLAN_HASH = "7ff420d83a54a821f2ca117dbb7b0d348a95590e1062f0cb0be611773375b3c2"


def typed_field(kind: str, field: str | None) -> dict[str, object]:
    return {
        "payload_type": "field_ref",
        "unit": "none",
        "value": {"kind": kind, "field": field},
    }


def q5_payload(*, kind: str = "frame", field: str = "controller_frame_id") -> dict[str, object]:
    payload = json.loads(LEGACY_PLAN.read_text(encoding="utf-8"))
    payload["draft_plan"]["nodes"][1]["parameters"]["frame_field"] = typed_field(kind, field)
    return payload


def catalog_with_transition_field(field: str):
    catalog = default_catalog()
    primitives = []
    for entry in catalog.primitives:
        if entry.name != "transition_anchor":
            primitives.append(entry)
            continue
        outputs = []
        for output in entry.outputs:
            if output.name != "anchor_evaluations":
                outputs.append(output)
                continue
            outputs.append(
                output.model_copy(
                    update={"evidence_fields": [*output.evidence_fields, field]}
                )
            )
        primitives.append(entry.model_copy(update={"outputs": outputs}))
    return catalog.model_copy(update={"primitives": primitives})


class TypedFieldReferenceLawTests(unittest.TestCase):
    def test_model_accepts_exactly_the_five_ratified_kinds(self) -> None:
        for kind in FieldReferenceKind:
            value = TypedValue(
                payload_type=PayloadType.FIELD_REF,
                value={"kind": kind.value, "field": f"{kind.value}_evidence"},
            )
            self.assertEqual(f"{kind.value}_evidence", field_reference_name(value))

        absent = TypedValue(
            payload_type=PayloadType.FIELD_REF,
            value={"kind": "status", "field": None},
        )
        self.assertEqual("none", field_reference_name(absent))
        with self.assertRaises(ValidationError):
            TypedValue(
                payload_type=PayloadType.FIELD_REF,
                unit=Unit.COUNT,
                value={"kind": "frame", "field": "frame_id"},
            )
        with self.assertRaises(ValidationError):
            TypedValue(
                payload_type=PayloadType.FIELD_REF,
                value={"kind": "numeric", "field": "value"},
            )

    def test_canonical_contract_migrates_all_five_kinds_without_literal_authoring_lists(self) -> None:
        catalog = default_catalog()
        catalog_parameters = [
            parameter
            for entry in [*catalog.primitives, *catalog.relations]
            for parameter in entry.parameters
        ]
        operator_parameters = [
            parameter
            for signature in declared_operator_signatures().values()
            for parameter in signature.parameters
        ]
        migrated = [
            parameter
            for parameter in [*catalog_parameters, *operator_parameters]
            if parameter.payload_type == PayloadType.FIELD_REF
        ]

        # Ratchet census: grows ONLY with an explicit acknowledgment here.
        # 110→118 (2026-07-18): GEO-1 between_observed_lines (+1 frame,
        # +1 entity) and CAR-0a episode identity/attribution (+1 frame,
        # +1 entity, +3 status, +1 provenance).
        self.assertEqual(118, len(migrated))
        self.assertEqual(
            Counter(frame=43, entity=36, status=27, provenance=7, point=5),
            Counter(parameter.field_reference_kind.value for parameter in migrated),
        )
        self.assertTrue(all(parameter.allowed_values is None for parameter in migrated))
        self.assertTrue(all(parameter.allow_legacy_enum for parameter in migrated))

    def test_new_declared_frame_field_binds_without_legacy_enum_expansion(self) -> None:
        catalog = catalog_with_transition_field("controller_frame_id")
        structured_zone = next(
            entry for entry in catalog.primitives if entry.name == "structured_zone"
        )
        frame_parameter = next(
            parameter for parameter in structured_zone.parameters if parameter.name == "frame_field"
        )
        self.assertNotIn("controller_frame_id", frame_parameter.legacy_allowed_values)

        bound = bind_document(
            TacticalQueryDocument.model_validate(q5_payload()),
            catalog=catalog,
        )
        zone = next(node for node in bound.nodes if node.node_id == "own_half_zone")
        resolved = zone.resolved_parameters["frame_field"]
        self.assertEqual(PayloadType.FIELD_REF, resolved.payload_type)
        self.assertEqual("controller_frame_id", field_reference_name(resolved))

    def test_wrong_kind_is_rejected_even_when_field_is_declared(self) -> None:
        catalog = catalog_with_transition_field("controller_frame_id")
        document = TacticalQueryDocument.model_validate(q5_payload(kind="point"))

        with self.assertRaises(BindError) as raised:
            bind_document(document, catalog=catalog)

        self.assertIn(
            "parameter_field_reference_kind_mismatch",
            {issue.code for issue in raised.exception.issues},
        )

    def test_typed_reference_to_undeclared_field_is_rejected(self) -> None:
        document = TacticalQueryDocument.model_validate(q5_payload())

        with self.assertRaises(BindError) as raised:
            bind_document(document)

        self.assertIn(
            "catalog_field_parameter_not_in_input",
            {issue.code for issue in raised.exception.issues},
        )

    def test_legacy_enum_plan_and_bound_hashes_remain_byte_stable(self) -> None:
        document = TacticalQueryDocument.model_validate_json(
            LEGACY_PLAN.read_text(encoding="utf-8")
        )
        bound = bind_document(document)

        self.assertEqual(LEGACY_PLAN_HASH, bound.plan_hash)
        self.assertEqual(LEGACY_BOUND_PLAN_HASH, bound.bound_plan_hash)
        zone = next(node for node in bound.nodes if node.node_id == "own_half_zone")
        resolved = zone.resolved_parameters["frame_field"]
        self.assertEqual(PayloadType.ENUM, resolved.payload_type)
        self.assertEqual("transition_frame_id", resolved.value)


if __name__ == "__main__":
    unittest.main()
