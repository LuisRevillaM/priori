"""Verify M2A-S1B pass-bypass measurement wiring."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from tqe.runtime.pass_bypass import evaluate_pass_bypass_measurements


REQUIRED_FIELDS = {
    "anchor_id",
    "pass_episode_id",
    "match_id",
    "period",
    "event_anchor_frame_id",
    "physical_release_frame_id",
    "controlled_reception_frame_id",
    "expected_active_opponent_ids",
    "evaluated_opponent_ids",
    "missing_active_opponent_ids",
    "candidate_goal_side_ids",
    "bypassed_player_ids",
    "opponents_bypassed_count",
    "evaluation_status",
    "coverage_status",
    "failure_reason",
}


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify(*, out_json: Path, out_md: Path) -> dict[str, Any]:
    output = evaluate_pass_bypass_measurements(match_ids=("J03WOY",), periods=("firstHalf", "secondHalf"))
    output_dict = asdict(output)
    rows = output_dict["anchor_evaluations"]
    pass_rows = [item for item in rows if item["evaluation_status"] == "PASS"]
    unknown_rows = [item for item in rows if item["evaluation_status"] == "UNKNOWN"]
    checks = [
        {
            "check_id": "runtime_schema",
            "status": "PASS" if output.schema_version == "m2a.opponents_bypassed_by_action.v1" else "FAIL",
            "detail": output.schema_version,
        },
        {
            "check_id": "anchor_count_matches_controlled_pass_source",
            "status": "PASS"
            if output.summary["controlled_anchor_evaluation_count"]
            == output.summary["bypass_anchor_evaluation_count"]
            else "FAIL",
            "detail": (
                f"controlled={output.summary['controlled_anchor_evaluation_count']} "
                f"bypass={output.summary['bypass_anchor_evaluation_count']}"
            ),
        },
        {
            "check_id": "complete_measurements_exist",
            "status": "PASS" if pass_rows else "FAIL",
            "detail": f"{len(pass_rows)} complete measurements",
        },
        {
            "check_id": "required_fields_present",
            "status": "PASS" if all(REQUIRED_FIELDS.issubset(item.keys()) for item in rows) else "FAIL",
            "detail": ",".join(sorted(REQUIRED_FIELDS)),
        },
        {
            "check_id": "defending_outfield_denominator_is_complete",
            "status": "PASS"
            if all(
                len(item["expected_active_opponent_ids"]) == 10
                and len(item["evaluated_opponent_ids"]) == 10
                and not item["missing_active_opponent_ids"]
                for item in pass_rows
            )
            else "FAIL",
            "detail": "all complete measurements have 10 expected/evaluated defending outfield players",
        },
        {
            "check_id": "unknown_rows_have_reasons",
            "status": "PASS" if all(item["failure_reason"] for item in unknown_rows) else "FAIL",
            "detail": f"{len(unknown_rows)} UNKNOWN rows",
        },
        {
            "check_id": "measurement_has_future_recipe_headroom_without_classifying",
            "status": "PASS"
            if output.summary["max_opponents_bypassed_count"] >= 5
            and "HIGH_BYPASS_COMPLETED_PASS" not in json.dumps(output.summary)
            and "gte_5" not in json.dumps(output.summary).lower()
            else "FAIL",
            "detail": f"max measured opponents_bypassed_count={output.summary['max_opponents_bypassed_count']}",
        },
    ]
    decision = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    report = {
        "schema_version": "m2a.s1b.pass_bypass_verify.v1",
        "decision": decision,
        "checks": checks,
        "runtime_summary": output.summary,
        "accepted_scope": output.accepted_scope,
        "artifact_hash": stable_hash(
            {
                "anchor_evaluations": rows,
                "config": output.config,
            }
        ),
        "sample_complete_measurements": pass_rows[:10],
        "sample_largest_bypass_measurements": [
            item
            for item in pass_rows
            if int(item["opponents_bypassed_count"]) == report_max_count(output.summary)
        ][:10],
        "sample_unknown_measurements": unknown_rows[:20],
        "output": output_dict,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(report, out_md)
    return report


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# M2A-S1B Pass Bypass Measurement Verification",
        "",
        f"Decision: **{report['decision']}**",
        "",
        f"Runtime artifact hash: `{report['artifact_hash']}`",
        "",
        "## Checks",
        "",
    ]
    for check in report["checks"]:
        lines.append(f"- `{check['check_id']}`: **{check['status']}** - {check['detail']}")
    lines.extend(
        [
            "",
            "## Runtime Summary",
            "",
            f"- Controlled anchor evaluations: {report['runtime_summary']['controlled_anchor_evaluation_count']}",
            f"- Bypass anchor evaluations: {report['runtime_summary']['bypass_anchor_evaluation_count']}",
            f"- Evaluation status counts: `{report['runtime_summary']['evaluation_status_counts']}`",
            f"- Coverage status counts: `{report['runtime_summary']['coverage_status_counts']}`",
            f"- Failure reason counts: `{report['runtime_summary']['failure_reason_counts']}`",
            f"- Opponents bypassed distribution: `{report['runtime_summary']['opponents_bypassed_count_distribution']}`",
            f"- Max measured opponents bypassed: {report['runtime_summary']['max_opponents_bypassed_count']}",
            "",
            "## Boundary",
            "",
            "- This verifies `opponents_bypassed_by_action` measurement wiring only.",
            "- It does not emit `high_bypass_completed_pass_v1` QueryResult rows.",
            "- Raw `opponents_bypassed_count` values remain measurement evidence for the next recipe gate.",
            "- Hermes exposure and all-corpus execution remain blocked.",
            "",
            "## Sample Largest Bypass Measurements",
            "",
        ]
    )
    for item in report["sample_largest_bypass_measurements"][:5]:
        lines.append(
            "- "
            f"{item['match_id']} {item['period']} row {item['event_row_index']} "
            f"{item['passer_id']}->{item['receiver_id']} "
            f"count={item['opponents_bypassed_count']} "
            f"bypassed={list(item['bypassed_player_ids'])}"
        )
    if not report["sample_largest_bypass_measurements"]:
        lines.append("- none")
    lines.extend(["", "## Sample UNKNOWN Measurements", ""])
    for item in report["sample_unknown_measurements"][:5]:
        lines.append(
            "- "
            f"{item['match_id']} {item['period']} row {item['event_row_index']} "
            f"reason={item['failure_reason']}"
        )
    if not report["sample_unknown_measurements"]:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def report_max_count(summary: dict[str, Any]) -> int:
    return int(summary.get("max_opponents_bypassed_count") or 0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-json", default="artifacts/m2a/s1b-pass-bypass-verify.json")
    parser.add_argument(
        "--out-md",
        default="delivery/m2a-high-bypass-completed-pass/M2A_S1B_PASS_BYPASS.md",
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
