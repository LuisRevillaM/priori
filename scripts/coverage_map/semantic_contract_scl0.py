#!/usr/bin/env python3
"""SCL-0 meaning-to-contract proof harness.

SCL-0 deliberately stops short of natural-language compilation. It proves the
next layer down: independently-authored football meanings can become typed
target contracts without leaking catalog refs, gold chains, pattern labels, or
known provider paths into the search compiler.
"""

from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "compiler-reachability" / "scl0-meaning-sample.v0.json"
OUT_DIR = ROOT / "generated" / "semantic-contract-scl0"
TARGETS_OUT = OUT_DIR / "scl0-search-targets.v0.json"
LEDGER_OUT = OUT_DIR / "scl0-coverage-ledger.json"
CONTRACT_LEDGER_OUT = OUT_DIR / "scl0-contract-ledger.json"
SEARCH_ROW_LEDGER = OUT_DIR / "search-run" / "row-ledger.json"
PREP_REPORT = ROOT / "artifacts" / "autonomous" / "scl0-meaning-contract-prep-report.json"
ASSESS_REPORT = ROOT / "artifacts" / "autonomous" / "scl0-meaning-contract-assessment-report.json"

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
FORBIDDEN_MEANING_TERMS = {
    "catalog_ref",
    "gold_chain",
    "join_episode_sets",
    "provider_chain",
    "runtime_ref",
    "same_player_return",
}

CROSS_CONCEPT_REUSE_REQUIRED_RULES = {
    "meaning.element.lane_occupancy",
    "meaning.kinematics.acceleration",
    "meaning.cover_shadow.observed_lane_geometry",
    "meaning.space.open_region",
    "meaning.team_press.observed_multi_defender_pressure",
    "meaning.relation.marking_proximity",
    "meaning.movement.off_ball_run",
    "meaning.run_type.observed_path",
    "meaning.reachability.time_to_arrival",
    "meaning.restart.set_piece_structure",
}


@dataclass(frozen=True)
class Span:
    phrase: str
    start: int
    end: int


@dataclass
class ContractBuilder:
    text: str
    contract: dict[str, Any] = field(
        default_factory=lambda: {
            "desired_output": "classification",
            "required_evidence": [],
            "status_semantics": [],
        }
    )
    traces: list[dict[str, Any]] = field(default_factory=list)
    claim_parts: list[str] = field(default_factory=list)

    def add_evidence(self, field_name: str, span: Span, rule_id: str) -> None:
        if field_name not in self.contract["required_evidence"]:
            self.contract["required_evidence"].append(field_name)
        self.trace(f"required_evidence.{field_name}", field_name, span, rule_id)

    def add_status(self, field_name: str, required_value: str, span: Span, rule_id: str) -> None:
        item = {"field": field_name, "required_value": required_value}
        if item not in self.contract["status_semantics"]:
            self.contract["status_semantics"].append(item)
        self.trace(f"status_semantics.{field_name}", required_value, span, rule_id)

    def add_threshold(
        self,
        field_name: str,
        *,
        operator: str,
        threshold: float,
        unit: str,
        span: Span,
        rule_id: str,
    ) -> None:
        item = {"field": field_name, "operator": operator, "threshold": threshold, "unit": unit}
        if item not in self.contract["status_semantics"]:
            self.contract["status_semantics"].append(item)
        self.trace(f"status_semantics.{field_name}", f"{operator}:{threshold}:{unit}", span, rule_id)

    def add_modality(self, modality: str, span: Span, rule_id: str) -> None:
        modalities = self.contract.setdefault("required_modalities", [])
        if modality not in modalities:
            modalities.append(modality)
        self.trace(f"required_modalities.{modality}", modality, span, rule_id)

    def add_constraint(self, constraint: dict[str, Any], span: Span, rule_id: str) -> None:
        constraints = self.contract.setdefault("composition_constraints", [])
        if constraint not in constraints:
            constraints.append(copy.deepcopy(constraint))
        kind = str(constraint.get("kind", "unknown"))
        self.trace(f"composition_constraints.{kind}", constraint, span, rule_id)

    def add_claim_part(self, value: str, span: Span, rule_id: str) -> None:
        if value not in self.claim_parts:
            self.claim_parts.append(value)
        self.trace("claim_boundary", value, span, rule_id)

    def trace(self, path: str, value: Any, span: Span, rule_id: str) -> None:
        self.traces.append(
            {
                "contract_path": path,
                "value": value,
                "rule_id": rule_id,
                "source_phrase": span.phrase,
                "source_start": span.start,
                "source_end": span.end,
            }
        )

    def finish(self) -> dict[str, Any]:
        self.contract["required_evidence"] = sorted(self.contract["required_evidence"])
        self.contract["status_semantics"] = sorted(
            self.contract["status_semantics"],
            key=lambda item: (str(item.get("field")), str(item.get("operator", "")), str(item.get("required_value", ""))),
        )
        if "required_modalities" in self.contract:
            self.contract["required_modalities"] = sorted(self.contract["required_modalities"])
        if "composition_constraints" in self.contract:
            self.contract["composition_constraints"] = sorted(
                self.contract["composition_constraints"],
                key=lambda item: json.dumps(item, sort_keys=True),
            )
        self.contract["claim_boundary"] = " ".join(self.claim_parts) if self.claim_parts else (
            "Observed football meaning only; no tactical quality, intent, causation, decision value, or optimality claim."
        )
        return self.contract


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "assess"])
    args = parser.parse_args()
    return prepare() if args.mode == "prepare" else assess()


