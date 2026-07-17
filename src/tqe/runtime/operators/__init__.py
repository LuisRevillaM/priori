"""Composition operator registry scaffolding.

R1-0 opens the operator era with an explicit registry and zero registered
operators. Future R1 packets add signatures and implementations here; the
binder already fails closed while this registry is empty.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib import import_module
from typing import Any

from tqe.runtime.ir import CompositionOperatorSignature
from tqe.runtime.field_references import migrate_operator_field_references
from tqe.runtime.operators.aggregate_over import AGGREGATE_OVER_SIGNATURE
from tqe.runtime.operators.delta_across_anchor import DELTA_ACROSS_ANCHOR_SIGNATURE
from tqe.runtime.operators.extremum_over_set import EXTREMUM_OVER_SET_SIGNATURE
from tqe.runtime.operators.project_onto_axis import PROJECT_ONTO_AXIS_SIGNATURE
from tqe.runtime.operators.rate import RATE_SIGNATURE
from tqe.runtime.operators.typed_join import TYPED_JOIN_SIGNATURE
from tqe.runtime.operators.sequence_pattern import SEQUENCE_PATTERN_SIGNATURE
from tqe.runtime.operators.window import WINDOW_SIGNATURE

OperatorImplementation = Callable[..., None]
OperatorKey = tuple[str, str]


OPERATOR_SIGNATURES: tuple[CompositionOperatorSignature, ...] = tuple(
    migrate_operator_field_references(signature)
    for signature in (
        PROJECT_ONTO_AXIS_SIGNATURE,
        DELTA_ACROSS_ANCHOR_SIGNATURE,
        EXTREMUM_OVER_SET_SIGNATURE,
        WINDOW_SIGNATURE,
        TYPED_JOIN_SIGNATURE,
        AGGREGATE_OVER_SIGNATURE,
        RATE_SIGNATURE,
        SEQUENCE_PATTERN_SIGNATURE,
    )
)
_OPERATOR_SIGNATURES_BY_NAME = {signature.name: signature for signature in OPERATOR_SIGNATURES}
OPERATOR_SIGNATURES_BY_CONSTRAINT_KIND: dict[str, CompositionOperatorSignature] = {
    "aggregate_over": _OPERATOR_SIGNATURES_BY_NAME["aggregate_over"],
    "delta_across_anchor": _OPERATOR_SIGNATURES_BY_NAME["delta_across_anchor"],
    "extremum_over_set": _OPERATOR_SIGNATURES_BY_NAME["extremum_over_set"],
    "rate": _OPERATOR_SIGNATURES_BY_NAME["rate"],
    "typed_join": _OPERATOR_SIGNATURES_BY_NAME["typed_join"],
    "vector_projection": _OPERATOR_SIGNATURES_BY_NAME["project_onto_axis"],
    "window": _OPERATOR_SIGNATURES_BY_NAME["window"],
    "sequence_pattern": _OPERATOR_SIGNATURES_BY_NAME["sequence_pattern"],
}
LEGACY_COMPOSITION_CONSTRAINT_KIND_SCHEMAS: dict[str, dict[str, Any]] = {
    "before_after_same_anchor": {
        "operator": None,
        "parameters": [
            "after_status_field",
            "change_mode",
            "maximum_before_value_m",
            "minimum_change_m",
            "status_fields",
            "value_family",
            "value_fields",
        ],
    },
    "distinct_entity_fields": {
        "operator": None,
        "parameters": ["fields"],
    },
    "frame_alignment": {
        "operator": None,
        "parameters": ["after_frame_field", "before_frame_field"],
    },
    "relation_on_anchor": {
        "operator": None,
        "parameters": [
            "anchor_frame_field",
            "anchor_status_field",
            "anchor_status_value",
            "candidate_scope",
            "maximum_arrival_seconds",
            "maximum_support_distance_m",
            "minimum_duration_seconds",
            "minimum_supporting_players",
            "relation_status_field",
            "support_region_mode",
        ],
    },
    "same_anchor_identity": {
        "operator": None,
        "parameters": ["left_key_field", "right_key_field"],
    },
    "same_player_return": {
        "operator": None,
        "parameters": ["first_player_field", "return_player_field"],
    },
    "temporal_order": {
        "operator": None,
        "parameters": ["after_frame_field", "before_frame_field", "maximum_gap_seconds"],
    },
}
OPERATOR_IMPLEMENTATION_NAMES: tuple[tuple[str, str, str], ...] = (
    ("project_onto_axis", "0.1.0", "execute_project_onto_axis"),
    ("delta_across_anchor", "0.1.0", "execute_delta_across_anchor"),
    ("extremum_over_set", "0.1.0", "execute_extremum_over_set"),
    ("window", "0.1.0", "execute_window"),
    ("typed_join", "0.1.0", "execute_typed_join"),
    ("aggregate_over", "0.1.0", "execute_aggregate_over"),
    ("rate", "0.1.0", "execute_rate"),
    ("sequence_pattern", "0.1.0", "execute_sequence_pattern"),
)
OPERATOR_IMPLEMENTATION_MODULES: dict[str, str] = {
    "execute_aggregate_over": "tqe.runtime.operators.aggregate_over",
    "execute_delta_across_anchor": "tqe.runtime.operators.delta_across_anchor",
    "execute_extremum_over_set": "tqe.runtime.operators.extremum_over_set",
    "execute_project_onto_axis": "tqe.runtime.operators.project_onto_axis",
    "execute_rate": "tqe.runtime.operators.rate",
    "execute_typed_join": "tqe.runtime.operators.typed_join",
    "execute_window": "tqe.runtime.operators.window",
    "execute_sequence_pattern": "tqe.runtime.operators.sequence_pattern",
}


def declared_operator_signatures() -> dict[OperatorKey, CompositionOperatorSignature]:
    signatures: dict[OperatorKey, CompositionOperatorSignature] = {}
    for signature in OPERATOR_SIGNATURES:
        key = (signature.name, signature.version)
        if key in signatures:
            raise RuntimeError(f"Duplicate operator signature {signature.name}@{signature.version}")
        signatures[key] = signature
    return signatures


def composition_constraint_kind_schemas() -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {
        key: {"operator": value["operator"], "parameters": list(value["parameters"])}
        for key, value in LEGACY_COMPOSITION_CONSTRAINT_KIND_SCHEMAS.items()
    }
    for kind, signature in OPERATOR_SIGNATURES_BY_CONSTRAINT_KIND.items():
        parameters = {parameter.name for parameter in signature.parameters}
        if kind == "typed_join":
            parameters.update(
                {
                    "left_composition_constraints",
                    "left_input_context",
                    "left_required_fields",
                    "right_composition_constraints",
                    "right_input_context",
                    "right_required_fields",
                }
            )
        if kind == "aggregate_over":
            parameters.update(
                {
                    "population_composition_constraints",
                    "population_required_fields",
                }
            )
        if kind == "rate":
            parameters.update(
                {
                    "denominator_composition_constraints",
                    "denominator_required_fields",
                    "numerator_composition_constraints",
                    "numerator_required_fields",
                }
            )
        if kind == "sequence_pattern":
            parameters.update(
                {
                    "stage_1_required_fields",
                    "stage_2_required_fields",
                    "stage_3_required_fields",
                }
            )
        schemas[kind] = {
            "operator": signature.name,
            "operator_version": signature.version,
            "parameters": sorted(parameters),
        }
    return dict(sorted(schemas.items()))


SUPPORTED_COMPOSITION_CONSTRAINT_KINDS: frozenset[str] = frozenset(
    composition_constraint_kind_schemas()
)


def declared_composition_grammar() -> dict[str, Any]:
    return {
        "operator_count": len(OPERATOR_SIGNATURES),
        "operators": [
            signature.model_dump(mode="json", exclude_none=True)
            for signature in OPERATOR_SIGNATURES
        ],
        "constraint_kinds": [
            {"kind": kind, **schema}
            for kind, schema in composition_constraint_kind_schemas().items()
        ],
    }


def build_operator_registry(namespace: Mapping[str, Any]) -> dict[OperatorKey, OperatorImplementation]:
    registry: dict[OperatorKey, OperatorImplementation] = {}
    for name, version, implementation_name in OPERATOR_IMPLEMENTATION_NAMES:
        key = (name, version)
        implementation = _implementation_callable(implementation_name, namespace)
        if not callable(implementation):
            raise RuntimeError(f"Missing operator implementation callable {implementation_name}")
        if key in registry:
            raise RuntimeError(f"Duplicate operator registration for {name}@{version}")
        registry[key] = implementation
    return registry


def registry_completeness_findings(
    signatures: Mapping[OperatorKey, CompositionOperatorSignature] | None = None,
    implementations: Mapping[OperatorKey, OperatorImplementation] | None = None,
) -> list[str]:
    signature_keys = set((signatures or declared_operator_signatures()).keys())
    implementation_keys = set((implementations or build_operator_registry({})).keys())
    findings: list[str] = []
    for key in sorted(signature_keys - implementation_keys):
        findings.append(f"signature_without_implementation:{key[0]}@{key[1]}")
    for key in sorted(implementation_keys - signature_keys):
        findings.append(f"implementation_without_signature:{key[0]}@{key[1]}")
    return findings


def _implementation_callable(implementation_name: str, namespace: Mapping[str, Any]) -> Any:
    module_name = OPERATOR_IMPLEMENTATION_MODULES.get(implementation_name)
    if module_name is None:
        return namespace.get(implementation_name)
    return getattr(import_module(module_name), implementation_name)
