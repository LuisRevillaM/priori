#!/usr/bin/env python3
"""Project compiler-search target contracts from registry/passport declarations.

This is a contract-generation readiness step, not an atlas-scale reachability
measurement. It projects typed target contracts from the generated semantic
registry passport projection, then refuses contracts that carry synthesis-path
hints such as pattern labels, catalog refs, runtime refs, or gold-chain text.
"""

from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tqe.runtime.catalog import default_catalog  # noqa: E402
from tqe.runtime.ir import CatalogEntry, stable_hash  # noqa: E402


PASSPORTS = ROOT / "generated" / "semantic-registry" / "capability-passport-projection.json"
OUT_DIR = ROOT / "generated" / "compiler-search-contracts"
TARGETS_OUT = OUT_DIR / "registry-projected-targets.v0.json"
LEDGER_OUT = OUT_DIR / "registry-projected-coverage-ledger.json"
REPORT_OUT = ROOT / "artifacts" / "autonomous" / "compiler-contract-projection-report.json"

SCHEMA_VERSION = "compiler_search_contract_projection.v0"
TARGET_SCHEMA_VERSION = "compiler_search_targets.v0"
CONTRACT_SOURCE = "semantic_registry_passport_projection"
MEASUREMENT_STATUS = "CONTRACT_PROJECTION_READY_NOT_ATLAS_SCALE"
SUPPORTED_MODALITIES = {"tracking", "events", "tracking_event_synchronized"}
EXCLUDED_CATALOG_REFS = {
    "controlled_line_break_episode",
    "relation_destination_entry_classification",
    "outcome_classification",
}
FORBIDDEN_CONTRACT_KEYS = {
    "catalog_ref",
    "catalog_refs",
    "closest_supported_substitute",
    "composition_pattern",
    "gold_chain",
    "gold_chain_path",
    "pattern",
    "provider_chain",
    "runtime_capability",
    "runtime_capability_ref",
    "runtime_ref",
    "runtime_refs",
    "source_runtime_capability",
}