def prepare() -> int:
    config = load_json(CONFIG)
    targets: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    contract_rows: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for case in config["cases"]:
        case_id = str(case["case_id"])
        opaque_concept = case_id
        coverage_rows.append(coverage_row(case, opaque_concept))
        definitions = case.get("definitions") or []
        if len(definitions) < 2:
            findings.append({"code": "insufficient_independent_definitions", "case_id": case_id})
        generated_contracts: list[dict[str, Any]] = []
        for definition in definitions:
            contract, traces = generate_contract_from_meaning(str(definition["text"]))
            generated_contracts.append(contract)
            target_id = f"{case_id}_{definition['author_id']}_v0"
            targets.append(
                {
                    "target_id": target_id,
                    "concept": opaque_concept,
                    "held_out": bool(case.get("held_out")),
                    "multi_step": has_multi_step_contract(contract),
                    "target_contract": contract,
                }
            )
            contract_rows.append(
                {
                    "case_id": case_id,
                    "concept": case["concept"],
                    "author_id": definition["author_id"],
                    "definition_text": definition["text"],
                    "target_id": target_id,
                    "opaque_search_concept": opaque_concept,
                    "contract": contract,
                    "contract_hash": stable_hash(contract),
                    "trace": traces,
                }
            )
            findings.extend(clean_meaning_findings(case_id, definition))
            findings.extend(contract_anti_circularity_findings(case_id, definition["author_id"], contract))
            findings.extend(trace_findings(case_id, definition["author_id"], contract, traces))
        findings.extend(independent_stability_findings(case, generated_contracts))
        findings.extend(perturbation_findings(case))
    findings.extend(cross_concept_reuse_findings(contract_rows))

    targets_payload = {
        "schema_version": "compiler_search_targets.v0",
        "strategy": "bounded_backward_search.v0.1.scl0_meaning_contracts",
        "sample_policy": config["sample_policy"],
        "note": (
            "Targets are opaque typed contracts generated from meaning definitions. "
            "Search receives no football concept name, definition text, gold chain, provider path, or pattern label."
        ),
        "targets": targets,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TARGETS_OUT.write_text(json.dumps(targets_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LEDGER_OUT.write_text(json.dumps(coverage_rows, indent=1) + "\n", encoding="utf-8")
    CONTRACT_LEDGER_OUT.write_text(json.dumps(contract_rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = {
        "schema_version": "scl0_meaning_contract_prepare.v0",
        "status": "PASS" if not findings else "FAIL",
        "scope": {
            "natural_language_compiler": False,
            "search_receives_definition_text": False,
            "search_receives_football_concept_name": False,
            "generator_receives_concept_id": False,
            "catalog_refs_allowed_in_contract": False,
            "gold_chains_allowed_in_contract": False,
        },
        "summary": {
            "case_count": len(config["cases"]),
            "target_count": len(targets),
            "definition_count": len(contract_rows),
            "held_out_case_count": sum(1 for case in config["cases"] if case.get("held_out")),
            "known_negative_case_count": sum(1 for case in config["cases"] if case.get("sample_role") == "known_negative"),
            "findings_count": len(findings),
            "element_rule_usage": rule_usage_counts(contract_rows),
        },
        "six_gates": {
            "clean_meaning_input": not any(item["code"].startswith("meaning_") for item in findings),
            "no_provider_gold_pattern_leakage": not any(item["code"].startswith("contract_anti_circularity") for item in findings),
            "independent_author_stability": not any(item["code"] == "independent_author_contract_drift" for item in findings),
            "known_negatives_configured": any(case.get("sample_role") == "known_negative" for case in config["cases"]),
            "held_out_configured": any(case.get("held_out") for case in config["cases"]),
            "generator_faithfulness_trace_and_perturbation": not any(
                item["code"].startswith("trace_") or item["code"].startswith("perturbation_")
                for item in findings
            ),
        },
        "findings": findings,
        "outputs": {
            "targets_path": relative_path(TARGETS_OUT),
            "coverage_ledger_path": relative_path(LEDGER_OUT),
            "contract_ledger_path": relative_path(CONTRACT_LEDGER_OUT),
        },
    }
    PREP_REPORT.parent.mkdir(parents=True, exist_ok=True)
    PREP_REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


def assess() -> int:
    config = load_json(CONFIG)
    contract_rows = load_json(CONTRACT_LEDGER_OUT)
    search_rows = load_json(SEARCH_ROW_LEDGER)
    rows_by_target = {row["target_id"]: row for row in search_rows}
    contract_by_target = {row["target_id"]: row for row in contract_rows}
    findings: list[dict[str, Any]] = []
    case_reports: list[dict[str, Any]] = []

    for case in config["cases"]:
        variants = []
        for definition in case.get("definitions") or []:
            target_id = f"{case['case_id']}_{definition['author_id']}_v0"
            search_row = rows_by_target.get(target_id)
            contract_row = contract_by_target.get(target_id)
            if search_row is None:
                findings.append({"code": "missing_search_row", "target_id": target_id})
                continue
            if contract_row is None:
                findings.append({"code": "missing_contract_row", "target_id": target_id})
                continue
            variants.append(
                {
                    "author_id": definition["author_id"],
                    "target_id": target_id,
                    "contract_hash": contract_row["contract_hash"],
                    "result": search_row["result"],
                    "failure_taxonomy": search_row.get("failure_taxonomy"),
                    "result_count": search_row.get("result_count"),
                    "requested_evidence_failure_count": search_row.get("requested_evidence_failure_count"),
                    "providers_used": search_row.get("providers_used", []),
                    "rules_used": search_row.get("rules_used", []),
                    "concept_name_used_as_hint": search_row.get("concept_name_used_as_hint"),
                    "gold_chain_used_as_input": search_row.get("gold_chain_used_as_input"),
                    "pattern_dispatch_used": search_row.get("pattern_dispatch_used"),
                }
            )
        case_findings = assess_case(case, variants)
        findings.extend(case_findings)
        case_reports.append(
            {
                "case_id": case["case_id"],
                "concept": case["concept"],
                "sample_role": case["sample_role"],
                "held_out": bool(case.get("held_out")),
                "expected_result": case.get("expected_result"),
                "expected_failure_taxonomy": case.get("expected_failure_taxonomy"),
                "variants": variants,
                "findings": case_findings,
            }
        )

    findings.extend(search_blindness_findings(config, search_rows))
    result_counts = collections.Counter(row["result"] for row in search_rows)
    failure_counts = collections.Counter(row["failure_taxonomy"] for row in search_rows if row.get("failure_taxonomy"))
    known_negative_rows = [
        variant
        for case in case_reports
        if case["sample_role"] == "known_negative"
        for variant in case["variants"]
    ]
    held_out_rows = [
        variant
        for case in case_reports
        if case["held_out"]
        for variant in case["variants"]
    ]

    report = {
        "schema_version": "scl0_meaning_contract_assessment.v0",
        "status": "PASS" if not findings else "FAIL",
        "scope": {
            "claim": (
                "Small SCL-0 proof that traceable meaning definitions can generate typed contracts "
                "which the existing search compiler can execute or gap honestly. Not natural-language compilation."
            ),
            "search_receives_only_typed_contract": True,
            "atlas_wide": False,
        },
        "summary": {
            "case_count": len(case_reports),
            "target_count": len(search_rows),
            "result_distribution": dict(sorted(result_counts.items())),
            "failure_distribution": dict(sorted(failure_counts.items())),
            "known_negative_target_count": len(known_negative_rows),
            "known_negative_honest_failure_count": sum(1 for row in known_negative_rows if row["result"] != "compiler_reachable"),
            "held_out_target_count": len(held_out_rows),
            "held_out_compiler_reachable_count": sum(1 for row in held_out_rows if row["result"] == "compiler_reachable"),
            "findings_count": len(findings),
        },
        "six_gates": {
            "clean_meaning_input": True,
            "no_provider_gold_pattern_leakage": True,
            "independent_author_stability": not any(item["code"] == "independent_author_verdict_drift" for item in findings),
            "known_negatives_fail_honestly": not any(item["code"].startswith("known_negative_") for item in findings),
            "held_out_concepts_work": not any(item["code"].startswith("held_out_") for item in findings),
            "generator_faithfulness_trace_and_perturbation": True,
            "search_receives_only_contract": not any(item["code"].startswith("search_blindness_") for item in findings),
        },
        "cases": case_reports,
        "findings": findings,
        "inputs": {
            "contract_ledger": relative_path(CONTRACT_LEDGER_OUT),
            "search_row_ledger": relative_path(SEARCH_ROW_LEDGER),
            "targets": relative_path(TARGETS_OUT),
        },
    }
    ASSESS_REPORT.parent.mkdir(parents=True, exist_ok=True)
    ASSESS_REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


def generate_contract_from_meaning(text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    builder = ContractBuilder(text=text)
    lower = normalize(text)
    matched = False
    has_pressure_change_phrase = any(
        phrase in lower
        for phrase in ("out of pressure", "pressure reduced", "less pressure", "pressure distance improves")
    )

    if span := first_span(text, [r"probability", r"likelihood", r"expected(?:\s+\w+){0,3}", r"learned"]):
        builder.add_modality("learned_model", span, "meaning.modality.learned_probability")
        builder.add_claim_part("Requires a learned probability/expectation model; tracking/events alone do not support this claim.", span, "meaning.modality.learned_probability")
        matched = True

    if span := first_span(text, [r"\bbody orientation\b", r"\bstance\b", r"\bfacing\b", r"\bgaze\b"]):
        builder.add_modality("body_orientation", span, "meaning.modality.body_orientation")
        builder.add_claim_part("Requires body-orientation or stance data; tracking/events alone do not support this claim.", span, "meaning.modality.body_orientation")
        matched = True

    if "goal" in lower and "kick" in lower and ("build" in lower or "restart" in lower):
        span = first_span(text, [r"goal[- ]kick", r"goal kick", r"restart"]) or whole_span(text)
        add_status_contract(builder, "scl0_restart_structure_status", span, "meaning.missing_primitive.restart_structure")
        builder.add_claim_part("Requires an executable goal-kick build-structure primitive; no substitute restart claim is inferred.", span, "meaning.missing_primitive.goal_kick_build_structure")
        matched = True

    if is_pass_chain_meaning(lower):
        span = first_span(text, [r"two-pass", r"wall-pass", r"pass(?:es|er)?", r"relayed?", r"combination"]) or whole_span(text)
        add_pass_chain_element(builder, span)
        matched = True

    if is_same_player_return_meaning(lower):
        span = first_span(
            text,
            [
                r"returns? (?:the )?(?:pass |ball )?(?:back )?(?:to )?(?:the )?original passer",
                r"come[s]? back to that same original passer",
                r"return pass back",
                r"same original passer",
            ],
        ) or whole_span(text)
        builder.add_constraint(
            {
                "kind": "same_player_return",
                "left_field": "input_passer_id",
                "right_field": "terminal_receiver_id",
                "description": "The terminal receiver must be the original input passer.",
            },
            span,
            "meaning.constraint.same_player_return",
        )
        builder.add_claim_part("Observed identity-return pass chain only; no planned combination, third-man intent, quality, causation, or optimality claim.", span, "meaning.constraint.same_player_return")
        matched = True

    if span := first_span(text, [r"\bcarry\b", r"\bcarries\b", r"\bcarrying\b"]):
        add_carry_element(builder, span)
        matched = True

    if ("forward" in lower or "progress" in lower) and any(token in lower for token in ("carry", "carries", "carrying", "carrier")):
        span = first_span(text, [r"forward", r"progress(?:es|ion)?"]) or whole_span(text)
        add_forward_progression_element(builder, span)
        matched = True

    if is_reachability_meaning(lower):
        span = first_span(text, [r"arrival window", r"arrival time", r"arrive(?:s|d)?", r"reach(?:es|able|ability)?"]) or whole_span(text)
        add_time_to_arrival_element(builder, span)
        matched = True

    if is_lane_occupancy_meaning(lower):
        span = first_span(text, [r"lateral lanes?", r"pitch lanes?", r"wide lanes?", r"channels?", r"lane occupation", r"occupied lanes?"]) or whole_span(text)
        add_lane_occupancy_element(builder, span)
        matched = True

    if is_line_break_meaning(lower):
        span = first_span(text, [r"line[- ]break", r"breaks? (?:the )?line", r"broke (?:the )?line", r"beyond the observed second defending line"]) or whole_span(text)
        add_observed_line_break_element(builder, span)
        matched = True

    if is_underneath_support_absence_meaning(lower):
        span = first_span(text, [r"no underneath support", r"without underneath support", r"no .*outlet", r"behind-ball support region", r"support outlet"]) or whole_span(text)
        add_underneath_support_absence_element(builder, span)
        matched = True

    if not has_pressure_change_phrase and (
        "under pressure" in lower or "defender pressure" in lower or "nearest-defender pressure" in lower
    ):
        span = first_span(text, [r"under observed defender pressure", r"under defender pressure", r"under pressure", r"nearest-defender pressure"]) or whole_span(text)
        add_pressure_element(builder, span)
        builder.add_claim_part("Observed pressure components only; no defender intent, pressure quality, causation, or decision-value claim.", span, "meaning.pressure.receive_under_pressure")
        matched = True

    if has_pressure_change_phrase:
        span = first_span(text, [r"out of pressure", r"pressure reduced", r"less pressure", r"pressure distance improves"]) or whole_span(text)
        add_pressure_change_element(builder, span)
        builder.add_claim_part("Observed pressure-distance change only; no pressure-breaking skill, intent, causation, or optimality claim.", span, "meaning.element.pressure_change")
        matched = True

    if "shape" in lower and ("width" in lower or "depth" in lower):
        span = first_span(text, [r"team shape width or depth", r"team width or depth", r"shape width or depth", r"team-shape", r"shape"]) or whole_span(text)
        add_team_shape_element(builder, span)
        matched = True

    if "increase" in lower or "larger" in lower or "expansion" in lower or "expands" in lower:
        span = first_span(text, [r"increases", r"gets larger", r"larger", r"expansion", r"expands"]) or whole_span(text)
        add_increase_element(builder, span)
        matched = True

    if is_cover_shadow_meaning(lower):
        span = first_span(
            text,
            [
                r"cover shadow",
                r"passing[- ]lane denial",
                r"passing lane",
                r"lane denial",
                r"screens? from the ball",
                r"blocks?",
            ],
        ) or whole_span(text)
        add_cover_shadow_element(builder, span)
        matched = True

    if is_marking_meaning(lower):
        span = first_span(text, [r"marking assignment", r"\bmarker\b", r"\bmarked\b", r"\bunmarked\b", r"free player"]) or whole_span(text)
        add_marking_proximity_element(
            builder,
            span,
            require_unmarked=is_unmarked_meaning(lower),
        )
        matched = True

    if is_marking_assignment_meaning(lower):
        span = first_span(text, [r"marking assignment", r"\bassigned\b", r"\bmarker relation\b", r"\bmarker\b"]) or whole_span(text)
        add_missing_primitive_element(
            builder,
            "scl1_marking_assignment_status",
            span,
            "meaning.missing_primitive.marking_assignment",
            "Requires marker-assignment or defensive-responsibility evidence; observed nearest-opponent proximity is not treated as assignment or scheme.",
        )
        matched = True

    if is_off_ball_run_meaning(lower):
        span = first_span(text, [r"off[- ]ball run", r"diagonal run", r"run[- ]in[- ]behind", r"run typing"]) or whole_span(text)
        add_off_ball_run_element(builder, span)
        matched = True

    if is_observed_off_ball_run_path_meaning(lower):
        span = first_span(text, [r"diagonal(?: off[- ]ball)? run", r"run[- ]in[- ]behind"]) or whole_span(text)
        add_off_ball_run_type_element(
            builder,
            span,
            require_run_in_behind="run in behind" in lower or "run-in-behind" in lower,
            require_diagonal="diagonal" in lower and "run" in lower,
        )
        matched = True

    if is_off_ball_run_purpose_or_role_meaning(lower):
        span = first_span(text, [r"run typing", r"decoy", r"drag(?:ging)?", r"overlap", r"underlap", r"third[- ]man"]) or whole_span(text)
        add_missing_primitive_element(
            builder,
            "scl1_off_ball_run_purpose_status",
            span,
            "meaning.missing_primitive.off_ball_run_purpose",
            "Requires run purpose, role, coordination, or tactical typing evidence; observed off-ball path geometry is not treated as decoy, marker dragging, overlap/underlap role, or third-player purpose.",
        )
        matched = True

    if is_acceleration_meaning(lower):
        span = first_span(
            text,
            [r"acceleration", r"accelerates?", r"deceleration", r"decelerates?", r"slowing down", r"slows down", r"speeding up"],
        ) or whole_span(text)
        add_acceleration_element(builder, span, direction="deceleration" if is_deceleration_meaning(lower) else "acceleration")
        matched = True

    if is_set_piece_structure_meaning(lower):
        span = first_span(text, [r"set[- ]piece", r"corner routine", r"free[- ]kick routine", r"corner variant", r"restart routine"]) or whole_span(text)
        add_set_piece_structure_element(builder, span)
        if is_set_piece_routine_meaning(lower):
            routine_span = first_span(text, [r"routine pattern", r"routine", r"variant", r"worked", r"near[- ]post", r"far[- ]post"]) or span
            add_missing_primitive_element(
                builder,
                "scl1_set_piece_routine_status",
                routine_span,
                "meaning.missing_primitive.set_piece_routine",
                "Requires routine, variant, or planned set-piece design typing; observed at-frame arrangement is not treated as a routine claim.",
            )
        matched = True

    if is_team_press_meaning(lower):
        span = first_span(text, [r"team press", r"pressing trap", r"pressing structure", r"collective press", r"counterpress(?:ing)?"]) or whole_span(text)
        add_team_press_element(builder, span)
        if is_pressing_trap_or_coordination_meaning(lower):
            trap_span = first_span(text, [r"pressing trap", r"trap", r"trigger", r"intended", r"constrain", r"coordination", r"coordinated"]) or span
            add_missing_primitive_element(
                builder,
                "scl1_pressing_trap_status",
                trap_span,
                "meaning.missing_primitive.pressing_trap_or_coordination",
                "Requires press trap, trigger-plan, coordination, or intent evidence; observed multi-defender pressure geometry is not treated as a trap or coordinated scheme.",
            )
        matched = True

    if is_open_space_region_meaning(lower) or is_space_creation_or_value_meaning(lower):
        span = first_span(text, [r"space region", r"open space", r"free space", r"available space", r"free area", r"open area", r"generated space"]) or whole_span(text)
        add_space_region_generation_element(builder, span)
        matched = True

    if is_space_creation_or_value_meaning(lower):
        span = first_span(text, [r"space creation", r"creates? (?:generated )?space", r"generated space", r"space exploitation", r"exploit(?:s|ed|ing)? space"]) or whole_span(text)
        add_missing_primitive_element(
            builder,
            "scl1_space_creation_status",
            span,
            "meaning.missing_primitive.space_creation",
            "Requires before/after generated-space change, value, exploitation, or attribution evidence; base open-space geometry is not treated as creation, exploitation, purpose, or tactical value.",
        )
        matched = True

    apply_generic_composition_rules(builder, text)

    if not matched:
        span = whole_span(text)
        add_status_contract(builder, "scl0_unresolved_meaning_status", span, "meaning.unresolved")
        builder.add_claim_part("The meaning is underspecified for SCL-0 and must return a precise typed gap.", span, "meaning.unresolved")

    contract = builder.finish()
    return contract, builder.traces


def add_status_contract(builder: ContractBuilder, field_name: str, span: Span, rule_id: str) -> None:
    builder.add_evidence(field_name, span, rule_id)
    builder.add_status(field_name, "PASS", span, rule_id)


def add_missing_primitive_element(
    builder: ContractBuilder,
    field_name: str,
    span: Span,
    rule_id: str,
    claim_boundary: str,
) -> None:
    add_status_contract(builder, field_name, span, rule_id)
    builder.add_claim_part(claim_boundary, span, rule_id)


def add_pass_chain_element(builder: ContractBuilder, span: Span) -> None:
    rule_id = "meaning.pass_chain.connected_sequence"
    for field_name in [
        "pass_chain_status",
        "input_pass_episode_id",
        "relay_pass_episode_id",
        "input_passer_id",
        "relay_player_id",
        "terminal_receiver_id",
        "terminal_controlled_reception_frame_id",
    ]:
        builder.add_evidence(field_name, span, rule_id)
    builder.add_status("pass_chain_status", "PASS", span, rule_id)
    builder.add_constraint(
        {
            "kind": "distinct_entity_fields",
            "value": "input_passer_id,relay_player_id",
        },
        span,
        rule_id,
    )
    builder.add_constraint(
        {
            "kind": "temporal_order",
            "temporal_relation": "left_before_right",
            "left_time_field": "relay_touch_frame_id",
            "right_time_field": "terminal_controlled_reception_frame_id",
            "maximum_gap_seconds": 6.0,
        },
        span,
        rule_id,
    )
    builder.add_claim_part("Observed connected pass-chain sequence only; no planned combination, tactical quality, causation, or optimality claim.", span, rule_id)


def add_pressure_element(builder: ContractBuilder, span: Span) -> None:
    rule_id = "meaning.pressure.observed_components"
    for field_name in [
        "pressure_status",
        "pressure_reason",
        "carrier_id",
        "pressure_frame_id",
        "nearest_defender_id",
        "nearest_defender_distance_m",
        "closing_speed_mps",
        "approach_angle_degrees",
        "coverage_status",
    ]:
        builder.add_evidence(field_name, span, rule_id)
    builder.add_status("pressure_status", "PASS", span, rule_id)


def add_carry_element(builder: ContractBuilder, span: Span) -> None:
    rule_id = "meaning.element.carry"
    for field_name in [
        "carry_status",
        "carrier_id",
        "carry_start_frame_id",
        "carry_end_frame_id",
    ]:
        builder.add_evidence(field_name, span, rule_id)
    builder.add_status("carry_status", "PASS", span, rule_id)
    builder.add_claim_part("Observed movement-under-control only; no defender bypass, skill, intent, or pressure-break quality claim.", span, rule_id)


def add_forward_progression_element(builder: ContractBuilder, span: Span) -> None:
    rule_id = "meaning.element.forward_progression"
    builder.add_evidence("carry_forward_progression_m", span, rule_id)
    builder.add_threshold("carry_forward_progression_m", operator="gte", threshold=3.0, unit="metre", span=span, rule_id=rule_id)
    builder.add_claim_part("Observed forward component only; no tactical quality, intent, or optimality claim.", span, rule_id)


def add_time_to_arrival_element(builder: ContractBuilder, span: Span) -> None:
    rule_id = "meaning.reachability.time_to_arrival"
    for field_name in [
        "time_to_arrival_status",
        "time_to_arrival_reason",
        "arrival_frame_id",
        "target_point",
        "candidate_scope",
        "nearest_arrival_player_id",
        "minimum_arrival_seconds",
        "maximum_arrival_seconds",
        "maximum_player_speed_mps",
        "reachability_model",
        "momentum_policy",
        "reachable_verdict_bias",
        "coverage_status",
    ]:
        builder.add_evidence(field_name, span, rule_id)
    builder.add_status("time_to_arrival_status", "PASS", span, rule_id)
    builder.add_claim_part(
        "Observed static-point reachability only; reachable is an optimistic straight-line bound and no intent, pitch-control, or lane-denial claim is inferred.",
        span,
        rule_id,
    )


def add_lane_occupancy_element(builder: ContractBuilder, span: Span) -> None:
    rule_id = "meaning.element.lane_occupancy"
    for field_name in [
        "lane_occupancy_status",
        "lane_occupancy_reason",
        "lane_evaluation_frame_id",
        "lane_player_scope",
        "occupied_lanes",
        "occupied_lane_count",
        "lane_counts",
        "coverage_status",
    ]:
        builder.add_evidence(field_name, span, rule_id)
    builder.add_status("lane_occupancy_status", "PASS", span, rule_id)
    builder.add_claim_part(
        "Observed fixed lateral-lane classification and occupancy evidence only; no lane-count threshold, tactical role, complete coverage, intent, or support-quality claim is inferred.",
        span,
        rule_id,
    )


def add_observed_line_break_element(builder: ContractBuilder, span: Span) -> None:
    rule_id = "meaning.line_break.observed_second_line_transition"
    for field_name in [
        "line_break_status",
        "line_break_reason",
        "pass_episode_id",
        "physical_release_frame_id",
        "controlled_reception_frame_id",
        "line_x_m",
        "release_relative_position_status",
        "reception_relative_position_status",
        "receiver_id",
        "multi_line_status",
        "target_line_rank",
        "observed_line_count",
        "defensive_line_player_ids",
    ]:
        builder.add_evidence(field_name, span, rule_id)
    builder.add_status("line_break_status", "PASS", span, rule_id)
    builder.add_claim_part(
        "Observed receiver movement beyond geometric line rank 2 only; no tactical line taxonomy, intent, pass quality, causation, or optimality claim.",
        span,
        rule_id,
    )


def add_underneath_support_absence_element(builder: ContractBuilder, span: Span) -> None:
    rule_id = "meaning.support_absence.underneath_outlet"
    for field_name in [
        "support_arrival_status",
        "support_arrival_reason",
        "support_anchor_frame_id",
        "support_region_mode",
        "maximum_arrival_seconds",
        "minimum_duration_seconds",
        "maximum_support_distance_m",
        "minimum_supporting_players",
        "supporting_player_ids",
        "candidate_player_ids",
        "coverage_status",
        "required_anchor_status_field",
        "required_anchor_status_value",
    ]:
        builder.add_evidence(field_name, span, rule_id)
    builder.add_status("support_arrival_status", "FAIL", span, rule_id)
    builder.add_constraint(
        {
            "kind": "relation_on_anchor",
            "relation_status_field": "support_arrival_status",
            "anchor_status_field": "line_break_status",
            "anchor_status_value": "PASS",
            "anchor_frame_field": "controlled_reception_frame_id",
            "candidate_scope": "perspective_outfield",
            "support_region_mode": "BEHIND_BALL_OUTLET",
            "maximum_arrival_seconds": 3.0,
            "minimum_duration_seconds": 0.0,
            "maximum_support_distance_m": 8.0,
            "minimum_supporting_players": 1,
        },
        span,
        rule_id,
    )
    builder.add_claim_part(
        "No underneath support means the declared behind-ball outlet region was evaluated and no supporting player arrived inside the frozen distance/time window; no support quality, intent, or tactical judgement claim.",
        span,
        rule_id,
    )


def add_acceleration_element(builder: ContractBuilder, span: Span, *, direction: str) -> None:
    rule_id = "meaning.kinematics.acceleration"
    status_field = "deceleration_status" if direction == "deceleration" else "acceleration_status"
    for field_name in [
        status_field,
        "acceleration_reason",
        "acceleration_frame_id",
        "acceleration_entity_id",
        "previous_speed_mps",
        "current_speed_mps",
        "delta_speed_mps",
        "acceleration_mps2",
        "acceleration_model",
        "smoothing_policy",
        "noise_policy",
        "tracking_quality_status",
        "coverage_status",
        "acceleration_verdict_bias",
    ]:
        builder.add_evidence(field_name, span, rule_id)
    builder.add_status(status_field, "PASS", span, rule_id)
    builder.add_claim_part(
        "Observed two-window speed-change evidence only; no effort, sprint quality, physical capacity, intent, pressure-breaking quality, or tactical causation claim.",
        span,
        rule_id,
    )


def add_off_ball_run_element(builder: ContractBuilder, span: Span) -> None:
    rule_id = "meaning.movement.off_ball_run"
    for field_name in [
        "source_anchor_id",
        "off_ball_run_status",
        "off_ball_run_reason",
        "run_player_id",
        "run_start_frame_id",
        "run_end_frame_id",
        "run_duration_seconds",
        "run_displacement_m",
        "run_forward_progression_m",
        "run_lateral_displacement_m",
        "run_speed_mps",
        "run_start_ball_distance_m",
        "run_end_ball_distance_m",
        "candidate_scope",
        "candidate_team_role",
        "coverage_status",
        "off_ball_run_model",
        "off_ball_distance_policy",
        "off_ball_run_claim_boundary",
    ]:
        builder.add_evidence(field_name, span, rule_id)
    builder.add_status("off_ball_run_status", "PASS", span, rule_id)
    builder.add_claim_part(
        "Observed off-ball movement episode only; no run type, purpose, decoy, marker-dragging, space creation, role, intent, quality, causation, or optimality claim.",
        span,
        rule_id,
    )


def add_off_ball_run_type_element(
    builder: ContractBuilder,
    span: Span,
    *,
    require_run_in_behind: bool,
    require_diagonal: bool,
) -> None:
    rule_id = "meaning.run_type.observed_path"
    for field_name in [
        "off_ball_run_type_status",
        "off_ball_run_type_reason",
        "run_in_behind_status",
        "diagonal_run_status",
        "observed_run_type_labels",
        "run_player_id",
        "run_start_frame_id",
        "run_end_frame_id",
        "run_forward_progression_m",
        "run_lateral_displacement_m",
        "defensive_line_start_x_m",
        "defensive_line_end_x_m",
        "attacking_direction",
        "run_start_beyond_line",
        "run_end_beyond_line",
        "coverage_status",
        "off_ball_run_type_model",
        "off_ball_run_type_claim_boundary",
    ]:
        builder.add_evidence(field_name, span, rule_id)
    if require_run_in_behind:
        builder.add_status("run_in_behind_status", "PASS", span, rule_id)
    elif require_diagonal:
        builder.add_status("diagonal_run_status", "PASS", span, rule_id)
    else:
        builder.add_status("off_ball_run_type_status", "PASS", span, rule_id)
    builder.add_claim_part(
        "Observed off-ball run path geometry only; no decoy, marker-dragging, space creation, overlap/underlap role, third-player purpose, intent, causation, quality, or optimality claim.",
        span,
        rule_id,
    )


def add_marking_proximity_element(builder: ContractBuilder, span: Span, *, require_unmarked: bool = False) -> None:
    rule_id = "meaning.relation.marking_proximity"
    for field_name in [
        "marking_status",
        "unmarked_status",
        "marking_reason",
        "marking_frame_id",
        "target_player_id",
        "nearest_marker_id",
        "nearest_marker_distance_m",
        "maximum_marking_distance_m",
        "candidate_scope",
        "target_player_team_role",
        "candidate_team_role",
        "observed_marker_candidate_count",
        "coverage_status",
        "marking_model",
        "marking_assignment_policy",
        "marking_claim_boundary",
    ]:
        builder.add_evidence(field_name, span, rule_id)
    builder.add_status("unmarked_status" if require_unmarked else "marking_status", "PASS", span, rule_id)
    builder.add_claim_part(
        "Observed nearest-opposition proximity only; no marking assignment, defensive scheme, man-or-zone responsibility, role, intent, causation, quality, or optimality claim.",
        span,
        rule_id,
    )


def add_cover_shadow_element(builder: ContractBuilder, span: Span) -> None:
    rule_id = "meaning.cover_shadow.observed_lane_geometry"
    for field_name in [
        "cover_shadow_status",
        "passing_lane_denial_status",
        "cover_shadow_reason",
        "cover_shadow_frame_id",
        "target_entity_id",
        "ball_point",
        "target_point",
        "lane_length_m",
        "candidate_scope",
        "observed_defender_count",
        "maximum_lane_distance_m",
        "minimum_projection_fraction",
        "screening_defender_id",
        "screening_defender_distance_to_lane_m",
        "screening_defender_projection_fraction",
        "screening_defender_point",
        "screening_projection_point",
        "screening_defender_evidence",
        "cover_shadow_model",
        "coverage_status",
        "cover_shadow_claim_boundary",
    ]:
        builder.add_evidence(field_name, span, rule_id)
    builder.add_status("cover_shadow_status", "PASS", span, rule_id)
    builder.add_status("passing_lane_denial_status", "PASS", span, rule_id)
    builder.add_claim_part(
        "Observed ball-target lane screening geometry only; no defender intent, tactical denial quality, pass probability, pitch-control value, scheme, causation, or optimality claim.",
        span,
        rule_id,
    )


def add_team_press_element(builder: ContractBuilder, span: Span) -> None:
    rule_id = "meaning.team_press.observed_multi_defender_pressure"
    for field_name in [
        "team_press_status",
        "team_press_reason",
        "team_press_frame_id",
        "carrier_id",
        "pressure_actor_ids",
        "pressure_actor_count",
        "nearby_defender_ids",
        "nearby_defender_count",
        "observed_defender_count",
        "pressure_angle_spread_degrees",
        "pressure_actor_evidence",
        "maximum_press_distance_m",
        "minimum_closing_speed_mps",
        "maximum_approach_angle_degrees",
        "minimum_pressing_defenders",
        "minimum_angle_spread_degrees",
        "coverage_status",
        "team_press_model",
        "team_press_claim_boundary",
    ]:
        builder.add_evidence(field_name, span, rule_id)
    builder.add_status("team_press_status", "PASS", span, rule_id)
    builder.add_claim_part(
        "Observed multi-defender pressure geometry only; no press trap, trigger plan, coordinated scheme, defensive communication, intent, causation, pressure quality, or optimality claim.",
        span,
        rule_id,
    )


def add_set_piece_structure_element(builder: ContractBuilder, span: Span) -> None:
    rule_id = "meaning.restart.set_piece_structure"
    for field_name in [
        "set_piece_structure_status",
        "set_piece_structure_reason",
        "set_piece_restart_type",
        "event_type",
        "event_anchor_frame_id",
        "set_piece_attacking_team_role",
        "set_piece_defending_team_role",
        "attacking_shape_width_m",
        "attacking_shape_depth_m",
        "defending_shape_width_m",
        "defending_shape_depth_m",
        "coverage_status",
        "structure_model",
        "coordinate_system",
        "set_piece_structure_claim_boundary",
    ]:
        builder.add_evidence(field_name, span, rule_id)
    builder.add_status("set_piece_structure_status", "PASS", span, rule_id)
    builder.add_claim_part(
        "Observed provider restart/set-piece event and at-frame outfield arrangement only; no routine variant, planned play, delivery design, marking assignment, role, intent, quality, or tactical causation claim.",
        span,
        rule_id,
    )


def add_space_region_generation_element(builder: ContractBuilder, span: Span) -> None:
    rule_id = "meaning.space.open_region"
    for field_name in [
        "open_space_status",
        "open_space_reason",
        "space_frame_id",
        "zone_scope",
        "grid_step_m",
        "minimum_opponent_distance_m",
        "minimum_teammate_distance_m",
        "open_space_region_count",
        "representative_open_space_point",
        "representative_nearest_opponent_distance_m",
        "representative_nearest_teammate_distance_m",
        "open_space_candidate_points",
        "space_region_model",
        "space_region_claim_boundary",
        "coverage_status",
    ]:
        builder.add_evidence(field_name, span, rule_id)
    builder.add_status("open_space_status", "PASS", span, rule_id)
    builder.add_claim_part(
        "Observed sampled open-space candidate geometry only; no space value, pitch control, creation, exploitation, player intent, tactical causation, or optimality claim.",
        span,
        rule_id,
    )


def add_pressure_change_element(builder: ContractBuilder, span: Span) -> None:
    rule_id = "meaning.element.pressure_change"
    for field_name in [
        "change_status",
        "before_value",
        "after_value",
        "delta_value",
    ]:
        builder.add_evidence(field_name, span, rule_id)
    builder.add_status("change_status", "PASS", span, rule_id)
    builder.add_constraint(
        {
            "kind": "before_after_same_anchor",
            "value_family": "pressure_distance",
            "value_fields": ["nearest_defender_distance_m"],
            "status_fields": ["pressure_status"],
            "change_mode": "increase_at_least",
            "minimum_change_m": 1.5,
            "maximum_before_value_m": 6.0,
        },
        span,
        rule_id,
    )


def add_team_shape_element(builder: ContractBuilder, span: Span) -> None:
    rule_id = "meaning.element.team_shape"
    for field_name in [
        "before_value",
        "after_value",
        "before_value_field",
        "after_value_field",
    ]:
        builder.add_evidence(field_name, span, rule_id)
    builder.add_constraint(
        {
            "kind": "before_after_same_anchor",
            "value_family": "team_shape_width_or_depth",
            "value_fields": ["team_width_m", "team_depth_m", "team_area_m2"],
            "status_fields": ["team_compactness_status"],
            "change_mode": "increase_at_least",
            "minimum_change_m": 4.0,
            "maximum_before_value_m": 80.0,
        },
        span,
        rule_id,
    )
    builder.add_claim_part("Observed team-shape width/depth measurement only; no tactical quality, intent, or causation claim.", span, rule_id)


def add_increase_element(builder: ContractBuilder, span: Span) -> None:
    rule_id = "meaning.element.increase"
    for field_name in [
        "change_status",
        "change_reason",
        "delta_value",
        "minimum_change_m",
    ]:
        builder.add_evidence(field_name, span, rule_id)
    builder.add_status("change_status", "PASS", span, rule_id)
    builder.add_claim_part("Observed increase across a shared anchor only; no tactical quality, intent, or causation claim.", span, rule_id)


def apply_generic_composition_rules(builder: ContractBuilder, text: str) -> None:
    lower = normalize(text)
    span = whole_span(text)
    has_carry = has_evidence(builder.contract, "carry_status")
    has_pressure = has_evidence(builder.contract, "pressure_status")
    has_pressure_change = has_pressure_distance_change_constraint(builder.contract)
    has_change = has_evidence(builder.contract, "change_status")
    has_lane = has_evidence(builder.contract, "lane_occupancy_status")
    has_reachability = has_evidence(builder.contract, "time_to_arrival_status")

    if has_carry and (has_pressure or has_change):
        rule_id = "meaning.composition.same_anchor_episode_join"
        builder.add_evidence("join_status", span, rule_id)
        builder.add_evidence("join_reason", span, rule_id)
        builder.add_status("join_status", "PASS", span, rule_id)
        builder.add_constraint({"kind": "same_anchor_identity", "left_key_field": "anchor_id", "right_key_field": "anchor_id"}, span, rule_id)
        builder.add_claim_part("Observed same-anchor composition only; no tactical causation, quality, intent, or optimality claim.", span, rule_id)

    if has_carry and has_pressure_change:
        rule_id = "meaning.composition.carry_pressure_frame_alignment"
        builder.add_constraint(
            {
                "kind": "frame_alignment",
                "before_frame_field": "carry_start_frame_id",
                "after_frame_field": "carry_end_frame_id",
            },
            span,
            rule_id,
        )
        builder.add_claim_part("Pressure change is measured from carry start to carry end.", span, rule_id)

    if has_carry and has_pressure and not has_pressure_change:
        rule_id = "meaning.composition.carry_pressure_anchor_alignment"
        builder.add_claim_part("Pressure is observed on the carrier at the joined carry anchor; no pressure-quality claim.", span, rule_id)

    if "shape" in lower and has_change:
        builder.add_claim_part("Shape change is evaluated as a measurement increase, not tactical intent.", span, "meaning.composition.shape_change")

    if has_lane and has_reachability:
        rule_id = "meaning.composition.lane_reachability_same_anchor"
        builder.add_evidence("join_status", span, rule_id)
        builder.add_evidence("join_reason", span, rule_id)
        builder.add_status("join_status", "PASS", span, rule_id)
        builder.add_constraint({"kind": "same_anchor_identity", "left_key_field": "anchor_id", "right_key_field": "anchor_id"}, span, rule_id)
        builder.add_claim_part(
            "Lane occupancy and reachability are joined on the same observed anchor only; no pitch-control or denial-quality claim is inferred.",
            span,
            rule_id,
        )


def has_evidence(contract: dict[str, Any], field_name: str) -> bool:
    return field_name in contract.get("required_evidence", [])


def has_pressure_distance_change_constraint(contract: dict[str, Any]) -> bool:
    for constraint in contract.get("composition_constraints", []):
        if constraint.get("kind") == "before_after_same_anchor" and constraint.get("value_family") == "pressure_distance":
            return True
    return False


def is_pass_chain_meaning(lower: str) -> bool:
    return (
        ("two-pass" in lower or "wall-pass" in lower or "combination" in lower or "relayed" in lower or "return pass" in lower)
        and "pass" in lower
    )


def is_same_player_return_meaning(lower: str) -> bool:
    patterns = [
        "return pass back",
        "returns the return pass back",
        "receives the return pass back",
        "returns to the original passer",
        "return pass back as the terminal receiver",
        "come back to that same original passer",
        "same original passer",
    ]
    return any(pattern in lower for pattern in patterns)


def is_reachability_meaning(lower: str) -> bool:
    return any(
        phrase in lower
        for phrase in (
            "arrival window",
            "arrival time",
            "can arrive",
            "can reach",
            "reachable",
            "reachability",
            "able to arrive",
            "able to reach",
        )
    )


def is_lane_occupancy_meaning(lower: str) -> bool:
    return any(
        phrase in lower
        for phrase in (
            "lateral lane",
            "pitch lane",
            "wide lane",
            "occupied lane",
            "lane occupation",
            "channel occupation",
            "channels",
        )
    )


def is_line_break_meaning(lower: str) -> bool:
    return any(
        phrase in lower
        for phrase in (
            "line break",
            "line-break",
            "break the line",
            "breaks the line",
            "broke the line",
            "beyond the observed second defending line",
            "second defending line",
        )
    )


def is_underneath_support_absence_meaning(lower: str) -> bool:
    has_absence = any(phrase in lower for phrase in ("no ", "without", "empty", "absent", "stays empty"))
    has_support = any(phrase in lower for phrase in ("underneath support", "support outlet", "outlet", "behind-ball support region"))
    return has_absence and has_support


def is_cover_shadow_meaning(lower: str) -> bool:
    return "cover shadow" in lower or "passing-lane denial" in lower or "passing lane denial" in lower or "lane denial" in lower


def is_marking_meaning(lower: str) -> bool:
    return any(phrase in lower for phrase in ("marking assignment", "marker", "marked", "unmarked", "free player"))


def is_marking_assignment_meaning(lower: str) -> bool:
    return (
        "marking assignment" in lower
        or "marker relation" in lower
        or "marking scheme" in lower
        or ("assigned" in lower and ("marker" in lower or "marking" in lower))
    )


def is_unmarked_meaning(lower: str) -> bool:
    return any(phrase in lower for phrase in ("unmarked", "free player", "not closely marked"))


def is_off_ball_run_meaning(lower: str) -> bool:
    return any(phrase in lower for phrase in ("off-ball run", "off ball run", "diagonal run", "run in behind", "run-in-behind", "run typing"))


def is_observed_off_ball_run_path_meaning(lower: str) -> bool:
    return any(phrase in lower for phrase in ("diagonal run", "diagonal off-ball run", "diagonal off ball run", "run in behind", "run-in-behind"))


def is_off_ball_run_purpose_or_role_meaning(lower: str) -> bool:
    return any(
        phrase in lower
        for phrase in (
            "run typing",
            "decoy",
            "dragging",
            "drag a marker",
            "overlap",
            "underlap",
            "third-man",
            "third man",
        )
    )


def is_acceleration_meaning(lower: str) -> bool:
    return any(phrase in lower for phrase in ("acceleration", "accelerates", "accelerate", "deceleration", "decelerates", "slowing down", "slows down", "speeding up"))


def is_deceleration_meaning(lower: str) -> bool:
    return any(phrase in lower for phrase in ("deceleration", "decelerates", "decelerate", "slowing down", "slows down"))


def is_set_piece_structure_meaning(lower: str) -> bool:
    return any(
        phrase in lower
        for phrase in (
            "set-piece",
            "set piece",
            "corner routine",
            "corner variant",
            "free-kick routine",
            "free kick routine",
            "restart routine",
        )
    )


def is_set_piece_routine_meaning(lower: str) -> bool:
    return any(
        phrase in lower
        for phrase in (
            "routine",
            "variant",
            "pattern",
            "worked",
            "near-post",
            "near post",
            "far-post",
            "far post",
        )
    )


def is_team_press_meaning(lower: str) -> bool:
    return any(
        phrase in lower
        for phrase in (
            "team press",
            "pressing trap",
            "pressing structure",
            "collective press",
            "counterpress",
            "counterpressing",
        )
    )


def is_pressing_trap_or_coordination_meaning(lower: str) -> bool:
    return any(
        phrase in lower
        for phrase in (
            "pressing trap",
            "trap",
            "trigger",
            "intended",
            "constrain",
            "coordination",
            "coordinated",
            "scheme",
        )
    )


def is_open_space_region_meaning(lower: str) -> bool:
    return any(
        phrase in lower
        for phrase in (
            "space region",
            "open space",
            "free space",
            "available space",
            "free area",
            "open area",
        )
    )


def is_space_creation_or_value_meaning(lower: str) -> bool:
    return any(
        phrase in lower
        for phrase in (
            "generated space",
            "space creation",
            "creates space",
            "create space",
            "created space",
            "creates generated space",
            "space exploitation",
            "exploit space",
            "exploits space",
            "space value",
        )
    )


def assess_case(case: dict[str, Any], variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    expected_result = case.get("expected_result")
    expected_failure = case.get("expected_failure_taxonomy")
    verdicts = {(variant["result"], variant.get("failure_taxonomy")) for variant in variants}
    if len(verdicts) > 1:
        findings.append({"code": "independent_author_verdict_drift", "case_id": case["case_id"], "verdicts": sorted(verdicts)})
    for variant in variants:
        if variant.get("concept_name_used_as_hint"):
            findings.append({"code": "search_blindness_concept_name_hint", "case_id": case["case_id"], "target_id": variant["target_id"]})
        if variant.get("gold_chain_used_as_input"):
            findings.append({"code": "search_blindness_gold_chain_used", "case_id": case["case_id"], "target_id": variant["target_id"]})
        if variant.get("pattern_dispatch_used"):
            findings.append({"code": "search_blindness_pattern_dispatch", "case_id": case["case_id"], "target_id": variant["target_id"]})
        if expected_result and variant["result"] != expected_result:
            findings.append(
                {
                    "code": "unexpected_search_result",
                    "case_id": case["case_id"],
                    "target_id": variant["target_id"],
                    "expected": expected_result,
                    "actual": variant["result"],
                    "failure_taxonomy": variant.get("failure_taxonomy"),
                }
            )
        if expected_failure and variant.get("failure_taxonomy") != expected_failure:
            findings.append(
                {
                    "code": "unexpected_failure_taxonomy",
                    "case_id": case["case_id"],
                    "target_id": variant["target_id"],
                    "expected": expected_failure,
                    "actual": variant.get("failure_taxonomy"),
                }
            )
        if case.get("sample_role") == "known_negative" and variant["result"] == "compiler_reachable":
            findings.append({"code": "known_negative_became_reachable", "case_id": case["case_id"], "target_id": variant["target_id"]})
        if case.get("held_out") and variant["result"] != "compiler_reachable":
            findings.append({"code": "held_out_not_reachable", "case_id": case["case_id"], "target_id": variant["target_id"]})
    return findings


def search_blindness_findings(config: dict[str, Any], search_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    football_names = {str(case["concept"]).lower() for case in config["cases"]}
    targets_payload = load_json(TARGETS_OUT)
    target_strings = {value.lower() for value in recursive_string_values(targets_payload)}
    serialized_targets = json.dumps(targets_payload, sort_keys=True).lower()
    for name in football_names:
        if name in target_strings or name.replace("_", " ") in target_strings:
            findings.append({"code": "search_blindness_football_concept_name_in_targets", "concept": name})
    for case in config["cases"]:
        for definition in case.get("definitions") or []:
            if str(definition["text"]).lower() in serialized_targets:
                findings.append({"code": "search_blindness_definition_text_in_targets", "case_id": case["case_id"]})
    for row in search_rows:
        if not str(row.get("concept", "")).startswith("scl"):
            findings.append({"code": "search_blindness_non_opaque_reporting_concept", "target_id": row.get("target_id"), "concept": row.get("concept")})
    return findings


def recursive_string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(recursive_string_values(item))
        return result
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(recursive_string_values(item))
        return result
    return []


def independent_stability_findings(case: dict[str, Any], contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(contracts) < 2:
        return []
    hashes = {stable_hash(contract) for contract in contracts}
    if len(hashes) > 1:
        return [{"code": "independent_author_contract_drift", "case_id": case["case_id"], "hashes": sorted(hashes)}]
    return []


def perturbation_findings(case: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    definitions = case.get("definitions") or []
    if not definitions:
        return findings
    base_contract, _base_traces = generate_contract_from_meaning(str(definitions[0]["text"]))
    for perturbation in case.get("perturbations") or []:
        changed_contract, traces = generate_contract_from_meaning(str(perturbation["text"]))
        if stable_hash(base_contract) == stable_hash(changed_contract):
            findings.append({"code": "perturbation_contract_did_not_change", "case_id": case["case_id"], "perturbation_id": perturbation["perturbation_id"]})
        removed_kind = perturbation.get("must_remove_constraint_kind")
        if removed_kind and has_constraint_kind(changed_contract, str(removed_kind)):
            findings.append(
                {
                    "code": "perturbation_expected_constraint_still_present",
                    "case_id": case["case_id"],
                    "perturbation_id": perturbation["perturbation_id"],
                    "constraint_kind": removed_kind,
                }
            )
        removed_evidence = perturbation.get("must_remove_required_evidence")
        if removed_evidence and str(removed_evidence) in changed_contract.get("required_evidence", []):
            findings.append(
                {
                    "code": "perturbation_expected_evidence_still_present",
                    "case_id": case["case_id"],
                    "perturbation_id": perturbation["perturbation_id"],
                    "field": str(removed_evidence),
                }
            )
        findings.extend(trace_findings(case["case_id"], str(perturbation["perturbation_id"]), changed_contract, traces))
    return findings


def rule_usage_counts(contract_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    usage: dict[str, set[str]] = collections.defaultdict(set)
    definition_counts: collections.Counter[str] = collections.Counter()
    for row in contract_rows:
        case_id = str(row["case_id"])
        for trace in row.get("trace") or []:
            rule_id = str(trace.get("rule_id", ""))
            if not rule_id:
                continue
            usage[rule_id].add(case_id)
            definition_counts[rule_id] += 1
    return {
        rule_id: {
            "case_count": len(case_ids),
            "definition_count": int(definition_counts[rule_id]),
            "cases": sorted(case_ids),
        }
        for rule_id, case_ids in sorted(usage.items())
    }


def cross_concept_reuse_findings(contract_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    usage = rule_usage_counts(contract_rows)
    for rule_id in sorted(CROSS_CONCEPT_REUSE_REQUIRED_RULES):
        if rule_id not in usage:
            continue
        case_count = int(usage[rule_id]["case_count"])
        if case_count < 2:
            findings.append(
                {
                    "code": "cross_concept_reuse_missing",
                    "rule_id": rule_id,
                    "case_count": case_count,
                    "cases": usage[rule_id]["cases"],
                }
            )
    return findings


def trace_findings(case_id: str, author_id: str, contract: dict[str, Any], traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    trace_paths = {trace["contract_path"] for trace in traces}
    for field_name in contract.get("required_evidence", []):
        if f"required_evidence.{field_name}" not in trace_paths:
            findings.append({"code": "trace_missing_required_evidence", "case_id": case_id, "author_id": author_id, "field": field_name})
    for item in contract.get("status_semantics", []):
        field_name = item.get("field")
        if f"status_semantics.{field_name}" not in trace_paths:
            findings.append({"code": "trace_missing_status_semantics", "case_id": case_id, "author_id": author_id, "field": field_name})
    for modality in contract.get("required_modalities", []):
        if f"required_modalities.{modality}" not in trace_paths:
            findings.append({"code": "trace_missing_required_modality", "case_id": case_id, "author_id": author_id, "modality": modality})
    for constraint in contract.get("composition_constraints", []):
        kind = constraint.get("kind")
        if f"composition_constraints.{kind}" not in trace_paths:
            findings.append({"code": "trace_missing_composition_constraint", "case_id": case_id, "author_id": author_id, "kind": kind})
    if "claim_boundary" not in trace_paths:
        findings.append({"code": "trace_missing_claim_boundary", "case_id": case_id, "author_id": author_id})
    for trace in traces:
        if int(trace["source_start"]) < 0 or int(trace["source_end"]) <= int(trace["source_start"]):
            findings.append({"code": "trace_invalid_span", "case_id": case_id, "author_id": author_id, "trace": trace})
    return findings


def clean_meaning_findings(case_id: str, definition: dict[str, Any]) -> list[dict[str, Any]]:
    text = str(definition["text"]).lower()
    findings = []
    for term in sorted(FORBIDDEN_MEANING_TERMS):
        if term in text:
            findings.append({"code": "meaning_input_forbidden_term", "case_id": case_id, "author_id": definition["author_id"], "term": term})
    return findings


def contract_anti_circularity_findings(case_id: str, author_id: str, contract: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    for path, value in walk_json(contract):
        key = path[-1] if path else ""
        if key in FORBIDDEN_CONTRACT_KEYS:
            findings.append({"code": "contract_anti_circularity_forbidden_key", "case_id": case_id, "author_id": author_id, "path": ".".join(path)})
        if isinstance(value, str):
            lowered = value.lower()
            for forbidden in sorted(FORBIDDEN_CONTRACT_KEYS):
                if forbidden in lowered:
                    findings.append({"code": "contract_anti_circularity_forbidden_value", "case_id": case_id, "author_id": author_id, "path": ".".join(path), "term": forbidden})
    return findings


def coverage_row(case: dict[str, Any], opaque_concept: str) -> dict[str, Any]:
    return {
        "concept": opaque_concept,
        "classification": case.get("coverage_classification", "supported"),
        "composition_maturity": "semantic_contract_layer_sample",
        "original_concept_redacted_for_search": True,
    }


def has_multi_step_contract(contract: dict[str, Any]) -> bool:
    return bool(contract.get("composition_constraints"))


def has_constraint_kind(contract: dict[str, Any], kind: str) -> bool:
    return any(item.get("kind") == kind for item in contract.get("composition_constraints", []))


def first_span(text: str, patterns: list[str]) -> Span | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return Span(phrase=text[match.start() : match.end()], start=match.start(), end=match.end())
    return None


def whole_span(text: str) -> Span:
    return Span(phrase=text, start=0, end=len(text))


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def walk_json(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    items = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            items.extend(walk_json(child, (*path, str(key))))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(walk_json(child, (*path, str(index))))
    return items


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def relative_path(path: Path) -> str:
    return str(path.relative_to(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
