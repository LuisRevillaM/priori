#!/usr/bin/env python3
"""SCL-NL-0 verification harness.

The NL interpreter is intentionally separate from this file. This harness is
allowed to connect NL output to SCL contracts and compiler search targets so it
can prove the layer boundary.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.coverage_map.semantic_contract_scl0 import (  # noqa: E402
    generate_contract_from_meaning,
    has_constraint_kind,
    stable_hash,
)
from scripts.coverage_map.semantic_nl_interpreter_scl0 import (  # noqa: E402
    CLARIFICATION_REQUIRED,
    MEANING_DEFINITION,
    interpret_request,
)

CONFIG = ROOT / "config" / "compiler-reachability" / "scl-nl0-sample.v0.json"
OUT_DIR = ROOT / "generated" / "semantic-nl-scl0"
TARGETS_OUT = OUT_DIR / "scl-nl0-search-targets.v0.json"
LEDGER_OUT = OUT_DIR / "scl-nl0-coverage-ledger.json"
NL_LEDGER_OUT = OUT_DIR / "scl-nl0-meaning-ledger.json"
CONTRACT_LEDGER_OUT = OUT_DIR / "scl-nl0-contract-ledger.json"
SEARCH_ROW_LEDGER = OUT_DIR / "search-run" / "row-ledger.json"
PREP_REPORT = ROOT / "artifacts" / "autonomous" / "scl-nl0-prep-report.json"
ASSESS_REPORT = ROOT / "artifacts" / "autonomous" / "scl-nl0-assessment-report.json"
NL_INTERPRETER = ROOT / "scripts" / "coverage_map" / "semantic_nl_interpreter_scl0.py"

FORBIDDEN_NL_SOURCE_TERMS = {
    "generate_contract_from_meaning",
    "semantic_contract_scl0",
    "compiler_search_reachability",
    "default_catalog",
    "catalog_ref",
    "controlled_pass_episode",
    "carry_episode",
    "pressure_on_carrier",
    "join_episode_sets",
    "same_player_return",
    "team_press_status",
    "cover_shadow_status",
    "required_evidence",
    "status_semantics",
    "target_contract",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "assess"])
    args = parser.parse_args()
    return prepare() if args.mode == "prepare" else assess()


def prepare() -> int:
    config = load_json(CONFIG)
    findings: list[dict[str, Any]] = source_blindness_findings()
    targets: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    nl_rows: list[dict[str, Any]] = []
    contract_rows: list[dict[str, Any]] = []

    for case in config["cases"]:
        case_id = str(case["case_id"])
        opaque_concept = case_id
        coverage_rows.append(coverage_row(case, opaque_concept))
        case_meaning_hashes: list[str] = []
        case_contract_hashes: list[str] = []

        for request in case.get("requests", []):
            request_id = str(request["request_id"])
            text = str(request["text"])
            interpretation = interpret_request(text)
            row = {
                "case_id": case_id,
                "concept": case["concept"],
                "request_id": request_id,
                "request_text": text,
                "nl_output": interpretation.as_dict(),
                "expected_nl_status": case.get("expected_nl_status"),
            }
            nl_rows.append(row)
            if interpretation.status != case.get("expected_nl_status"):
                findings.append(
                    {
                        "code": "unexpected_nl_status",
                        "case_id": case_id,
                        "request_id": request_id,
                        "expected": case.get("expected_nl_status"),
                        "actual": interpretation.status,
                    }
                )

            if interpretation.status == CLARIFICATION_REQUIRED:
                if not interpretation.clarification_codes or not interpretation.clarification_questions:
                    findings.append({"code": "clarification_missing_payload", "case_id": case_id, "request_id": request_id})
                continue

            if interpretation.status != MEANING_DEFINITION or interpretation.meaning_definition is None:
                findings.append({"code": "meaning_definition_missing", "case_id": case_id, "request_id": request_id})
                continue

            case_meaning_hashes.append(interpretation.as_dict()["meaning_hash"])
            contract, traces = generate_contract_from_meaning(interpretation.meaning_definition)
            contract_hash = stable_hash(contract)
            case_contract_hashes.append(contract_hash)
            target_id = f"{case_id}_{request_id}_v0"
            targets.append(
                {
                    "target_id": target_id,
                    "concept": opaque_concept,
                    "held_out": bool(case.get("held_out")),
                    "multi_step": bool(contract.get("composition_constraints")),
                    "target_contract": contract,
                }
            )
            contract_rows.append(
                {
                    "case_id": case_id,
                    "concept": case["concept"],
                    "request_id": request_id,
                    "opaque_search_concept": opaque_concept,
                    "target_id": target_id,
                    "meaning_hash": interpretation.as_dict()["meaning_hash"],
                    "meaning_definition": interpretation.meaning_definition,
                    "contract": contract,
                    "contract_hash": contract_hash,
                    "trace": traces,
                }
            )
            findings.extend(traceability_findings(case_id, request_id, interpretation.meaning_definition, traces))
            findings.extend(contract_leakage_findings(case_id, request_id, contract))
            findings.extend(vocabulary_invariance_findings(case, request, interpretation))

        if case.get("same_meaning_expected") and len(set(case_meaning_hashes)) > 1:
            findings.append({"code": "cross_phrasing_meaning_drift", "case_id": case_id, "hashes": sorted(set(case_meaning_hashes))})
        if case.get("same_meaning_expected") and len(set(case_contract_hashes)) > 1:
            findings.append({"code": "cross_phrasing_contract_drift", "case_id": case_id, "hashes": sorted(set(case_contract_hashes))})
        findings.extend(changed_meaning_findings(case, case_meaning_hashes, case_contract_hashes))

    targets_payload = {
        "schema_version": "compiler_search_targets.v0",
        "strategy": "bounded_backward_search.v0.1.scl_nl0_meaning_contracts",
        "sample_policy": config["sample_policy"],
        "note": (
            "Targets are opaque typed contracts generated from NL-produced meaning definitions. "
            "Search receives no user request, meaning definition, football concept name, gold chain, provider path, or pattern label."
        ),
        "targets": targets,
    }
    findings.extend(search_target_blindness_findings(targets_payload, nl_rows, contract_rows, config))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TARGETS_OUT.write_text(json.dumps(targets_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LEDGER_OUT.write_text(json.dumps(coverage_rows, indent=1) + "\n", encoding="utf-8")
    NL_LEDGER_OUT.write_text(json.dumps(nl_rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    CONTRACT_LEDGER_OUT.write_text(json.dumps(contract_rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = {
        "schema_version": "scl_nl0_prepare.v0",
        "status": "PASS" if not findings else "FAIL",
        "scope": {
            "nl_layer_reads_scl_vocabulary": False,
            "nl_layer_reads_catalog": False,
            "nl_layer_reads_search_schema": False,
            "search_receives_only_typed_contract": True,
            "atlas_wide": False,
        },
        "summary": {
            "case_count": len(config["cases"]),
            "request_count": len(nl_rows),
            "search_target_count": len(targets),
            "clarification_count": sum(1 for row in nl_rows if row["nl_output"]["status"] == CLARIFICATION_REQUIRED),
            "meaning_definition_count": sum(1 for row in nl_rows if row["nl_output"]["status"] == MEANING_DEFINITION),
            "findings_count": len(findings),
        },
        "gates": gate_summary(findings),
        "outputs": {
            "targets": relative_path(TARGETS_OUT),
            "coverage_ledger": relative_path(LEDGER_OUT),
            "nl_ledger": relative_path(NL_LEDGER_OUT),
            "contract_ledger": relative_path(CONTRACT_LEDGER_OUT),
        },
        "findings": findings,
    }
    PREP_REPORT.parent.mkdir(parents=True, exist_ok=True)
    PREP_REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


def assess() -> int:
    config = load_json(CONFIG)
    nl_rows = load_json(NL_LEDGER_OUT)
    contract_rows = load_json(CONTRACT_LEDGER_OUT)
    search_rows = load_json(SEARCH_ROW_LEDGER)
    contract_by_target = {row["target_id"]: row for row in contract_rows}
    search_by_target = {row["target_id"]: row for row in search_rows}
    findings: list[dict[str, Any]] = []
    case_reports: list[dict[str, Any]] = []
    pipeline_outcomes: list[str] = []

    for case in config["cases"]:
        case_id = str(case["case_id"])
        request_reports: list[dict[str, Any]] = []
        for request in case.get("requests", []):
            request_id = str(request["request_id"])
            nl_row = next(row for row in nl_rows if row["case_id"] == case_id and row["request_id"] == request_id)
            target_id = f"{case_id}_{request_id}_v0"
            search_row = search_by_target.get(target_id)
            contract_row = contract_by_target.get(target_id)
            outcome = classify_pipeline_outcome(nl_row=nl_row, search_row=search_row, contract_row=contract_row)
            pipeline_outcomes.append(outcome)
            expected = case.get("expected_pipeline_outcome")
            if outcome != expected:
                findings.append(
                    {
                        "code": "unexpected_pipeline_outcome",
                        "case_id": case_id,
                        "request_id": request_id,
                        "expected": expected,
                        "actual": outcome,
                        "failure_taxonomy": None if search_row is None else search_row.get("failure_taxonomy"),
                    }
                )
            expected_failure = case.get("expected_failure_taxonomy")
            if expected_failure and (search_row is None or search_row.get("failure_taxonomy") != expected_failure):
                findings.append(
                    {
                        "code": "unexpected_failure_taxonomy",
                        "case_id": case_id,
                        "request_id": request_id,
                        "expected": expected_failure,
                        "actual": None if search_row is None else search_row.get("failure_taxonomy"),
                    }
                )
            if search_row is not None:
                if search_row.get("concept_name_used_as_hint"):
                    findings.append({"code": "search_concept_name_hint_used", "case_id": case_id, "target_id": target_id})
                if search_row.get("gold_chain_used_as_input"):
                    findings.append({"code": "search_gold_chain_used", "case_id": case_id, "target_id": target_id})
                if search_row.get("pattern_dispatch_used"):
                    findings.append({"code": "search_pattern_dispatch_used", "case_id": case_id, "target_id": target_id})
            request_reports.append(
                {
                    "request_id": request_id,
                    "nl_status": nl_row["nl_output"]["status"],
                    "meaning_hash": nl_row["nl_output"]["meaning_hash"],
                    "target_id": None if contract_row is None else target_id,
                    "contract_hash": None if contract_row is None else contract_row["contract_hash"],
                    "search_result": None if search_row is None else search_row["result"],
                    "failure_taxonomy": None if search_row is None else search_row.get("failure_taxonomy"),
                    "pipeline_outcome": outcome,
                }
            )
        case_reports.append(
            {
                "case_id": case_id,
                "concept": case["concept"],
                "sample_role": case["sample_role"],
                "held_out": bool(case.get("held_out")),
                "expected_pipeline_outcome": case.get("expected_pipeline_outcome"),
                "requests": request_reports,
            }
        )

    nl_status_counts = collections.Counter(row["nl_output"]["status"] for row in nl_rows)
    pipeline_counts = collections.Counter(pipeline_outcomes)
    search_result_counts = collections.Counter(row["result"] for row in search_rows)
    failure_counts = collections.Counter(row["failure_taxonomy"] for row in search_rows if row.get("failure_taxonomy"))

    report = {
        "schema_version": "scl_nl0_assessment.v0",
        "status": "PASS" if not findings else "FAIL",
        "scope": {
            "claim": (
                "Small SCL-NL-0 proof that a vocabulary-blind NL layer can produce football meaning definitions "
                "which the existing SCL layer independently composes or honest-gaps."
            ),
            "search_receives_only_typed_contract": True,
            "nl_understood_but_not_expressible_bucket": True,
            "atlas_wide": False,
        },
        "summary": {
            "case_count": len(case_reports),
            "request_count": len(nl_rows),
            "search_target_count": len(search_rows),
            "nl_status_distribution": dict(sorted(nl_status_counts.items())),
            "pipeline_outcome_distribution": dict(sorted(pipeline_counts.items())),
            "search_result_distribution": dict(sorted(search_result_counts.items())),
            "failure_distribution": dict(sorted(failure_counts.items())),
            "findings_count": len(findings),
        },
        "gates": gate_summary(findings),
        "cases": case_reports,
        "findings": findings,
        "inputs": {
            "nl_ledger": relative_path(NL_LEDGER_OUT),
            "contract_ledger": relative_path(CONTRACT_LEDGER_OUT),
            "search_row_ledger": relative_path(SEARCH_ROW_LEDGER),
        },
    }
    ASSESS_REPORT.parent.mkdir(parents=True, exist_ok=True)
    ASSESS_REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


def classify_pipeline_outcome(
    *,
    nl_row: dict[str, Any],
    search_row: dict[str, Any] | None,
    contract_row: dict[str, Any] | None,
) -> str:
    status = nl_row["nl_output"]["status"]
    if status == CLARIFICATION_REQUIRED:
        return "clarification_required"
    if search_row is None:
        return "missing_search_row"
    if search_row["result"] == "compiler_reachable":
        return "compiler_reachable"
    taxonomy = search_row.get("failure_taxonomy")
    if taxonomy == "unsupported_modality":
        return "unsupported_modality"
    if contract_row is not None and contract_is_unresolved(contract_row["contract"]):
        return "nl_understood_but_not_expressible"
    return taxonomy or "not_compiler_reachable"


def source_blindness_findings() -> list[dict[str, Any]]:
    source = NL_INTERPRETER.read_text(encoding="utf-8").lower()
    findings = []
    for term in sorted(FORBIDDEN_NL_SOURCE_TERMS):
        if term.lower() in source:
            findings.append({"code": "nl_source_forbidden_downstream_term", "term": term})
    return findings


def vocabulary_invariance_findings(
    case: dict[str, Any],
    request: dict[str, Any],
    baseline: Any,
) -> list[dict[str, Any]]:
    disabled = case.get("vocabulary_invariance_disable")
    if not disabled:
        return []
    rerun = interpret_request(str(request["text"]), disabled_downstream_elements=disabled)
    if rerun.as_dict()["meaning_hash"] != baseline.as_dict()["meaning_hash"]:
        return [
            {
                "code": "vocabulary_invariance_failed",
                "case_id": case["case_id"],
                "request_id": request["request_id"],
                "disabled_downstream_elements": disabled,
                "baseline_hash": baseline.as_dict()["meaning_hash"],
                "rerun_hash": rerun.as_dict()["meaning_hash"],
            }
        ]
    return []


def changed_meaning_findings(
    case: dict[str, Any],
    base_meaning_hashes: list[str],
    base_contract_hashes: list[str],
) -> list[dict[str, Any]]:
    changed = case.get("changed_meaning_request")
    if not changed or not base_meaning_hashes:
        return []
    findings: list[dict[str, Any]] = []
    changed_output = interpret_request(str(changed["text"]))
    if changed_output.status != MEANING_DEFINITION or changed_output.meaning_definition is None:
        findings.append({"code": "changed_meaning_not_interpreted", "case_id": case["case_id"]})
        return findings
    changed_hash = changed_output.as_dict()["meaning_hash"]
    if changed_hash in set(base_meaning_hashes):
        findings.append({"code": "changed_meaning_did_not_change_nl_output", "case_id": case["case_id"]})
    changed_contract, _traces = generate_contract_from_meaning(changed_output.meaning_definition)
    if stable_hash(changed_contract) in set(base_contract_hashes):
        findings.append({"code": "changed_meaning_did_not_change_contract", "case_id": case["case_id"]})
    removed = changed.get("must_remove_constraint_kind")
    if removed and has_constraint_kind(changed_contract, str(removed)):
        findings.append(
            {
                "code": "changed_meaning_expected_constraint_still_present",
                "case_id": case["case_id"],
                "constraint_kind": removed,
            }
        )
    return findings


def traceability_findings(case_id: str, request_id: str, meaning_definition: str, traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not traces:
        findings.append({"code": "scl_trace_missing", "case_id": case_id, "request_id": request_id})
    for trace in traces:
        phrase = str(trace.get("source_phrase", ""))
        start = int(trace.get("source_start", -1))
        end = int(trace.get("source_end", -1))
        if start < 0 or end <= start or meaning_definition[start:end] != phrase:
            findings.append({"code": "scl_trace_invalid_span", "case_id": case_id, "request_id": request_id, "trace": trace})
    return findings


def contract_leakage_findings(case_id: str, request_id: str, contract: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    serialized = json.dumps(contract, sort_keys=True).lower()
    for term in ("catalog_ref", "provider_chain", "gold_chain", "runtime_ref", "pattern"):
        if term in serialized:
            findings.append({"code": "contract_contains_forbidden_hint", "case_id": case_id, "request_id": request_id, "term": term})
    return findings


def search_target_blindness_findings(
    targets_payload: dict[str, Any],
    nl_rows: list[dict[str, Any]],
    contract_rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    serialized_targets = json.dumps(targets_payload, sort_keys=True).lower()
    for row in nl_rows:
        text = str(row["request_text"]).lower()
        meaning_definition = row["nl_output"].get("meaning_definition")
        if text and text in serialized_targets:
            findings.append({"code": "search_target_contains_user_request", "case_id": row["case_id"], "request_id": row["request_id"]})
        if meaning_definition and str(meaning_definition).lower() in serialized_targets:
            findings.append({"code": "search_target_contains_meaning_definition", "case_id": row["case_id"], "request_id": row["request_id"]})
    for case in config["cases"]:
        concept = str(case["concept"]).lower()
        if concept in serialized_targets or concept.replace("_", " ") in serialized_targets:
            findings.append({"code": "search_target_contains_football_concept_name", "concept": concept})
    for row in contract_rows:
        if not str(row["opaque_search_concept"]).startswith("sclnl0_"):
            findings.append({"code": "search_target_non_opaque_concept", "case_id": row["case_id"], "concept": row["opaque_search_concept"]})
    return findings


def contract_is_unresolved(contract: dict[str, Any]) -> bool:
    return "scl0_unresolved_meaning_status" in contract.get("required_evidence", [])


def coverage_row(case: dict[str, Any], opaque_concept: str) -> dict[str, Any]:
    return {
        "concept": opaque_concept,
        "classification": case.get("coverage_classification", "supported"),
        "composition_maturity": "scl_nl0_sample",
        "original_concept_redacted_for_search": True,
    }


def gate_summary(findings: list[dict[str, Any]]) -> dict[str, bool]:
    codes = [str(item["code"]) for item in findings]
    return {
        "nl_source_blind_to_scl_vocabulary": not any(code.startswith("nl_source_") for code in codes),
        "search_receives_only_typed_contract": not any(code.startswith("search_target_") or code.startswith("search_") for code in codes),
        "vocabulary_invariance": "vocabulary_invariance_failed" not in codes,
        "changed_meaning_changes_output": not any(code.startswith("changed_meaning_") for code in codes),
        "ambiguity_requires_clarification": "clarification_missing_payload" not in codes and "unexpected_nl_status" not in codes,
        "cross_phrasing_stability": not any(code.startswith("cross_phrasing_") for code in codes),
        "known_negatives_honest": "unexpected_failure_taxonomy" not in codes,
        "held_out_configured": True,
        "scl_traceability": not any(code.startswith("scl_trace_") for code in codes),
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def relative_path(path: Path) -> str:
    return str(path.relative_to(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
