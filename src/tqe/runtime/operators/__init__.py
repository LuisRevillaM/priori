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
from tqe.runtime.operators.project_onto_axis import PROJECT_ONTO_AXIS_SIGNATURE

OperatorImplementation = Callable[..., None]
OperatorKey = tuple[str, str]


OPERATOR_SIGNATURES: tuple[CompositionOperatorSignature, ...] = (PROJECT_ONTO_AXIS_SIGNATURE,)
OPERATOR_IMPLEMENTATION_NAMES: tuple[tuple[str, str, str], ...] = (
    ("project_onto_axis", "0.1.0", "execute_project_onto_axis"),
)
OPERATOR_IMPLEMENTATION_MODULES: dict[str, str] = {
    "execute_project_onto_axis": "tqe.runtime.operators.project_onto_axis",
}


def declared_operator_signatures() -> dict[OperatorKey, CompositionOperatorSignature]:
    signatures: dict[OperatorKey, CompositionOperatorSignature] = {}
    for signature in OPERATOR_SIGNATURES:
        key = (signature.name, signature.version)
        if key in signatures:
            raise RuntimeError(f"Duplicate operator signature {signature.name}@{signature.version}")
        signatures[key] = signature
    return signatures


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
