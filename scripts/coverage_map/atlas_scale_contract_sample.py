#!/usr/bin/env python3
"""Prepare and assess a larger atlas compiler-search contract sample.

This is a scale step, not a 741-row population claim. It projects typed target
contracts for a deterministic, stratified subset of the current coverage map,
then assesses the search ledger with honesty controls:

- generated contracts cannot contain synthesis path hints;
- supported-row positives are measured, not assumed reachable;
- known-negative controls must fail with the expected taxonomy;
- author/template variants must agree at the verdict level.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
COVERAGE_LEDGER = ROOT / "generated" / "coverage-map.json"
OUT_DIR = ROOT / os.environ.get("TQE_ATLAS_SCALE_OUT_DIR", "generated/compiler-search-atlas-scale-sample")
TARGETS_OUT = OUT_DIR / os.environ.get("TQE_ATLAS_SCALE_TARGETS_FILENAME", "atlas-scale-targets.v0.json")
LEDGER_OUT = OUT_DIR / os.environ.get("TQE_ATLAS_SCALE_LEDGER_FILENAME", "atlas-scale-coverage-ledger.json")
SEARCH_ROW_LEDGER = OUT_DIR / "search-run" / "row-ledger.json"
PREP_REPORT = ROOT / os.environ.get(
    "TQE_ATLAS_SCALE_PREP_REPORT",
    "artifacts/autonomous/compiler-atlas-scale-contract-prep-report.json",
)
ASSESS_REPORT = ROOT / os.environ.get(
    "TQE_ATLAS_SCALE_ASSESS_REPORT",
    "artifacts/autonomous/compiler-atlas-scale-contract-sample-report.json",
)

MAX_POSITIVE_CONCEPTS = int(os.environ.get("TQE_ATLAS_SCALE_POSITIVE_CONCEPTS", "16"))
MAX_BLIND_CONCEPTS = int(os.environ.get("TQE_ATLAS_SCALE_BLIND_CONCEPTS", str(MAX_POSITIVE_CONCEPTS)))
MAX_NEGATIVE_CONCEPTS = int(os.environ.get("TQE_ATLAS_SCALE_NEGATIVE_CONCEPTS", "8"))
MAX_POSITIVES_PER_TEMPLATE = int(os.environ.get("TQE_ATLAS_SCALE_POSITIVES_PER_TEMPLATE", "3"))
MAX_FRONTIER_CONCEPTS = int(os.environ.get("TQE_ATLAS_SCALE_FRONTIER_CONCEPTS", "48"))
BLIND_SAMPLE_SEED = os.environ.get("TQE_ATLAS_SCALE_BLIND_SAMPLE_SEED", "supported_blind_draw_v0")
SAMPLE_POLICY = os.environ.get("TQE_ATLAS_SCALE_SAMPLE_POLICY", "atlas_scale_stratified_contract_sample_v0")
INCLUDE_KNOWN_GOOD_CONTROLS = os.environ.get("TQE_ATLAS_SCALE_INCLUDE_KNOWN_GOOD_CONTROLS", "0") == "1"
BLIND_SUPPORTED_DRAW = os.environ.get("TQE_ATLAS_SCALE_BLIND_SUPPORTED_DRAW", "0") == "1"
FRONTIER_PARTIAL_DRAW = os.environ.get("TQE_ATLAS_SCALE_FRONTIER_PARTIAL_DRAW", "0") == "1"
MEASURED_SAMPLE_ROLES = {"blind_probe", "frontier_probe", "positive_probe"}

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
EXCLUDED_POSITIVE_FAMILY_PREFIXES = (
    "Temporal logic",
    "Evidence, replay",
    "Data quality",
    "Match clock",
    "Learned probability",
)
CONTRACT_FIDELITY_INSUFFICIENT: dict[str, str] = {
    "bounce_pass_sequence": (
        "Named return/relay combinations need explicit player-linkage semantics; "
        "a generic action anchor or chain would be a weak proxy."
    ),
    "give_and_go_sequence": (
        "Give-and-go requires a two-pass player-return structure; the current "
        "generated contracts cannot faithfully express that identity constraint."
    ),
    "up_back_through_sequence": (
        "Up-back-through requires ordered leg roles and directional constraints "
        "beyond the current generated contract templates."
    ),
    "wall_pass_sequence": (
        "Wall-pass semantics require return-pass/player-linkage constraints that "
        "cannot be represented by a generic action-anchor contract."
    ),
}
KNOWN_GOOD_CONTROL_REASONS: dict[str, str] = {
    "bounce_pass_sequence": "Requires identity-constrained return/relay linkage.",
    "give_and_go_sequence": "Requires same-originating-player return after the relay.",
    "up_back_through_sequence": "Requires ordered up/back/through leg roles plus player/linkage constraints.",
    "wall_pass_sequence": "Requires one-two return-pass identity linkage.",
}
FIDELITY_EXPECTATIONS: dict[str, dict[str, Any]] = {
    "action_anchor": {
        "minimum_unique_provider_count": 1,
        "required_provider_all": ["action_event_anchor"],
        "reason": "Single synchronized action anchor is the intended minimum for this contract.",
    },
    "action_chain": {
        "minimum_unique_provider_count": 2,
        "required_provider_all": ["action_event_anchor", "action_chain"],
        "reason": "A sequence contract must be satisfied by an ordered action chain, not one action anchor.",
    },
    "carry": {
        "minimum_unique_provider_count": 2,
        "required_provider_all": ["controlled_pass_episode", "carry_episode"],
        "reason": "Carry contracts inherit controlled-pass anchoring before carry evaluation.",
    },
    "carry_pressure_change": {
        "minimum_unique_provider_count": 5,
        "required_provider_all": [
            "controlled_pass_episode",
            "carry_episode",
            "pressure_on_carrier",
            "change_across_anchor",
            "join_episode_sets",
        ],
        "required_rule_all": [
            "generic_before_after_change",
            "generic_binary_episode_join",
        ],
        "reason": "Carry-out-of-pressure requires carry, pressure change, and a generic binary episode join.",
    },
    "compactness": {
        "minimum_unique_provider_count": 2,
        "required_provider_all": ["action_event_anchor", "team_compactness"],
        "reason": "Shape contracts need an anchor plus team compactness evaluation.",
    },
    "compactness_change": {
        "minimum_unique_provider_count": 3,
        "required_provider_all": ["controlled_pass_episode", "team_compactness", "change_across_anchor"],
        "required_rule_all": ["generic_before_after_change"],
        "reason": "Shape-change contracts need before/after compactness over a shared anchor.",
    },
    "controlled_pass": {
        "minimum_unique_provider_count": 1,
        "required_provider_all": ["controlled_pass_episode"],
        "reason": "Controlled-pass contracts are satisfied by the controlled pass episode primitive.",
    },
    "distance": {
        "minimum_unique_provider_count": 2,
        "required_provider_all": ["action_event_anchor", "pairwise_distance"],
        "reason": "Distance contracts need an anchor plus pairwise-distance evaluation.",
    },
    "line": {
        "minimum_unique_provider_count": 2,
        "required_provider_any": [["multi_line_model", "defensive_line_model"]],
        "reason": "Line contracts need an observed line model, usually anchored to an event frame.",
    },
    "local_number": {
        "minimum_unique_provider_count": 2,
        "required_provider_all": ["local_number_relation"],
        "required_provider_any": [["action_event_anchor", "controlled_pass_episode", "transition_anchor"]],
        "reason": "Local-number contracts need a legitimate anchor plus local player counts.",
    },
    "pass_chain": {
        "minimum_unique_provider_count": 3,
        "required_provider_all": ["one_touch_relay_episode", "controlled_pass_episode", "pass_chain_episode"],
        "reason": "Pass-chain contracts must exercise the relay and terminal reception chain.",
    },
    "pressure": {
        "minimum_unique_provider_count": 2,
        "required_provider_all": ["controlled_pass_episode", "pressure_on_carrier"],
        "reason": "Pressure contracts need a carrier/reception anchor plus pressure evaluation.",
    },
    "support": {
        "minimum_unique_provider_count": 2,
        "required_provider_all": ["support_arrival_relation"],
        "required_provider_any": [["action_event_anchor", "controlled_pass_episode", "transition_anchor"]],
        "reason": "Support contracts need a legitimate anchor plus support-arrival evaluation.",
    },
    "switch": {
        "minimum_unique_provider_count": 2,
        "required_provider_all": ["switch_of_play"],
        "required_provider_any": [["action_event_anchor", "controlled_pass_episode"]],
        "reason": "Switch contracts need a legitimate action/pass anchor plus switch geometry.",
    },
    "time_to_arrival": {
        "minimum_unique_provider_count": 2,
        "required_provider_all": ["action_event_anchor", "time_to_arrival"],
        "reason": "Arrival contracts need an anchor plus reachability evaluation.",
    },
    "transition": {
        "minimum_unique_provider_count": 1,
        "required_provider_all": ["transition_anchor"],
        "reason": "Transition contracts are satisfied by a genuine possession-change anchor.",
    },
    "transition_outcome": {
        "minimum_unique_provider_count": 2,
        "required_provider_all": ["transition_anchor", "outcome_window"],
        "reason": "Transition-outcome contracts need a transition plus an outcome window.",
    },
    "velocity": {
        "minimum_unique_provider_count": 2,
        "required_provider_all": ["action_event_anchor", "velocity"],
        "reason": "Velocity contracts need an anchor plus displacement-derived velocity.",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "assess"])
    args = parser.parse_args()
    return prepare() if args.mode == "prepare" else assess()


@dataclass(frozen=True)
class ContractTemplate:
    template_id: str
    selectors: tuple[str, ...]
    build: Callable[[str], list[dict[str, Any]]]


def prepare() -> int:
    rows = load_json(COVERAGE_LEDGER)
    if BLIND_SUPPORTED_DRAW:
        measured_configs, skipped_measured_rows = select_blind_supported_rows(rows)
        positive_configs: list[dict[str, Any]] = []
        blind_configs = measured_configs
        frontier_configs: list[dict[str, Any]] = []
    elif FRONTIER_PARTIAL_DRAW:
        measured_configs, skipped_measured_rows = select_frontier_partial_rows(rows)
        positive_configs = []
        blind_configs = []
        frontier_configs = measured_configs
    else:
        positive_configs, skipped_measured_rows = select_positive_rows(rows)
        blind_configs = []
        frontier_configs = []
    negative_configs = select_known_negative_rows(rows)
    control_source_rows = skipped_measured_rows
    if FRONTIER_PARTIAL_DRAW:
        control_source_rows = [*skipped_measured_rows, *divergence_control_refusals(rows)]
    known_good_configs = select_known_good_control_rows(rows, control_source_rows) if INCLUDE_KNOWN_GOOD_CONTROLS else []
    reported_skipped_rows = control_source_rows if FRONTIER_PARTIAL_DRAW else skipped_measured_rows
    concept_configs = [*frontier_configs, *blind_configs, *positive_configs, *negative_configs, *known_good_configs]

    targets: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for concept_config in concept_configs:
        ledger_rows.append(ledger_row_for_sample(concept_config))
        variants = concept_config["variants"]
        required_variant_count = 2 if concept_config["sample_role"] in {"positive_probe", "known_negative"} else 1
        if len(variants) < required_variant_count:
            findings.append(
                {
                    "code": "insufficient_contract_variants",
                    "concept": concept_config["concept"],
                    "message": f"Sample role {concept_config['sample_role']} requires at least {required_variant_count} contract variant(s).",
                }
            )
        for variant in variants:
            target = target_from_variant(concept_config, variant)
            target_findings = contract_findings(target)
            findings.extend(target_findings)
            if not target_findings:
                targets.append(target)

    targets_payload = {
        "schema_version": "compiler_search_targets.v0",
        "strategy": "bounded_backward_search.v0.1.atlas_scale_stratified_contract_sample",
        "sample_policy": SAMPLE_POLICY,
        "note": (
            "Large deterministic atlas sample. Contract variants are generated from "
            "intrinsic evidence/status requirements, not gold chains. Template ids are "
            "audit metadata outside target_contract and are not consumed by synthesis."
        ),
        "targets": targets,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TARGETS_OUT.write_text(json.dumps(targets_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LEDGER_OUT.write_text(json.dumps(ledger_rows, indent=1) + "\n", encoding="utf-8")

    report = {
        "schema_version": "atlas_scale_contract_sample_prepare.v0",
        "status": "PASS" if not findings else "FAIL",
        "scope": {
            "atlas_wide": False,
            "large_stratified_sample": True,
            "blind_supported_draw": BLIND_SUPPORTED_DRAW,
            "frontier_partial_draw": FRONTIER_PARTIAL_DRAW,
            "natural_language": False,
            "coverage_map_gold_chain_used": False,
            "pattern_labels_used": False,
            "runtime_or_catalog_refs_used_inside_target_contract": False,
            "template_variants_not_true_independent_authors": True,
            "known_negative_controls_required": True,
            "known_good_controls_included": INCLUDE_KNOWN_GOOD_CONTROLS,
            "blind_rows_have_expected_result": False,
            "frontier_rows_have_expected_result": False,
        },
        "summary": {
            "frontier_partial_concept_count": len(frontier_configs),
            "blind_supported_concept_count": len(blind_configs),
            "positive_concept_count": len(positive_configs),
            "known_negative_concept_count": len(negative_configs),
            "known_good_control_concept_count": len(known_good_configs),
            "concept_count": len(concept_configs),
            "target_count": len(targets),
            "measured_template_distribution": dict(sorted(collections.Counter(item["contract_template_id"] for item in [*frontier_configs, *blind_configs, *positive_configs]).items())),
            "frontier_gap_distribution": dict(sorted(collections.Counter(item.get("frontier_gap_taxonomy") for item in frontier_configs).items())),
            "negative_distribution": dict(sorted(collections.Counter(item.get("expected_failure_taxonomy") for item in negative_configs).items())),
            "known_good_control_distribution": dict(sorted(collections.Counter(item.get("known_good_control_family") for item in known_good_configs).items())),
            "skipped_measured_row_count": len(reported_skipped_rows),
            "skipped_measured_row_distribution": dict(sorted(collections.Counter(item.get("reason") for item in reported_skipped_rows).items())),
        },
        "selection": {
            "max_positive_concepts": MAX_POSITIVE_CONCEPTS,
            "max_blind_concepts": MAX_BLIND_CONCEPTS,
            "max_frontier_concepts": MAX_FRONTIER_CONCEPTS,
            "max_negative_concepts": MAX_NEGATIVE_CONCEPTS,
            "max_positives_per_template": MAX_POSITIVES_PER_TEMPLATE,
            "blind_sample_seed": BLIND_SAMPLE_SEED,
            "skipped_measured_rows": reported_skipped_rows,
            "skipped_positive_rows": reported_skipped_rows,
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
    targets_payload = load_json(TARGETS_OUT)
    target_by_id = {target["target_id"]: target for target in targets_payload["targets"]}
    rows = load_json(SEARCH_ROW_LEDGER)
    rows_by_target = {row["target_id"]: row for row in rows}
    contract_fidelity_refusals = contract_fidelity_refusals_from_prep_report()
    findings: list[dict[str, Any]] = []
    concept_reports: list[dict[str, Any]] = []

    for concept, targets in group_targets_by_concept(targets_payload["targets"]).items():
        variants = []
        for target in targets:
            row = rows_by_target.get(target["target_id"])
            if row is None:
                findings.append({"code": "missing_search_row", "concept": concept, "target_id": target["target_id"]})
                continue
            variants.append(
                {
                    "variant_id": target["contract_variant"],
                    "target_id": target["target_id"],
                    "sample_role": target["sample_role"],
                    "contract_template_id": target.get("contract_template_id"),
                    "expected_failure_taxonomy": target.get("expected_failure_taxonomy"),
                    "known_good_control_expected_failure": target.get("known_good_control_expected_failure"),
                    "known_good_control_family": target.get("known_good_control_family"),
                    "result": row["result"],
                    "failure_taxonomy": row.get("failure_taxonomy"),
                    "result_count": row.get("result_count"),
                    "honest_zero": row.get("honest_zero"),
                    "terminal_provider": row.get("terminal_provider"),
                    "providers_used": row.get("providers_used", []),
                    "rules_used": row.get("rules_used", []),
                    "fidelity_expectation": target.get("fidelity_expectation"),
                }
            )
        concept_findings = assess_concept(concept, variants)
        findings.extend(concept_findings)
        concept_reports.append(
            {
                "concept": concept,
                "sample_role": targets[0]["sample_role"],
                "contract_template_id": targets[0].get("contract_template_id"),
                "variants": variants,
                "findings": concept_findings,
            }
        )

    result_counts = collections.Counter(row["result"] for row in rows)
    failure_counts = collections.Counter(row["failure_taxonomy"] for row in rows if row.get("failure_taxonomy"))
    measured_rows = [row for row in rows if target_by_id[row["target_id"]]["sample_role"] in MEASURED_SAMPLE_ROLES]
    blind_rows = [row for row in rows if target_by_id[row["target_id"]]["sample_role"] == "blind_probe"]
    frontier_rows = [row for row in rows if target_by_id[row["target_id"]]["sample_role"] == "frontier_probe"]
    positive_rows = [row for row in rows if target_by_id[row["target_id"]]["sample_role"] == "positive_probe"]
    known_negative_rows = [row for row in rows if target_by_id[row["target_id"]]["sample_role"] == "known_negative"]
    known_good_rows = [row for row in rows if target_by_id[row["target_id"]]["sample_role"] == "known_good_control"]
    fidelity_findings = [finding for finding in findings if finding.get("code") == "degenerate_reach_fidelity_violation"]
    measurement = measurement_buckets(
        rows=rows,
        target_by_id=target_by_id,
        fidelity_findings=fidelity_findings,
        contract_fidelity_refusals=contract_fidelity_refusals,
    )
    report = {
        "schema_version": "atlas_scale_contract_sample_assessment.v0",
        "status": "PASS" if not findings else "FAIL",
        "scope": {
            "atlas_wide": False,
            "large_stratified_sample": True,
            "natural_language": False,
            "claim": (
                "Large stratified atlas target-contract sample. In blind mode, measured rows carry "
                "no expected result; seeded known-character rows remain calibration controls. "
                "This is not a 741-row compiler-reachable percentage."
            ),
        },
        "summary": {
            "concept_count": len(concept_reports),
            "target_count": len(rows),
            "measured_target_count": len(measured_rows),
            "measured_compiler_reachable_count": sum(1 for item in measured_rows if item["result"] == "compiler_reachable"),
            "measured_compiler_reachable_pct": pct(sum(1 for item in measured_rows if item["result"] == "compiler_reachable"), len(measured_rows)),
            "blind_target_count": len(blind_rows),
            "blind_compiler_reachable_count": sum(1 for item in blind_rows if item["result"] == "compiler_reachable"),
            "blind_compiler_reachable_pct": pct(sum(1 for item in blind_rows if item["result"] == "compiler_reachable"), len(blind_rows)),
            "blind_failure_distribution": dict(
                sorted(collections.Counter(row.get("failure_taxonomy") for row in blind_rows if row.get("failure_taxonomy")).items())
            ),
            "frontier_target_count": len(frontier_rows),
            "frontier_compiler_reachable_count": sum(1 for item in frontier_rows if item["result"] == "compiler_reachable"),
            "frontier_compiler_reachable_pct": pct(sum(1 for item in frontier_rows if item["result"] == "compiler_reachable"), len(frontier_rows)),
            "frontier_failure_distribution": dict(
                sorted(collections.Counter(row.get("failure_taxonomy") for row in frontier_rows if row.get("failure_taxonomy")).items())
            ),
            "positive_target_count": len(positive_rows),
            "positive_compiler_reachable_count": sum(1 for item in positive_rows if item["result"] == "compiler_reachable"),
            "positive_compiler_reachable_pct": pct(sum(1 for item in positive_rows if item["result"] == "compiler_reachable"), len(positive_rows)),
            "fidelity_checked_reachable_count": sum(1 for item in measured_rows if item["result"] == "compiler_reachable" and target_by_id[item["target_id"]].get("fidelity_expectation")),
            "fidelity_violation_count": len(fidelity_findings),
            "contract_fidelity_refusal_count": len(contract_fidelity_refusals),
            "known_negative_target_count": len(known_negative_rows),
            "known_negative_honest_failure_count": sum(1 for item in known_negative_rows if item["result"] != "compiler_reachable"),
            "known_negative_honest_failure_pct": pct(sum(1 for item in known_negative_rows if item["result"] != "compiler_reachable"), len(known_negative_rows)),
            "known_good_control_target_count": len(known_good_rows),
            "result_distribution": dict(sorted(result_counts.items())),
            "failure_distribution": dict(sorted(failure_counts.items())),
            "measurement_bucket_distribution": measurement["bucket_distribution"],
            "execution_node_cache": execution_node_cache_summary(rows),
        },
        "concepts": concept_reports,
        "contract_fidelity_refusals": contract_fidelity_refusals,
        "measurement_buckets": measurement,
        "findings": findings,
        "inputs": {
            "targets_path": relative_path(TARGETS_OUT),
            "search_row_ledger": relative_path(SEARCH_ROW_LEDGER),
        },
    }
    ASSESS_REPORT.parent.mkdir(parents=True, exist_ok=True)
    ASSESS_REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


def contract_fidelity_refusals_from_prep_report() -> list[dict[str, Any]]:
    if not PREP_REPORT.exists():
        return []
    report = load_json(PREP_REPORT)
    rows = report.get("selection", {}).get("skipped_measured_rows", report.get("selection", {}).get("skipped_positive_rows", []))
    if not isinstance(rows, list):
        return []
    return [
        {
            "concept": str(row.get("concept")),
            "reason": str(row.get("reason")),
            "detail": str(row.get("detail")),
        }
        for row in rows
        if isinstance(row, dict) and row.get("reason") == "contract_fidelity_insufficient"
    ]


def select_known_good_control_rows(rows: list[dict[str, Any]], skipped_positive_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_concept = {row["concept"]: row for row in rows}
    configs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for skipped in skipped_positive_rows:
        concept = skipped.get("concept")
        if skipped.get("reason") != "contract_fidelity_insufficient" or concept not in KNOWN_GOOD_CONTROL_REASONS:
            continue
        if str(concept) in seen:
            continue
        seen.add(str(concept))
        row = by_concept.get(str(concept))
        if row is None:
            continue
        configs.append(
            {
                **row,
                "sample_role": "known_good_control",
                "contract_template_id": "known_good_identity_constrained_combination",
                "known_good_control_family": "identity_constrained_combination",
                "known_good_control_expected_failure": "missing_constraint",
                "variants": known_good_combination_variants(str(concept)),
            }
        )
    return configs


def divergence_control_refusals(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_concept = {str(row["concept"]): row for row in rows}
    refusals: list[dict[str, Any]] = []
    for concept, detail in CONTRACT_FIDELITY_INSUFFICIENT.items():
        if concept not in by_concept:
            continue
        refusals.append(
            {
                "reason": "contract_fidelity_insufficient",
                "concept": concept,
                "detail": detail,
                "selected_by_frontier_divergence_controls": True,
            }
        )
    return refusals


def select_blind_supported_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row in rows:
        if row.get("classification") != "supported":
            continue
        if is_excluded_positive_family(row):
            continue
        concept = str(row["concept"])
        if concept in CONTRACT_FIDELITY_INSUFFICIENT:
            candidates.append(
                {
                    "selection_kind": "contract_fidelity_insufficient",
                    "template_id": "known_good_identity_constrained_combination",
                    "row": row,
                }
            )
            continue
        template = template_for_row(row)
        if template is None:
            continue
        variants = template.build(concept)
        if any(contract_has_concept_hint(concept, variant["target_contract"]) for variant in variants):
            candidates.append(
                {
                    "selection_kind": "concept_hint_risk",
                    "template_id": template.template_id,
                    "row": row,
                }
            )
            continue
        candidates.append(
            {
                "selection_kind": "target_contract",
                "template_id": template.template_id,
                "row": row,
                "variants": variants,
            }
        )

    selected_descriptors = stratified_blind_selection(candidates)
    selected: list[dict[str, Any]] = []
    for descriptor in selected_descriptors:
        row = descriptor["row"]
        concept = str(row["concept"])
        if descriptor["selection_kind"] == "contract_fidelity_insufficient":
            skipped.append(
                {
                    "reason": "contract_fidelity_insufficient",
                    "concept": concept,
                    "detail": CONTRACT_FIDELITY_INSUFFICIENT[concept],
                    "selected_by_blind_draw": True,
                }
            )
            continue
        if descriptor["selection_kind"] == "concept_hint_risk":
            skipped.append(
                {
                    "reason": "concept_hint_risk",
                    "concept": concept,
                    "contract_template_id": descriptor["template_id"],
                    "selected_by_blind_draw": True,
                }
            )
            continue
        selected.append(
            {
                **row,
                "sample_role": "blind_probe",
                "contract_template_id": descriptor["template_id"],
                "variants": descriptor["variants"],
                "blind_sample_seed": BLIND_SAMPLE_SEED,
            }
        )
    return selected, skipped


def select_frontier_partial_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = [
        row
        for row in rows
        if row.get("classification") == "partial_with_typed_gap"
    ]
    candidates.sort(key=lambda row: stable_sample_key(str(row["concept"]), "frontier_partial"))
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row in candidates:
        if len(selected) >= MAX_FRONTIER_CONCEPTS:
            break
        concept = str(row["concept"])
        variants = frontier_partial_variants(row)
        if any(contract_has_concept_hint(concept, variant["target_contract"]) for variant in variants):
            skipped.append(
                {
                    "reason": "concept_hint_risk",
                    "concept": concept,
                    "selected_by_frontier_draw": True,
                }
            )
            continue
        selected.append(
            {
                **row,
                "sample_role": "frontier_probe",
                "contract_template_id": "frontier_partial_gap",
                "frontier_gap_taxonomy": frontier_gap_taxonomy(row),
                "variants": variants,
            }
        )
    return selected, skipped


def stratified_blind_selection(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for candidate in candidates:
        buckets[str(candidate["template_id"])].append(candidate)
    for template_id, bucket in buckets.items():
        bucket.sort(key=lambda item: stable_sample_key(str(item["row"]["concept"]), template_id))

    selected: list[dict[str, Any]] = []
    template_ids = sorted(buckets)
    round_index = 0
    while len(selected) < MAX_BLIND_CONCEPTS:
        added = False
        for template_id in template_ids:
            if len(selected) >= MAX_BLIND_CONCEPTS:
                break
            bucket = buckets[template_id]
            if round_index >= len(bucket):
                continue
            selected.append(bucket[round_index])
            added = True
        if not added:
            break
        round_index += 1
    return selected


def stable_sample_key(concept: str, template_id: str) -> str:
    return hashlib.sha256(f"{BLIND_SAMPLE_SEED}:{template_id}:{concept}".encode("utf-8")).hexdigest()


def frontier_gap_taxonomy(row: dict[str, Any]) -> str:
    if bool(row.get("composition_constraint_needed")) or str(row.get("composition_constraint_note") or "").strip():
        return "missing_constraint"
    return "missing_primitive"


def frontier_partial_variants(row: dict[str, Any]) -> list[dict[str, Any]]:
    taxonomy = frontier_gap_taxonomy(row)
    missing = str(row.get("required_missing_capability") or "typed_gap")
    if taxonomy == "missing_constraint":
        contract = {
            "desired_output": "classification",
            "required_evidence": ["frontier_constraint_status"],
            "status_semantics": [{"field": "frontier_constraint_status", "required_value": "PASS"}],
            "composition_constraints": [
                {
                    "kind": "frontier_missing_composition_constraint",
                    "gap_hash": stable_hash_text(missing)[:12],
                }
            ],
            "claim_boundary": (
                "Frontier partial-row probe requiring a declared semantic composition constraint. "
                "This target is expected to expose whether the current search can enforce that constraint; "
                "no tactical quality, intent, causation, or optimality claim."
            ),
        }
    else:
        missing_field = f"frontier_missing_{stable_hash_text(missing)[:12]}_status"
        contract = {
            "desired_output": "classification",
            "required_evidence": [missing_field],
            "status_semantics": [{"field": missing_field, "required_value": "PASS"}],
            "claim_boundary": (
                "Frontier partial-row probe requiring a declared missing operational capability. "
                "This target is expected to expose whether the current catalog has an executable provider; "
                "no substitute, tactical quality, intent, causation, or optimality claim."
            ),
        }
    return [{"variant_id": "frontier_gap", "target_contract": contract}]


def stable_hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def select_positive_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    skipped: list[dict[str, Any]] = []
    for row in rows:
        if row.get("classification") != "supported":
            continue
        if is_excluded_positive_family(row):
            continue
        if row["concept"] in CONTRACT_FIDELITY_INSUFFICIENT:
            skipped.append(
                {
                    "reason": "contract_fidelity_insufficient",
                    "concept": row["concept"],
                    "detail": CONTRACT_FIDELITY_INSUFFICIENT[row["concept"]],
                }
            )
            continue
        template = template_for_row(row)
        if template is None:
            continue
        variants = template.build(row["concept"])
        if any(contract_has_concept_hint(row["concept"], variant["target_contract"]) for variant in variants):
            skipped.append(
                {
                    "reason": "concept_hint_risk",
                    "concept": row["concept"],
                    "contract_template_id": template.template_id,
                }
            )
            continue
        candidates[template.template_id].append(
            {
                **row,
                "sample_role": "positive_probe",
                "contract_template_id": template.template_id,
                "variants": variants,
            }
        )

    selected: list[dict[str, Any]] = []
    template_ids = sorted(candidates)
    round_index = 0
    per_template: collections.Counter[str] = collections.Counter()
    while len(selected) < MAX_POSITIVE_CONCEPTS:
        added = False
        for template_id in template_ids:
            if len(selected) >= MAX_POSITIVE_CONCEPTS:
                break
            if per_template[template_id] >= MAX_POSITIVES_PER_TEMPLATE:
                continue
            bucket = candidates[template_id]
            if round_index >= len(bucket):
                continue
            selected.append(bucket[round_index])
            per_template[template_id] += 1
            added = True
        if not added:
            break
        round_index += 1
    return selected, skipped


def is_excluded_positive_family(row: dict[str, Any]) -> bool:
    family = str(row.get("family") or "")
    return any(family.startswith(prefix) for prefix in EXCLUDED_POSITIVE_FAMILY_PREFIXES)


def select_known_negative_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = [
        ("pass_completion_probability", "unsupported_modality", "learned_model"),
        ("goalkeeper_set_position_proxy", "unsupported_modality", "body_orientation"),
        ("expected_pass_completion", "unsupported_modality", "learned_model"),
        ("shot_expected_goal", "unsupported_modality", "learned_model"),
        ("goal_kick_build_structure", "missing_primitive", "set_piece_structure"),
        ("marking_assignment_candidate", "missing_primitive", "marking"),
        ("cover_shadow_region", "missing_primitive", "cover_shadow"),
        ("defender_bypassed_by_carry", "missing_primitive", "defender_bypassed_by_carry"),
    ]
    by_concept = {row["concept"]: row for row in rows}
    selected = []
    for concept, taxonomy, missing in priority[:MAX_NEGATIVE_CONCEPTS]:
        row = by_concept.get(concept)
        if row is None:
            continue
        selected.append(
            {
                **row,
                "sample_role": "known_negative",
                "contract_template_id": f"known_negative_{taxonomy}",
                "expected_failure_taxonomy": taxonomy,
                "variants": known_negative_variants(concept, taxonomy, missing),
            }
        )
    return selected


def template_for_row(row: dict[str, Any]) -> ContractTemplate | None:
    haystack = " ".join(
        normalize_match_text(str(row.get(key, "")))
        for key in ("concept", "family")
    )
    for template in TEMPLATES:
        if any(selector_matches(haystack, selector) for selector in template.selectors):
            return template
    return None


def normalize_match_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def selector_matches(haystack: str, selector: str) -> bool:
    selector_text = normalize_match_text(selector)
    if not selector_text:
        return False
    return re.search(rf"(^|\s){re.escape(selector_text)}($|\s)", haystack) is not None


def target_from_variant(concept_config: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    target = {
        "target_id": target_id_for(concept_config["concept"], variant["variant_id"]),
        "concept": concept_config["concept"],
        "held_out": True,
        "atlas_scale_sample": True,
        "contract_variant": variant["variant_id"],
        "contract_template_id": concept_config["contract_template_id"],
        "sample_role": concept_config["sample_role"],
        "target_contract": variant["target_contract"],
    }
    expectation = fidelity_expectation_for_template(concept_config["contract_template_id"])
    if expectation:
        target["fidelity_expectation"] = expectation
    if concept_config.get("expected_failure_taxonomy"):
        target["expected_failure_taxonomy"] = concept_config["expected_failure_taxonomy"]
    if concept_config.get("known_good_control_expected_failure"):
        target["known_good_control_expected_failure"] = concept_config["known_good_control_expected_failure"]
    if concept_config.get("known_good_control_family"):
        target["known_good_control_family"] = concept_config["known_good_control_family"]
    if concept_config.get("frontier_gap_taxonomy"):
        target["frontier_gap_taxonomy"] = concept_config["frontier_gap_taxonomy"]
    if concept_config.get("required_missing_capability"):
        target["required_missing_capability"] = concept_config["required_missing_capability"]
    if concept_config["contract_template_id"] in {"action_chain", "carry_pressure_change", "compactness_change", "pass_chain"}:
        target["multi_step"] = True
    return target


def fidelity_expectation_for_template(template_id: str) -> dict[str, Any] | None:
    expectation = FIDELITY_EXPECTATIONS.get(template_id)
    return None if expectation is None else dict(expectation)


def ledger_row_for_sample(concept_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "concept": concept_config["concept"],
        "family": concept_config.get("family", "atlas_scale_sample"),
        "classification": concept_config.get("classification", "supported"),
        "justification": concept_config.get("justification", "Atlas-scale contract sample row."),
        "required_missing_capability": concept_config.get("required_missing_capability", ""),
        "closest_supported_substitute": "",
        "composition_constraint_needed": bool(concept_config.get("composition_constraint_needed", False)),
        "priority_unlock": concept_config.get("priority_unlock", "INTERNAL"),
        "composition_constraint_note": concept_config.get("composition_constraint_note", ""),
        "source_composition_maturity": concept_config.get("composition_maturity", "handwired"),
        "composition_maturity": "handwired",
        "composition_maturity_applicable": concept_config.get("classification") == "supported",
    }


def contract_findings(target: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    forbidden_paths = forbidden_key_paths(target["target_contract"])
    if forbidden_paths:
        findings.append({"code": "forbidden_contract_hint_key", "target_id": target["target_id"], "paths": forbidden_paths})
    if contract_has_concept_hint(target["concept"], target["target_contract"]):
        findings.append({"code": "concept_id_used_as_contract_hint", "target_id": target["target_id"], "concept": target["concept"]})
    unsupported_modalities = [
        modality
        for modality in target["target_contract"].get("required_modalities", [])
        if modality not in SUPPORTED_MODALITIES
    ]
    if target.get("sample_role") == "known_negative" and target.get("expected_failure_taxonomy") == "unsupported_modality" and not unsupported_modalities:
        findings.append({"code": "unsupported_modality_control_has_no_unsupported_modality", "target_id": target["target_id"]})
    return findings


def assess_concept(concept: str, variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    verdicts = {(variant["result"], variant["failure_taxonomy"]) for variant in variants}
    if len(verdicts) > 1:
        findings.append({"code": "contract_variant_verdict_diverged", "concept": concept, "verdicts": sorted([list(item) for item in verdicts])})
    if not variants:
        return findings
    if variants[0]["sample_role"] == "known_negative":
        expected = variants[0].get("expected_failure_taxonomy")
        for variant in variants:
            if variant["result"] == "compiler_reachable":
                findings.append({"code": "known_negative_became_reachable", "concept": concept, "target_id": variant["target_id"]})
            if expected and variant["failure_taxonomy"] != expected:
                findings.append(
                    {
                        "code": "known_negative_wrong_failure",
                        "concept": concept,
                        "target_id": variant["target_id"],
                        "expected": expected,
                        "actual": variant["failure_taxonomy"],
                    }
                )
    elif variants[0]["sample_role"] == "known_good_control":
        expected = variants[0].get("expected_failure_taxonomy") or variants[0].get("known_good_control_expected_failure")
        for variant in variants:
            if expected and variant["result"] != "compiler_reachable" and variant["failure_taxonomy"] != expected:
                findings.append(
                    {
                        "code": "known_good_control_wrong_failure",
                        "concept": concept,
                        "target_id": variant["target_id"],
                        "expected": expected,
                        "actual": variant["failure_taxonomy"],
                    }
                )
    else:
        for variant in variants:
            if variant["result"] == "compiler_reachable":
                findings.extend(fidelity_findings_for_variant(concept, variant))
    return findings


def measurement_buckets(
    *,
    rows: list[dict[str, Any]],
    target_by_id: dict[str, dict[str, Any]],
    fidelity_findings: list[dict[str, Any]],
    contract_fidelity_refusals: list[dict[str, Any]],
) -> dict[str, Any]:
    fidelity_violation_target_ids = {str(finding.get("target_id")) for finding in fidelity_findings}
    controls_by_concept: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        target = target_by_id[row["target_id"]]
        if target.get("sample_role") == "known_good_control":
            controls_by_concept[row["concept"]].append(row)

    entries: list[dict[str, Any]] = []
    for row in rows:
        target = target_by_id[row["target_id"]]
        if target.get("sample_role") not in MEASURED_SAMPLE_ROLES:
            continue
        bucket = bucket_for_positive_row(
            row,
            target=target,
            fidelity_violation_target_ids=fidelity_violation_target_ids,
            controls=controls_by_concept.get(row["concept"], []),
        )
        entries.append(bucket)

    for refusal in contract_fidelity_refusals:
        concept = str(refusal["concept"])
        bucket = bucket_for_refusal(refusal, controls=controls_by_concept.get(concept, []))
        entries.append(bucket)

    bucket_distribution = collections.Counter(entry["bucket"] for entry in entries)
    bug_distribution = collections.Counter(
        str(entry.get("subtype"))
        for entry in entries
        if entry["bucket"] == "contract_generation_bug" and entry.get("subtype")
    )
    family_distribution = collections.Counter(
        str(entry.get("family"))
        for entry in entries
        if entry["bucket"] in {"genuine_gap", "unvalidated_refusal"} and entry.get("family")
    )
    return {
        "bucket_distribution": dict(sorted(bucket_distribution.items())),
        "contract_generation_bug_distribution": dict(sorted(bug_distribution.items())),
        "gap_family_distribution": dict(sorted(family_distribution.items())),
        "entries": entries,
    }


def bucket_for_positive_row(
    row: dict[str, Any],
    *,
    target: dict[str, Any],
    fidelity_violation_target_ids: set[str],
    controls: list[dict[str, Any]],
) -> dict[str, Any]:
    target_id = str(row["target_id"])
    if row["result"] == "compiler_reachable" and target_id not in fidelity_violation_target_ids:
        return {
            "concept": row["concept"],
            "target_id": target_id,
            "bucket": "clean_reach",
            "providers_used": row.get("providers_used", []),
        }
    if row["result"] == "compiler_reachable" and target_id in fidelity_violation_target_ids:
        control_bucket = bucket_from_known_good_controls(controls, clean_subtype="too_weak")
        return {
            "concept": row["concept"],
            "target_id": target_id,
            **control_bucket,
            "auto_result": "degenerate_reach",
            "providers_used": row.get("providers_used", []),
        }
    direct_failure_buckets = {"unsupported_modality", "missing_primitive", "search_budget_exceeded", "runtime_gap"}
    if target.get("sample_role") == "frontier_probe":
        direct_failure_buckets = {*direct_failure_buckets, "missing_constraint"}
    if row.get("failure_taxonomy") in direct_failure_buckets:
        return {
            "concept": row["concept"],
            "target_id": target_id,
            "bucket": str(row.get("failure_taxonomy")),
            "auto_result": row["result"],
            "frontier_gap_taxonomy": target.get("frontier_gap_taxonomy"),
            "required_missing_capability": target.get("required_missing_capability"),
        }
    control_bucket = bucket_from_known_good_controls(controls, clean_subtype="too_strict")
    return {
        "concept": row["concept"],
        "target_id": target_id,
        **control_bucket,
        "auto_result": row["result"],
        "failure_taxonomy": row.get("failure_taxonomy"),
    }


def bucket_for_refusal(refusal: dict[str, Any], *, controls: list[dict[str, Any]]) -> dict[str, Any]:
    control_bucket = bucket_from_known_good_controls(controls, clean_subtype="too_weak")
    return {
        "concept": refusal["concept"],
        **control_bucket,
        "auto_result": "contract_fidelity_refused",
        "refusal_reason": refusal.get("reason"),
        "detail": refusal.get("detail"),
    }


def bucket_from_known_good_controls(controls: list[dict[str, Any]], *, clean_subtype: str) -> dict[str, Any]:
    if not controls:
        return {"bucket": "unvalidated_refusal"}
    if any(row.get("result") == "compiler_reachable" for row in controls):
        return {"bucket": "contract_generation_bug", "subtype": clean_subtype}
    taxonomies = sorted({str(row.get("failure_taxonomy")) for row in controls if row.get("failure_taxonomy")})
    if set(taxonomies) == {"missing_constraint"}:
        return {"bucket": "genuine_gap", "family": "identity_constrained_combination", "known_good_failure_taxonomy": "missing_constraint"}
    return {
        "bucket": "unvalidated_refusal",
        "known_good_failure_taxonomies": taxonomies,
    }


def fidelity_findings_for_variant(concept: str, variant: dict[str, Any]) -> list[dict[str, Any]]:
    expectation = variant.get("fidelity_expectation")
    if not isinstance(expectation, dict) or not expectation:
        return []
    providers = list(dict.fromkeys(str(provider) for provider in variant.get("providers_used", [])))
    rules = set(str(rule) for rule in variant.get("rules_used", []))
    violations: list[str] = []
    minimum_count = int(expectation.get("minimum_unique_provider_count") or 0)
    if minimum_count and len(providers) < minimum_count:
        violations.append(f"expected at least {minimum_count} unique providers")
    missing_all = [provider for provider in expectation.get("required_provider_all", []) if provider not in providers]
    if missing_all:
        violations.append(f"missing required providers: {', '.join(missing_all)}")
    for group in expectation.get("required_provider_any", []):
        group_values = [str(item) for item in group]
        if group_values and not any(item in providers for item in group_values):
            violations.append(f"missing one provider from: {', '.join(group_values)}")
    missing_rules = [rule for rule in expectation.get("required_rule_all", []) if rule not in rules]
    if missing_rules:
        violations.append(f"missing required rules: {', '.join(missing_rules)}")
    if not violations:
        return []
    return [
        {
            "code": "degenerate_reach_fidelity_violation",
            "concept": concept,
            "target_id": variant["target_id"],
            "contract_template_id": variant.get("contract_template_id"),
            "providers_used": providers,
            "rules_used": sorted(rules),
            "violations": violations,
            "expectation": expectation,
        }
    ]


def group_targets_by_concept(targets: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for target in targets:
        grouped[target["concept"]].append(target)
    return dict(sorted(grouped.items()))


def execution_node_cache_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    summary: collections.Counter[str] = collections.Counter()
    for row in rows:
        cache = row.get("execution_node_cache")
        if not isinstance(cache, dict):
            continue
        for key in ("hits", "local_hits", "shared_hits", "misses", "disabled", "bypassed"):
            summary[key] += int(cache.get(key) or 0)
    return dict(sorted(summary.items()))


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


def contract_has_concept_hint(concept: str, contract: dict[str, Any]) -> bool:
    return bool(concept) and concept.lower() in json.dumps(contract, sort_keys=True).lower()


def target_id_for(concept: str, variant_id: str) -> str:
    return sanitize_id(f"atlas_scale_{concept}_{variant_id}_v0")


def sanitize_id(value: str) -> str:
    sanitized = re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")
    if not sanitized or not sanitized[0].isalpha():
        sanitized = f"target_{sanitized}"
    return sanitized


def known_negative_variants(concept: str, taxonomy: str, missing: str) -> list[dict[str, Any]]:
    if taxonomy == "unsupported_modality":
        modality = "body_orientation" if "body" in missing or "orientation" in missing else "learned_model"
        return [
            {
                "variant_id": "negative_a",
                "target_contract": {
                    "desired_output": "classification",
                    "required_modalities": [modality],
                    "required_evidence": ["unavailable_model_score"],
                    "status_semantics": [{"field": "unavailable_model_score", "operator": "gte", "threshold": 0.5, "unit": "none"}],
                    "claim_boundary": "Known-negative control requiring an unavailable modality; should not become compiler-reachable.",
                },
            },
            {
                "variant_id": "negative_b",
                "target_contract": {
                    "desired_output": "classification",
                    "required_modalities": [modality],
                    "required_evidence": ["unavailable_probability"],
                    "status_semantics": [{"field": "unavailable_probability", "operator": "gte", "threshold": 0.5, "unit": "none"}],
                    "claim_boundary": "Known-negative control requiring unavailable model or body data; should fail as unsupported modality.",
                },
            },
        ]
    field = "unavailable_primitive_status"
    reason_field = "unavailable_primitive_reason"
    return [
        {
            "variant_id": "negative_a",
            "target_contract": {
                "desired_output": "classification",
                "required_evidence": [field],
                "status_semantics": [{"field": field, "required_value": "PASS"}],
                "claim_boundary": "Known-negative control requiring a missing primitive; should not become compiler-reachable.",
            },
        },
        {
            "variant_id": "negative_b",
            "target_contract": {
                "desired_output": "classification",
                "required_evidence": [field, reason_field],
                "status_semantics": [{"field": field, "required_value": "PASS"}],
                "claim_boundary": "Known-negative control requiring missing runtime evidence; should fail as missing primitive.",
            },
        },
    ]


def known_good_combination_variants(_concept: str) -> list[dict[str, Any]]:
    return [
        {
            "variant_id": "known_good_identity_return",
            "target_contract": {
                "desired_output": "classification",
                "required_evidence": [
                    "pass_chain_status",
                    "input_pass_episode_id",
                    "relay_pass_episode_id",
                    "input_passer_id",
                    "relay_player_id",
                    "terminal_receiver_id",
                    "terminal_controlled_reception_frame_id",
                ],
                "status_semantics": [{"field": "pass_chain_status", "required_value": "PASS"}],
                "composition_constraints": [
                    {
                        "kind": "same_player_return",
                        "left_field": "input_passer_id",
                        "right_field": "terminal_receiver_id",
                        "description": "The terminal receiver must be the original input passer.",
                    },
                    {
                        "kind": "distinct_entity_fields",
                        "value": "input_passer_id,relay_player_id",
                    },
                    {
                        "kind": "temporal_order",
                        "temporal_relation": "left_before_right",
                        "left_time_field": "relay_touch_frame_id",
                        "right_time_field": "terminal_controlled_reception_frame_id",
                        "maximum_gap_seconds": 6.0,
                    },
                ],
                "claim_boundary": (
                    "Known-good identity-constrained combination contract: observed pass-chain where the terminal "
                    "receiver is the original input passer. No planned combination, wall-pass intent, quality, "
                    "causation, or optimality claim."
                ),
            },
        }
    ]


def variants(template_id: str, a: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"variant_id": f"{template_id}_a", "target_contract": a},
        {"variant_id": f"{template_id}_b", "target_contract": b},
    ]


def carry_contracts(_concept: str) -> list[dict[str, Any]]:
    return variants(
        "carry",
        {
            "desired_output": "classification",
            "required_evidence": ["carry_status", "carrier_id", "carry_start_frame_id", "carry_end_frame_id", "carry_forward_progression_m"],
            "status_semantics": [{"field": "carry_status", "required_value": "PASS"}, {"field": "carry_forward_progression_m", "operator": "gte", "threshold": 3.0, "unit": "metre"}],
            "claim_boundary": "Observed controlled ball movement with a declared forward component; no skill, opponent-bypass, intent, or value claim.",
        },
        {
            "desired_output": "classification",
            "required_evidence": ["carry_status", "carry_reason", "carrier_id", "displacement_m", "control_model"],
            "status_semantics": [{"field": "carry_status", "required_value": "PASS"}, {"field": "displacement_m", "operator": "gte", "threshold": 3.0, "unit": "metre"}],
            "claim_boundary": "Observed movement-under-control under frozen control thresholds; no dribbling quality, defender-bypass, or causation claim.",
        },
    )


def pressure_contracts(_concept: str) -> list[dict[str, Any]]:
    return variants(
        "pressure",
        {
            "desired_output": "classification",
            "required_evidence": ["pressure_status", "nearest_defender_id", "nearest_defender_distance_m", "closing_speed_mps", "approach_angle_degrees", "coverage_status"],
            "status_semantics": [{"field": "pressure_status", "required_value": "PASS"}],
            "claim_boundary": "Observed nearest-defender distance, closing speed, and approach angle; no defender intent, pressure quality, or tactical causation.",
        },
        {
            "desired_output": "classification",
            "required_evidence": ["pressure_status", "pressure_reason", "carrier_id", "pressure_frame_id", "pressure_duration_seconds", "coverage_status"],
            "status_semantics": [{"field": "pressure_status", "required_value": "PASS"}],
            "claim_boundary": "Observed carrier-pressure components under declared thresholds; no effort, intent, quality, or decision-value claim.",
        },
    )


def transition_contracts(_concept: str) -> list[dict[str, Any]]:
    return variants(
        "transition",
        {
            "desired_output": "classification",
            "required_evidence": ["transition_status", "transition_type", "transition_frame_id", "previous_team_role", "new_team_role"],
            "status_semantics": [{"field": "transition_status", "required_value": "PASS"}],
            "claim_boundary": "Observed possession-role change at a transition anchor; no transition intent, quality, or tactical causation.",
        },
        {
            "desired_output": "classification",
            "required_evidence": ["transition_status", "transition_reason", "transition_frame_id", "zone_status", "zone_name"],
            "status_semantics": [{"field": "transition_status", "required_value": "PASS"}],
            "claim_boundary": "Observed transition anchor with optional zone evidence; no counterattack or recovery-quality claim.",
        },
    )


def transition_outcome_contracts(_concept: str) -> list[dict[str, Any]]:
    return variants(
        "transition_outcome",
        {
            "desired_output": "classification",
            "required_evidence": ["transition_status", "transition_frame_id", "outcome_window_status", "minimum_settled_possession_seconds"],
            "status_semantics": [{"field": "transition_status", "required_value": "PASS"}, {"field": "outcome_window_status", "required_value": "PASS"}],
            "claim_boundary": "Observed transition followed by ball-alive retention for a frozen duration; no settled-possession quality or intent.",
        },
        {
            "desired_output": "classification",
            "required_evidence": ["transition_status", "outcome_window_status", "outcome_window_start_frame_id", "outcome_window_end_frame_id"],
            "status_semantics": [{"field": "transition_status", "required_value": "PASS"}, {"field": "outcome_window_status", "required_value": "PASS"}],
            "claim_boundary": "Observed transition and declared outcome window only; no phase quality, causal, or decision claim.",
        },
    )


def support_contracts(_concept: str) -> list[dict[str, Any]]:
    return variants(
        "support",
        {
            "desired_output": "classification",
            "required_evidence": ["support_arrival_status", "support_region_mode", "support_anchor_frame_id", "supporting_player_ids", "maximum_arrival_seconds"],
            "status_semantics": [{"field": "support_arrival_status", "required_value": "PASS"}],
            "claim_boundary": "Observed teammate support arrival under a declared region/window; no support quality, intent, or optimality.",
        },
        {
            "desired_output": "classification",
            "required_evidence": ["support_arrival_status", "support_arrival_reason", "first_arrival_seconds_after_anchor", "coverage_status"],
            "status_semantics": [{"field": "support_arrival_status", "required_value": "PASS"}],
            "claim_boundary": "Observed support timing and coverage only; no communication, role, or tactical correctness claim.",
        },
    )


def local_number_contracts(_concept: str) -> list[dict[str, Any]]:
    return variants(
        "local_number",
        {
            "desired_output": "classification",
            "required_evidence": ["local_number_status", "perspective_count", "defending_count", "local_number_difference", "radius_m"],
            "status_semantics": [{"field": "local_number_status", "required_value": "PASS"}],
            "claim_boundary": "Observed local player counts around a reference point; no pressure, role, or support-quality claim.",
        },
        {
            "desired_output": "classification",
            "required_evidence": ["local_number_status", "local_number_reason", "perspective_in_region_player_ids", "defending_in_region_player_ids", "coverage_status"],
            "status_semantics": [{"field": "local_number_status", "required_value": "PASS"}],
            "claim_boundary": "Observed local numerical relation with coverage evidence; no tactical role or superiority-quality claim.",
        },
    )


def distance_contracts(_concept: str) -> list[dict[str, Any]]:
    return variants(
        "distance",
        {
            "desired_output": "classification",
            "required_evidence": ["pairwise_distance_status", "distance_m", "entity_a_id", "entity_b_id", "distance_frame_id"],
            "status_semantics": [{"field": "pairwise_distance_status", "required_value": "PASS"}],
            "claim_boundary": "Observed pairwise distance at a declared frame; no availability, intent, or tactical value claim.",
        },
        {
            "desired_output": "classification",
            "required_evidence": ["pairwise_distance_status", "pairwise_distance_reason", "distance_m", "maximum_distance_m"],
            "status_semantics": [{"field": "pairwise_distance_status", "required_value": "PASS"}],
            "claim_boundary": "Observed distance threshold relation only; no pressure or marking assignment claim.",
        },
    )


def velocity_contracts(_concept: str) -> list[dict[str, Any]]:
    return variants(
        "velocity",
        {
            "desired_output": "classification",
            "required_evidence": ["velocity_status", "speed_mps", "velocity_vx_mps", "velocity_vy_mps", "velocity_frame_id"],
            "status_semantics": [{"field": "velocity_status", "required_value": "PASS"}],
            "claim_boundary": "Displacement-derived velocity components over a lookback window; no effort, intent, or future trajectory claim.",
        },
        {
            "desired_output": "classification",
            "required_evidence": ["velocity_status", "velocity_reason", "speed_mps", "velocity_dt_seconds", "velocity_entity_id"],
            "status_semantics": [{"field": "velocity_status", "required_value": "PASS"}, {"field": "speed_mps", "operator": "gte", "threshold": 0.5, "unit": "none"}],
            "claim_boundary": "Observed speed above a declared threshold; no run type, fatigue, or effort-quality claim.",
        },
    )


def time_to_arrival_contracts(_concept: str) -> list[dict[str, Any]]:
    return variants(
        "time_to_arrival",
        {
            "desired_output": "classification",
            "required_evidence": ["time_to_arrival_status", "minimum_arrival_seconds", "nearest_arrival_player_id", "reachable_verdict_bias"],
            "status_semantics": [{"field": "time_to_arrival_status", "required_value": "PASS"}],
            "claim_boundary": "Static-point straight-line arrival estimate with explicit point-mass bias; no pitch control or intent claim.",
        },
        {
            "desired_output": "classification",
            "required_evidence": ["time_to_arrival_status", "time_to_arrival_reason", "coverage_status", "reachability_model", "momentum_policy"],
            "status_semantics": [{"field": "time_to_arrival_status", "required_value": "PASS"}],
            "claim_boundary": "Observed reachability under declared max-speed assumptions; no moving-ball interception or space-value claim.",
        },
    )


def compactness_contracts(_concept: str) -> list[dict[str, Any]]:
    return variants(
        "compactness",
        {
            "desired_output": "classification",
            "required_evidence": ["team_compactness_status", "team_width_m", "team_depth_m", "team_area_m2", "observed_player_count"],
            "status_semantics": [{"field": "team_compactness_status", "required_value": "PASS"}],
            "claim_boundary": "Observed team shape dimensions at a declared frame; no tactical quality or role taxonomy.",
        },
        {
            "desired_output": "classification",
            "required_evidence": ["team_compactness_status", "team_compactness_reason", "maximum_team_width_m", "maximum_team_depth_m"],
            "status_semantics": [{"field": "team_compactness_status", "required_value": "PASS"}],
            "claim_boundary": "Observed compactness threshold relation only; no quality, intent, or causation claim.",
        },
    )


def switch_contracts(_concept: str) -> list[dict[str, Any]]:
    return variants(
        "switch",
        {
            "desired_output": "classification",
            "required_evidence": ["switch_status", "lateral_displacement_m", "release_frame_id", "reception_frame_id"],
            "status_semantics": [{"field": "switch_status", "required_value": "PASS"}],
            "claim_boundary": "Observed lateral ball movement across declared thresholds; no tactical intent or success-quality claim.",
        },
        {
            "desired_output": "classification",
            "required_evidence": ["switch_status", "switch_reason", "release_lateral_side", "reception_lateral_side", "switch_duration_seconds"],
            "status_semantics": [{"field": "switch_status", "required_value": "PASS"}],
            "claim_boundary": "Observed switch-of-play geometry only; no claim that it was planned, optimal, or tactically correct.",
        },
    )


def line_contracts(_concept: str) -> list[dict[str, Any]]:
    return variants(
        "line",
        {
            "desired_output": "classification",
            "required_evidence": ["multi_line_status", "observed_line_count", "target_line_rank", "line_x_m", "defensive_line_player_ids"],
            "status_semantics": [{"field": "multi_line_status", "required_value": "PASS"}],
            "claim_boundary": "Observed geometric line rank from tracked defenders; no tactical role taxonomy or definitive line-break claim.",
        },
        {
            "desired_output": "classification",
            "required_evidence": ["line_status", "line_x_m", "line_compactness_m", "defenders_goal_side_count"],
            "status_semantics": [{"field": "line_status", "required_value": "PASS"}],
            "claim_boundary": "Observed defensive-line geometry only; no midfield/backline role label, intent, or quality claim.",
        },
    )


def pass_contracts(_concept: str) -> list[dict[str, Any]]:
    return variants(
        "controlled_pass",
        {
            "desired_output": "classification",
            "required_evidence": ["controlled_pass_status", "pass_episode_id", "physical_release_frame_id", "controlled_reception_frame_id", "receiver_id"],
            "status_semantics": [{"field": "controlled_pass_status", "required_value": "PASS"}],
            "claim_boundary": "Observed event-linked controlled pass with tracking-confirmed endpoints; no pass quality or intent claim.",
        },
        {
            "desired_output": "classification",
            "required_evidence": ["controlled_pass_status", "forward_progression_m", "release_detection_status", "controlled_reception_status"],
            "status_semantics": [{"field": "controlled_pass_status", "required_value": "PASS"}],
            "claim_boundary": "Observed controlled pass episode and forward progression only; no tactical or probabilistic claim.",
        },
    )


def action_contracts(_concept: str) -> list[dict[str, Any]]:
    return variants(
        "action_anchor",
        {
            "desired_output": "classification",
            "required_evidence": ["action_event_status", "action_type", "event_anchor_frame_id", "passer_id", "receiver_id"],
            "status_semantics": [{"field": "action_event_status", "required_value": "PASS"}],
            "claim_boundary": "Observed event/action anchor from synchronized event data; no tactical pattern or intention claim.",
        },
        {
            "desired_output": "classification",
            "required_evidence": ["action_event_status", "action_event_reason", "event_type", "event_frame_offset_ms"],
            "status_semantics": [{"field": "action_event_status", "required_value": "PASS"}],
            "claim_boundary": "Observed action-event alignment only; no quality, plan, or tactical causation claim.",
        },
    )


def action_chain_contracts(_concept: str) -> list[dict[str, Any]]:
    return variants(
        "action_chain",
        {
            "desired_output": "classification",
            "required_evidence": [
                "action_chain_status",
                "chain_length",
                "first_action_anchor_id",
                "second_action_anchor_id",
                "action_gap_seconds",
            ],
            "status_semantics": [{"field": "action_chain_status", "required_value": "PASS"}],
            "claim_boundary": "Observed adjacent same-team action sequence under a frozen event-time gap; no tactical pattern, plan, or causation claim.",
        },
        {
            "desired_output": "classification",
            "required_evidence": [
                "action_chain_status",
                "action_chain_reason",
                "maximum_action_gap_seconds",
                "first_action_anchor_id",
                "second_action_anchor_id",
            ],
            "status_semantics": [{"field": "action_chain_status", "required_value": "PASS"}],
            "claim_boundary": "Observed ordered action-chain anchors only; no named-combination, role, intent, or quality claim.",
        },
    )


def pass_chain_contracts(_concept: str) -> list[dict[str, Any]]:
    return variants(
        "pass_chain",
        {
            "desired_output": "classification",
            "required_evidence": [
                "one_touch_relay_status",
                "pass_chain_status",
                "input_pass_episode_id",
                "relay_player_id",
                "terminal_receiver_id",
                "terminal_controlled_reception_frame_id",
            ],
            "status_semantics": [{"field": "pass_chain_status", "required_value": "PASS"}],
            "claim_boundary": "Observed event-linked relay plus terminal controlled reception; no planned combination, third-man, or decision-quality claim.",
        },
        {
            "desired_output": "classification",
            "required_evidence": [
                "one_touch_relay_status",
                "pass_chain_status",
                "pass_chain_reason",
                "relay_touch_frame_id",
                "terminal_pass_episode_id",
                "declared_next_pass_recipient_id",
            ],
            "status_semantics": [{"field": "pass_chain_status", "required_value": "PASS"}],
            "claim_boundary": "Observed pass-chain receipt sequence under existing relay thresholds; no intent, optimality, or tactical causation claim.",
        },
    )


def carry_pressure_change_contracts(_concept: str) -> list[dict[str, Any]]:
    base_constraints = [
        {"kind": "same_anchor_identity", "left_key_field": "anchor_id", "right_key_field": "anchor_id"},
        {"kind": "frame_alignment", "before_frame_field": "carry_start_frame_id", "after_frame_field": "carry_end_frame_id"},
        {
            "kind": "before_after_same_anchor",
            "value_family": "pressure_distance",
            "value_fields": ["nearest_defender_distance_m"],
            "status_fields": ["pressure_status"],
            "after_status_field": "none",
            "change_mode": "increase_at_least",
            "minimum_change_m": 2.0,
            "maximum_before_value_m": 4.0,
        },
    ]
    return variants(
        "carry_pressure_change",
        {
            "desired_output": "classification",
            "required_evidence": ["join_status", "carry_status", "carrier_id", "carry_start_frame_id", "carry_end_frame_id", "change_status", "before_value", "after_value", "delta_value"],
            "status_semantics": [{"field": "join_status", "required_value": "PASS"}],
            "composition_constraints": base_constraints,
            "claim_boundary": "Nearest-defender distance increased across an observed carry; no pressure-breaking quality, opponent bypass, intent, or causation.",
        },
        {
            "desired_output": "classification",
            "required_evidence": ["join_status", "join_reason", "carry_status", "change_status", "before_value_field", "after_value_field", "delta_value"],
            "status_semantics": [{"field": "join_status", "required_value": "PASS"}],
            "composition_constraints": base_constraints,
            "claim_boundary": "Observed carry joined to before/after pressure-distance change; no defender-beaten or decision-quality claim.",
        },
    )


def compactness_change_contracts(_concept: str) -> list[dict[str, Any]]:
    constraints = [
        {"kind": "frame_alignment", "before_frame_field": "physical_release_frame_id", "after_frame_field": "controlled_reception_frame_id"},
        {
            "kind": "before_after_same_anchor",
            "value_family": "team_width",
            "value_fields": ["team_width_m"],
            "status_fields": ["team_compactness_status"],
            "after_status_field": "team_compactness_status",
            "change_mode": "absolute_delta_at_least",
            "minimum_change_m": 4.0,
            "maximum_before_value_m": 80.0,
        },
    ]
    return variants(
        "compactness_change",
        {
            "desired_output": "classification",
            "required_evidence": ["change_status", "before_value", "after_value", "delta_value", "minimum_change_m"],
            "status_semantics": [{"field": "change_status", "required_value": "PASS"}],
            "composition_constraints": constraints,
            "claim_boundary": "Observed team-width change across a shared action anchor; no tactical quality, causation, or intent claim.",
        },
        {
            "desired_output": "classification",
            "required_evidence": ["change_status", "change_reason", "before_value_field", "after_value_field", "delta_value"],
            "status_semantics": [{"field": "change_status", "required_value": "PASS"}],
            "composition_constraints": constraints,
            "claim_boundary": "Observed before/after compactness delta only; no shape-quality or coaching interpretation.",
        },
    )


TEMPLATES: tuple[ContractTemplate, ...] = (
    ContractTemplate("carry_pressure_change", ("carry_out_of_pressure", "pressure_change_after"), carry_pressure_change_contracts),
    ContractTemplate("transition_outcome", ("retention", "retained", "settled", "outcome_window", "attacking_transition_window", "defensive_transition_window"), transition_outcome_contracts),
    ContractTemplate("compactness_change", ("shape_change_after", "line_state_change_after"), compactness_change_contracts),
    ContractTemplate("pass_chain", ("pass_chain", "one_touch", "one touch", "relay", "layoff", "lay off"), pass_chain_contracts),
    ContractTemplate("action_chain", ("action_chain", "action chain", "followed_by", "followed by", "sequence"), action_chain_contracts),
    ContractTemplate("pressure", ("pressure", "press", "carrier"), pressure_contracts),
    ContractTemplate("carry", ("carry", "dribbl"), carry_contracts),
    ContractTemplate("velocity", ("velocity", "speed", "movement", "run"), velocity_contracts),
    ContractTemplate("local_number", ("local_number", "number", "count", "superiority", "inferiority", "overload", "balance"), local_number_contracts),
    ContractTemplate("support", ("support", "option"), support_contracts),
    ContractTemplate("time_to_arrival", ("arrival", "reachability", "time_to_location"), time_to_arrival_contracts),
    ContractTemplate("switch", ("switch",), switch_contracts),
    ContractTemplate("line", ("line", "unit"), line_contracts),
    ContractTemplate("compactness", ("compactness", "shape", "width", "depth"), compactness_contracts),
    ContractTemplate("distance", ("distance", "proximity"), distance_contracts),
    ContractTemplate("transition", ("transition", "regain", "loss"), transition_contracts),
    ContractTemplate("controlled_pass", ("pass", "reception", "receive", "progression"), pass_contracts),
    ContractTemplate("action_anchor", ("action", "restart", "followed_by", "sequence", "anchor"), action_contracts),
)


def pct(numerator: int, denominator: int) -> float:
    return round(100 * numerator / max(denominator, 1), 1)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