def main() -> int:
    passport_payload = load_json(PASSPORTS)
    catalog_entries = {
        entry.name: entry
        for entry in [*default_catalog().primitives, *default_catalog().relations]
        if entry.name not in EXCLUDED_CATALOG_REFS
    }

    targets: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    skips: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for passport in passport_payload["passports"]:
        projection = project_passport(passport, catalog_entries)
        if projection.get("skip_reason"):
            skips.append(projection)
            continue
        target = projection["target"]
        target_findings = contract_findings(target)
        if target_findings:
            findings.extend(target_findings)
            skips.append(
                {
                    "passport_id": projection["passport_id"],
                    "runtime_capability": projection["runtime_capability"],
                    "skip_reason": "contract_anti_circularity_failed",
                    "findings": target_findings,
                }
            )
            continue
        targets.append(target)
        ledger_rows.append(projection["ledger_row"])

    targets_payload = {
        "schema_version": TARGET_SCHEMA_VERSION,
        "strategy": "bounded_backward_search.v0.1.registry_projected_contracts",
        "sample_policy": "registry_passport_projection_subset",
        "note": (
            "Targets are projected from semantic registry passport claim/evidence contracts. "
            "They are not atlas-wide, do not use coverage-map gold chains, and are suitable "
            "for a registry-backed readiness search only."
        ),
        "projection_source": {
            "source": CONTRACT_SOURCE,
            "path": relative_path(PASSPORTS),
            "passport_revision": passport_payload.get("passport_revision"),
            "passport_count": passport_payload.get("passport_count"),
        },
        "targets": targets,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TARGETS_OUT.write_text(json.dumps(targets_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LEDGER_OUT.write_text(json.dumps(ledger_rows, indent=1) + "\n", encoding="utf-8")

    skip_counts = collections.Counter(item["skip_reason"] for item in skips)
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if targets and not findings else "FAIL",
        "measurement_status": MEASUREMENT_STATUS,
        "scope": {
            "atlas_wide": False,
            "natural_language": False,
            "source": CONTRACT_SOURCE,
            "source_path": relative_path(PASSPORTS),
            "coverage_map_gold_chain_used": False,
            "pattern_labels_used": False,
            "runtime_or_catalog_refs_used_inside_target_contract": False,
        },
        "summary": {
            "passport_count": len(passport_payload["passports"]),
            "projected_target_count": len(targets),
            "skipped_count": len(skips),
            "skip_counts": dict(sorted(skip_counts.items())),
            "target_contract_hashes": {
                target["target_id"]: stable_hash(target["target_contract"]) for target in targets
            },
        },
        "anti_circularity": {
            "forbidden_contract_keys": sorted(FORBIDDEN_CONTRACT_KEYS),
            "findings": findings,
        },
        "outputs": {
            "targets_path": relative_path(TARGETS_OUT),
            "ledger_path": relative_path(LEDGER_OUT),
        },
        "skips": skips,
        "next_step": (
            "Run the search runner against the projected target/ledger pair with "
            "TQE_SEARCH_UPDATE_LEDGER=0. Treat the result as registry-subset readiness, "
            "not as a 741-row compiler reachability percentage."
        ),
    }
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


def project_passport(passport: dict[str, Any], catalog_entries: dict[str, CatalogEntry]) -> dict[str, Any]:
    runtime_id = runtime_id_from_binding(passport.get("binding", {}))
    passport_id = str(passport.get("binding", {}).get("id") or passport.get("display_name") or runtime_id)
    if passport.get("exposure_policy", {}).get("ai_compiler") != "ALLOWED":
        return skip(passport_id, runtime_id, "not_ai_compiler_allowed")
    if runtime_id not in catalog_entries:
        return skip(passport_id, runtime_id, "runtime_entry_not_in_search_catalog")

    entry = catalog_entries[runtime_id]
    available_fields = field_set(entry)
    evidence_contracts = passport.get("evidence_contracts") or []
    if not evidence_contracts:
        return skip(passport_id, runtime_id, "missing_evidence_contract")
    required_evidence = sorted({field for contract in evidence_contracts for field in contract.get("required", [])})
    missing_required = sorted(field for field in required_evidence if field not in available_fields)
    if missing_required:
        return skip(
            passport_id,
            runtime_id,
            "required_evidence_not_declared_in_runtime_catalog",
            {"missing_required_evidence": missing_required},
        )

    status_field = primary_status_field(entry, required_evidence)
    if status_field is None:
        return skip(passport_id, runtime_id, "no_status_predicate_available")
    if not status_field_allows_pass(entry, status_field):
        return skip(
            passport_id,
            runtime_id,
            "status_predicate_requires_declared_value",
            {
                "status_field": status_field,
                "allowed_values": output_allowed_values(entry, status_field),
            },
        )

    modalities = sorted(
        {
            normalize_modality(modality)
            for operationalization in passport.get("operationalizations", [])
            for modality in operationalization.get("required_modalities", [])
        }
    )
    unsupported_modalities = [modality for modality in modalities if modality not in SUPPORTED_MODALITIES]
    if unsupported_modalities:
        return skip(
            passport_id,
            runtime_id,
            "unsupported_registry_modality",
            {"unsupported_modalities": unsupported_modalities},
        )

    concept_id = first_concept_id(passport, runtime_id)
    target_id = sanitize_id(f"registry_projected_{runtime_id}")
    claim_boundary = claim_boundary_from_passport(passport)
    contract = {
        "desired_output": "classification",
        "required_modalities": modalities,
        "required_evidence": required_evidence,
        "status_semantics": [{"field": status_field, "required_value": "PASS"}],
        "claim_boundary": claim_boundary,
    }
    target = {
        "target_id": target_id,
        "concept": concept_id,
        "held_out": False,
        "registry_projected": True,
        "projection_source": {
            "source": CONTRACT_SOURCE,
            "passport_id": passport_id,
            "concept_refs": [concept.get("id") for concept in passport.get("concepts", [])],
            "operationalization_refs": [op.get("id") for op in passport.get("operationalizations", [])],
            "claim_contract_refs": [claim.get("contract_ref") for claim in passport.get("claim_contracts", [])],
            "evidence_contract_refs": [evidence.get("contract_ref") for evidence in evidence_contracts],
        },
        "target_contract": contract,
    }
    ledger_row = {
        "concept": concept_id,
        "family": "registry_projected_runtime_capability",
        "classification": "supported",
        "justification": (
            "Registry-projected target contract derived from claim/evidence contracts; "
            "not an atlas-scale coverage row."
        ),
        "required_missing_capability": "",
        "closest_supported_substitute": "",
        "composition_constraint_needed": False,
        "priority_unlock": "INTERNAL",
        "composition_constraint_note": "",
        "composition_maturity": "handwired",
        "composition_maturity_applicable": True,
    }
    return {
        "passport_id": passport_id,
        "runtime_capability": runtime_id,
        "target": target,
        "ledger_row": ledger_row,
    }


def field_set(entry: CatalogEntry) -> set[str]:
    fields = set(entry.evidence_fields)
    for output in entry.outputs:
        fields.add(output.name)
        fields.update(output.evidence_fields)
    return fields


def primary_status_field(entry: CatalogEntry, required_evidence: list[str]) -> str | None:
    required = set(required_evidence)
    for output in entry.outputs:
        if output.name.endswith("_status") and output.name in required:
            return output.name
    for field in required_evidence:
        if field.endswith("_status"):
            return field
    for output in entry.outputs:
        if output.name.endswith("_status"):
            return output.name
    return None


def status_field_allows_pass(entry: CatalogEntry, status_field: str) -> bool:
    allowed = output_allowed_values(entry, status_field)
    return not allowed or "PASS" in allowed


def output_allowed_values(entry: CatalogEntry, field_name: str) -> list[str]:
    for output in entry.outputs:
        if output.name == field_name:
            return [str(value) for value in (output.allowed_values or [])]
    return []


def claim_boundary_from_passport(passport: dict[str, Any]) -> str:
    permitted = sorted({item for contract in passport.get("claim_contracts", []) for item in contract.get("permitted", [])})
    prohibited = sorted({item for contract in passport.get("claim_contracts", []) for item in contract.get("prohibited", [])})
    permitted_text = ", ".join(permitted) if permitted else "registry-declared observed claim only"
    prohibited_text = ", ".join(prohibited) if prohibited else "no undeclared tactical claims"
    return f"Permitted: {permitted_text}. Prohibited: {prohibited_text}."


def first_concept_id(passport: dict[str, Any], fallback: str) -> str:
    concepts = passport.get("concepts") or []
    if concepts and concepts[0].get("id"):
        return str(concepts[0]["id"])
    return f"runtime.{fallback}"


def normalize_modality(modality: str) -> str:
    value = str(modality)
    aliases = {
        "event": "events",
        "provider_events": "events",
        "tracking_events": "tracking_event_synchronized",
    }
    return aliases.get(value, value)


def runtime_id_from_binding(binding: dict[str, Any]) -> str:
    runtime_capability = binding.get("runtime_capability")
    if isinstance(runtime_capability, dict) and runtime_capability.get("id"):
        return str(runtime_capability["id"])
    binding_id = str(binding.get("id") or "")
    match = re.match(r"^binding\.(?:primitive|relation)\.(?P<name>.+)\.[0-9]+_[0-9]+_[0-9]+$", binding_id)
    if match:
        return match.group("name")
    return binding_id


def contract_findings(target: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    contract = target["target_contract"]
    forbidden_paths = forbidden_key_paths(contract)
    if forbidden_paths:
        findings.append(
            {
                "code": "forbidden_contract_hint_key",
                "target_id": target["target_id"],
                "paths": forbidden_paths,
            }
        )
    concept = str(target["concept"]).lower()
    contract_text = json.dumps(contract, sort_keys=True).lower()
    if concept and concept in contract_text:
        findings.append(
            {
                "code": "concept_id_used_as_contract_hint",
                "target_id": target["target_id"],
                "concept": target["concept"],
            }
        )
    return findings


def forbidden_key_paths(value: Any, *, path: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key) in FORBIDDEN_CONTRACT_KEYS:
                paths.append(child_path)
            paths.extend(forbidden_key_paths(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(forbidden_key_paths(child, path=f"{path}[{index}]"))
    return paths


def skip(passport_id: str, runtime_capability: str, reason: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "passport_id": passport_id,
        "runtime_capability": runtime_capability,
        "skip_reason": reason,
    }
    if details:
        payload.update(details)
    return payload


def sanitize_id(value: str) -> str:
    sanitized = re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")
    if not sanitized or not sanitized[0].isalpha():
        sanitized = f"target_{sanitized}"
    return sanitized


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
