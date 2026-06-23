"""Verify M2A-S1C high-bypass completed-pass result emission."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from tqe.runtime.controlled_pass import evaluate_controlled_passes
from tqe.runtime.high_bypass_pass import (
    CLASSIFICATION,
    REQUIRED_EVIDENCE_ALIASES,
    HighBypassConfig,
    emit_high_bypass_completed_pass_results,
)
from tqe.runtime.pass_bypass import evaluate_pass_bypass_measurements


S0_CONTRACT_SHA256 = "ffa4c63bd127eb9ba232e6666bafc8e96c7a371f347d8fe6cac05d7466119ef7"
S1A_ARTIFACT_SHA256 = "fff166b583eb55fb349bdace6283ad6bf72f035d96bf684e21f32209889e8ea4"
S1B_ARTIFACT_SHA256 = "edfbeae2957622eca06cf89a4e4a1a0ceb89395a826964483c7c511e9d484b6c"
EXPECTED_PASS_EPISODE_IDS = [
    "J03WOY:firstHalf:home:188:DFL-OBJ-002G5J:DFL-OBJ-002FXT",
    "J03WOY:firstHalf:away:227:DFL-OBJ-00286X:DFL-OBJ-00019R",
    "J03WOY:firstHalf:home:331:DFL-OBJ-0028FW:DFL-OBJ-002FXT",
    "J03WOY:secondHalf:home:102:DFL-OBJ-002GM9:DFL-OBJ-002FXT",
    "J03WOY:secondHalf:away:172:DFL-OBJ-002FZB:DFL-OBJ-0028IJ",
    "J03WOY:secondHalf:home:356:DFL-OBJ-002GMO:DFL-OBJ-0026RH",
    "J03WOY:secondHalf:away:385:DFL-OBJ-0025BB:DFL-OBJ-0001IG",
]


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify(*, out_json: Path, out_md: Path) -> dict[str, Any]:
    controlled = evaluate_controlled_passes(match_ids=("J03WOY",), periods=("firstHalf", "secondHalf"))
    bypass = evaluate_pass_bypass_measurements(
        controlled_passes=controlled,
        match_ids=("J03WOY",),
        periods=("firstHalf", "secondHalf"),
    )
    output = emit_high_bypass_completed_pass_results(
        controlled_passes=controlled,
        bypass_measurements=bypass,
        match_ids=("J03WOY",),
        periods=("firstHalf", "secondHalf"),
    )
    repeat = emit_high_bypass_completed_pass_results(
        controlled_passes=controlled,
        bypass_measurements=bypass,
        match_ids=("J03WOY",),
        periods=("firstHalf", "secondHalf"),
    )
    strict = emit_high_bypass_completed_pass_results(
        controlled_passes=controlled,
        bypass_measurements=bypass,
        match_ids=("J03WOY",),
        periods=("firstHalf", "secondHalf"),
        config=HighBypassConfig(minimum_bypassed_opponents=8),
    )
    output_dict = asdict(output)
    results = output_dict["results"]
    traces = output_dict["predicate_traces"]
    result_ids = [str(item["result_id"]) for item in results]
    pass_episode_ids = [str(item["pass_episode_id"]) for item in results]
    trace_result_ids = [str(item.get("source_evidence", {}).get("result_id")) for item in traces]
    evidence_rows = [dict(item.get("requested_evidence") or {}) for item in results]
    checks = [
        check(
            "runtime_schema",
            output.schema_version == "m2a.high_bypass_completed_pass.v1",
            output.schema_version,
        ),
        check(
            "real_results_emitted",
            len(results) == 7,
            f"{len(results)} results",
        ),
        check(
            "expected_positive_pass_episodes",
            pass_episode_ids == EXPECTED_PASS_EPISODE_IDS,
            pass_episode_ids,
        ),
        check(
            "query_result_shape",
            all(
                {"result_id", "classification", "match_id", "period", "anchor_frame_id", "requested_evidence"}.issubset(
                    item.keys()
                )
                for item in results
            ),
            "all rows expose QueryResult-shaped fields",
        ),
        check(
            "classification_label",
            {item["classification"] for item in results} == {CLASSIFICATION},
            sorted({item["classification"] for item in results}),
        ),
        check(
            "requested_evidence_complete",
            output.summary["requested_evidence_failure_count"] == 0
            and all(required_evidence_present(evidence) for evidence in evidence_rows),
            f"failure_count={output.summary['requested_evidence_failure_count']}",
        ),
        check(
            "predicate_traces_attached",
            len(traces) == len(results) * 3 and set(trace_result_ids) == set(result_ids),
            f"results={len(results)} traces={len(traces)}",
        ),
        check(
            "thresholds_applied_in_recipe_layer",
            all(
                float(item["requested_evidence"]["forward_progression_m"]) >= 8.0
                and int(item["requested_evidence"]["opponents_bypassed_count"]) >= 5
                for item in results
            ),
            "all emitted rows satisfy S1C thresholds",
        ),
        check(
            "opponent_denominator_complete_for_positive_results",
            all(
                len(item["requested_evidence"]["expected_active_opposition_outfield_ids"]) == 10
                and len(item["requested_evidence"]["evaluated_opponent_ids"]) == 10
                and not item["requested_evidence"]["missing_active_opponent_ids"]
                for item in results
            ),
            "all positives have 10 expected/evaluated defending outfield players",
        ),
        check(
            "deterministic_result_identity",
            result_ids == [str(item["result_id"]) for item in repeat.results],
            result_ids,
        ),
        check(
            "threshold_mutation_changes_inclusion",
            len(strict.results) == 0,
            f"minimum_bypassed_opponents=8 produced {len(strict.results)} results",
        ),
        check(
            "scope_boundaries_preserved",
            output.accepted_scope["match_ids"] == ["J03WOY"]
            and "blocked" in output.accepted_scope["all_corpus_execution"]
            and "blocked" in output.accepted_scope["hermes_exposure"],
            output.accepted_scope,
        ),
    ]
    decision = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    report = {
        "schema_version": "m2a.s1c.high_bypass_verify.v1",
        "decision": decision,
        "upstream_artifact_hashes": {
            "s0_contract_sha256": S0_CONTRACT_SHA256,
            "s1a_artifact_sha256": S1A_ARTIFACT_SHA256,
            "s1b_artifact_sha256": S1B_ARTIFACT_SHA256,
        },
        "checks": checks,
        "runtime_summary": output.summary,
        "accepted_scope": output.accepted_scope,
        "artifact_hash": stable_hash(
            {
                "results": results,
                "predicate_traces": traces,
                "config": output.config,
            }
        ),
        "sample_results": results[:10],
        "sample_non_matches": output.non_match_examples[:20],
        "output": output_dict,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(report, out_md)
    return report


def check(check_id: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def required_evidence_present(evidence: dict[str, Any]) -> bool:
    for alias in REQUIRED_EVIDENCE_ALIASES:
        if alias not in evidence:
            return False
        if evidence[alias] is None and alias != "unknown_reason":
            return False
    return True


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# M2A-S1C High-Bypass Completed Pass Verification",
        "",
        f"Decision: **{report['decision']}**",
        "",
        f"Runtime artifact hash: `{report['artifact_hash']}`",
        "",
        "## Upstream Hashes",
        "",
        f"- S0 contract: `{report['upstream_artifact_hashes']['s0_contract_sha256']}`",
        f"- S1A controlled-pass artifact: `{report['upstream_artifact_hashes']['s1a_artifact_sha256']}`",
        f"- S1B pass-bypass artifact: `{report['upstream_artifact_hashes']['s1b_artifact_sha256']}`",
        "",
        "## Checks",
        "",
    ]
    for item in report["checks"]:
        lines.append(f"- `{item['check_id']}`: **{item['status']}** - {item['detail']}")
    lines.extend(
        [
            "",
            "## Runtime Summary",
            "",
            f"- Result count: {report['runtime_summary']['result_count']}",
            f"- Classification counts: `{report['runtime_summary']['classification_counts']}`",
            f"- Non-match reason counts: `{report['runtime_summary']['non_match_reason_counts']}`",
            f"- Requested evidence failure count: {report['runtime_summary']['requested_evidence_failure_count']}",
            f"- Predicate trace count: {report['runtime_summary']['trace_count']}",
            "",
            "## Boundary",
            "",
            "- This emits `high_bypass_completed_pass_v1` QueryResult-shaped rows for the J03WOY accepted scope only.",
            "- It does not expose M2A to Hermes.",
            "- It does not run the all-corpus path.",
            "- Replay UI integration and human visual review remain future slices.",
            "",
            "## Sample Results",
            "",
        ]
    )
    for item in report["sample_results"][:5]:
        evidence = item["requested_evidence"]
        lines.append(
            "- "
            f"{item['result_id']} {item['match_id']} {item['period']} "
            f"row={evidence['event_row_index']} "
            f"{evidence['passer_id']}->{evidence['receiver_id']} "
            f"progression={evidence['forward_progression_m']}m "
            f"bypassed={evidence['opponents_bypassed_count']}"
        )
    if not report["sample_results"]:
        lines.append("- none")
    lines.extend(["", "## Sample Non-Matches", ""])
    for item in report["sample_non_matches"][:5]:
        lines.append(
            "- "
            f"{item['match_id']} {item['period']} row={item['event_row_index']} "
            f"status={item['status']} reason={item['reason']}"
        )
    if not report["sample_non_matches"]:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-json", default="artifacts/m2a/s1c-high-bypass-verify.json")
    parser.add_argument(
        "--out-md",
        default="delivery/m2a-high-bypass-completed-pass/M2A_S1C_HIGH_BYPASS_RESULTS.md",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = verify(out_json=Path(args.out_json), out_md=Path(args.out_md))
    print(
        json.dumps(
            {
                "decision": report["decision"],
                "artifact_hash": report["artifact_hash"],
                "runtime_summary": report["runtime_summary"],
                "out_json": args.out_json,
                "out_md": args.out_md,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
