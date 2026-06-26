#!/usr/bin/env python3
"""Prepare and assess a bare-atlas compiler-search contract sample.

The registry-projected path proves that existing passports can become typed
search targets. This script handles the riskier next step: prose atlas concepts
that do not yet have registry objects. It keeps the sample small, preserves
author variants, and includes known-negative controls so contract generation can
be checked for both consistency and honesty.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "compiler-reachability" / "bare-atlas-contract-sample.v0.json"
COVERAGE_LEDGER = ROOT / "generated" / "coverage-map.json"
OUT_DIR = ROOT / "generated" / "compiler-search-bare-atlas"
TARGETS_OUT = OUT_DIR / "bare-atlas-targets.v0.json"
LEDGER_OUT = OUT_DIR / "bare-atlas-coverage-ledger.json"
SEARCH_ROW_LEDGER = OUT_DIR / "search-run" / "row-ledger.json"
PREP_REPORT = ROOT / "artifacts" / "autonomous" / "compiler-bare-atlas-contract-prep-report.json"
ASSESS_REPORT = ROOT / "artifacts" / "autonomous" / "compiler-bare-atlas-contract-sample-report.json"

SUPPORTED_MODALITIES = {"tracking", "events", "tracking_event_synchronized"}
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "assess"])
    args = parser.parse_args()
    return prepare() if args.mode == "prepare" else assess()


def prepare() -> int:
    config = load_json(CONFIG)
    coverage_rows = load_json(COVERAGE_LEDGER)
    coverage_by_concept = {row["concept"]: row for row in coverage_rows}
    targets: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for concept_config in config["concepts"]:
        concept = concept_config["concept"]
        coverage_row = coverage_by_concept.get(concept)
        if coverage_row is None:
            findings.append(
                {
                    "code": "concept_not_in_coverage_map",
                    "concept": concept,
                    "path": f"config.concepts[{concept}]",
                }
            )
            coverage_row = synthetic_coverage_row(concept_config)
        ledger_rows.append(ledger_row_for_sample(concept_config, coverage_row))
        variants = concept_config.get("variants") or []
        if len(variants) < 2:
            findings.append(
                {
                    "code": "insufficient_author_variants",
                    "concept": concept,
                    "message": "Every sampled concept must carry at least two independently-authored variants.",
                }
            )
        for variant in variants:
            target = target_from_variant(concept_config, variant)
            findings.extend(contract_findings(target))
            targets.append(target)

    targets_payload = {
        "schema_version": "compiler_search_targets.v0",
        "strategy": "bounded_backward_search.v0.1.bare_atlas_contract_sample",
        "sample_policy": config["sample_policy"],
        "note": config["note"],
        "targets": targets,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TARGETS_OUT.write_text(json.dumps(targets_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LEDGER_OUT.write_text(json.dumps(ledger_rows, indent=1) + "\n", encoding="utf-8")

    role_counts = collections.Counter(concept["sample_role"] for concept in config["concepts"])
    report = {
        "schema_version": "bare_atlas_contract_sample_prepare.v0",
        "status": "PASS" if not findings else "FAIL",
        "scope": {
            "atlas_wide": False,
            "natural_language": False,
            "coverage_map_gold_chain_used": False,
            "pattern_labels_used": False,
            "runtime_or_catalog_refs_used_inside_target_contract": False,
            "known_negative_controls_required": True,
            "independent_author_variants_required": True,
        },
        "summary": {
            "concept_count": len(config["concepts"]),
            "target_count": len(targets),
            "role_counts": dict(sorted(role_counts.items())),
            "author_variant_count": sum(len(concept.get("variants") or []) for concept in config["concepts"]),
        },
        "anti_circularity": {
            "forbidden_contract_keys": sorted(FORBIDDEN_CONTRACT_KEYS),
            "findings": findings,
        },
        "outputs": {
            "targets_path": relative_path(TARGETS_OUT),
            "ledger_path": relative_path(LEDGER_OUT),
        },
    }
    PREP_REPORT.parent.mkdir(parents=True, exist_ok=True)
    PREP_REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


def assess() -> int:
    config = load_json(CONFIG)
    rows = load_json(SEARCH_ROW_LEDGER)
    rows_by_target = {row["target_id"]: row for row in rows}
    findings: list[dict[str, Any]] = []
    concept_reports: list[dict[str, Any]] = []

    for concept_config in config["concepts"]:
        concept = concept_config["concept"]
        variants = []
        for variant in concept_config.get("variants") or []:
            target_id = target_id_for(concept, variant["author_id"])
            row = rows_by_target.get(target_id)
            if row is None:
                findings.append(
                    {
                        "code": "missing_search_row",
                        "concept": concept,
                        "target_id": target_id,
                    }
                )
                continue
            variants.append(
                {
                    "author_id": variant["author_id"],
                    "target_id": target_id,
                    "result": row["result"],
                    "failure_taxonomy": row.get("failure_taxonomy"),
                    "result_count": row.get("result_count"),
                    "honest_zero": row.get("honest_zero"),
                    "document_hash": row.get("document_hash"),
                }
            )
        concept_findings = assess_concept(concept_config, variants)
        findings.extend(concept_findings)
        concept_reports.append(
            {
                "concept": concept,
                "sample_role": concept_config["sample_role"],
                "expected_result": concept_config.get("expected_result"),
                "expected_failure_taxonomy": concept_config.get("expected_failure_taxonomy"),
                "variants": variants,
                "findings": concept_findings,
            }
        )

    result_counts = collections.Counter(row["result"] for row in rows)
    failure_counts = collections.Counter(row["failure_taxonomy"] for row in rows if row.get("failure_taxonomy"))
    known_negative_targets = [
        variant
        for concept in concept_reports
        if concept["sample_role"] == "known_negative"
        for variant in concept["variants"]
    ]
    positive_targets = [
        variant
        for concept in concept_reports
        if concept["sample_role"] == "positive_probe"
        for variant in concept["variants"]
    ]
    report = {
        "schema_version": "bare_atlas_contract_sample_assessment.v0",
        "status": "PASS" if not findings else "FAIL",
        "scope": {
            "atlas_wide": False,
            "natural_language": False,
            "sample_policy": config["sample_policy"],
            "claim": (
                "Small bare-atlas contract sample with author-variant consistency "
                "and known-negative honesty controls; not a compiler-reachable percentage for the 741 atlas."
            ),
        },
        "summary": {
            "concept_count": len(concept_reports),
            "target_count": len(rows),
            "positive_target_count": len(positive_targets),
            "positive_compiler_reachable_count": sum(1 for item in positive_targets if item["result"] == "compiler_reachable"),
            "known_negative_target_count": len(known_negative_targets),
            "known_negative_honest_failure_count": sum(1 for item in known_negative_targets if item["result"] != "compiler_reachable"),
            "result_distribution": dict(sorted(result_counts.items())),
            "failure_distribution": dict(sorted(failure_counts.items())),
        },
        "concepts": concept_reports,
        "findings": findings,
        "inputs": {
            "config_path": relative_path(CONFIG),
            "search_row_ledger": relative_path(SEARCH_ROW_LEDGER),
        },
    }
    ASSESS_REPORT.parent.mkdir(parents=True, exist_ok=True)
    ASSESS_REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


def assess_concept(concept_config: dict[str, Any], variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    concept = concept_config["concept"]
    verdicts = {(variant["result"], variant["failure_taxonomy"]) for variant in variants}
    if len(verdicts) > 1:
        findings.append(
            {
                "code": "author_variant_verdict_diverged",
                "concept": concept,
                "verdicts": sorted([list(verdict) for verdict in verdicts]),
            }
        )
    if concept_config["sample_role"] == "positive_probe":
        expected = concept_config.get("expected_result")
        if expected:
            for variant in variants:
                if variant["result"] != expected:
                    findings.append(
                        {
                            "code": "positive_probe_unexpected_result",
                            "concept": concept,
                            "target_id": variant["target_id"],
                            "expected": expected,
                            "actual": variant["result"],
                            "failure_taxonomy": variant["failure_taxonomy"],
                        }
                    )
    if concept_config["sample_role"] == "known_negative":
        expected_failure = concept_config.get("expected_failure_taxonomy")
        for variant in variants:
            if variant["result"] == "compiler_reachable":
                findings.append(
                    {
                        "code": "known_negative_became_reachable",
                        "concept": concept,
                        "target_id": variant["target_id"],
                    }
                )
            if expected_failure and variant["failure_taxonomy"] != expected_failure:
                findings.append(
                    {
                        "code": "known_negative_wrong_failure",
                        "concept": concept,
                        "target_id": variant["target_id"],
                        "expected": expected_failure,
                        "actual": variant["failure_taxonomy"],
                    }
                )
    return findings


def target_from_variant(concept_config: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    concept = concept_config["concept"]
    target = {
        "target_id": target_id_for(concept, variant["author_id"]),
        "concept": concept,
        "held_out": True,
        "bare_atlas_sample": True,
        "author_variant": variant["author_id"],
        "sample_role": concept_config["sample_role"],
        "target_contract": variant["target_contract"],
    }
    if concept_config.get("multi_step"):
        target["multi_step"] = True
    if concept_config.get("expected_failure_taxonomy"):
        target["expected_failure_taxonomy"] = concept_config["expected_failure_taxonomy"]
    return target


def ledger_row_for_sample(concept_config: dict[str, Any], coverage_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "concept": concept_config["concept"],
        "family": coverage_row.get("family") or concept_config.get("family") or "bare_atlas_sample",
        "classification": coverage_row.get("classification", "supported"),
        "justification": coverage_row.get("justification", "Bare-atlas contract sample row."),
        "required_missing_capability": coverage_row.get("required_missing_capability", ""),
        "closest_supported_substitute": "",
        "composition_constraint_needed": bool(coverage_row.get("composition_constraint_needed", False)),
        "priority_unlock": coverage_row.get("priority_unlock", "INTERNAL"),
        "composition_constraint_note": coverage_row.get("composition_constraint_note", ""),
        "source_composition_maturity": coverage_row.get("composition_maturity", "handwired"),
        "composition_maturity": "handwired",
        "composition_maturity_applicable": coverage_row.get("classification") == "supported",
    }


def synthetic_coverage_row(concept_config: dict[str, Any]) -> dict[str, Any]:
    role = concept_config["sample_role"]
    return {
        "concept": concept_config["concept"],
        "family": concept_config.get("family", "bare_atlas_sample"),
        "classification": "supported" if role == "positive_probe" else "missing_primitive",
        "justification": "Synthetic row for bare-atlas contract sample.",
        "required_missing_capability": "",
        "composition_maturity": "handwired",
        "composition_maturity_applicable": role == "positive_probe",
    }


def contract_findings(target: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    forbidden_paths = forbidden_key_paths(target["target_contract"])
    if forbidden_paths:
        findings.append(
            {
                "code": "forbidden_contract_hint_key",
                "target_id": target["target_id"],
                "paths": forbidden_paths,
            }
        )
    concept = str(target["concept"]).lower()
    contract_text = json.dumps(target["target_contract"], sort_keys=True).lower()
    if concept and concept in contract_text:
        findings.append(
            {
                "code": "concept_id_used_as_contract_hint",
                "target_id": target["target_id"],
                "concept": target["concept"],
            }
        )
    unsupported_modalities = [
        modality
        for modality in target["target_contract"].get("required_modalities", [])
        if modality not in SUPPORTED_MODALITIES
    ]
    if target.get("sample_role") == "known_negative" and target.get("expected_failure_taxonomy") == "unsupported_modality":
        if not unsupported_modalities:
            findings.append(
                {
                    "code": "unsupported_modality_control_has_no_unsupported_modality",
                    "target_id": target["target_id"],
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


def target_id_for(concept: str, author_id: str) -> str:
    return sanitize_id(f"bare_atlas_{concept}_{author_id}_v0")


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
