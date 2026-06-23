"""Verify M2A-S1A controlled_pass_episode runtime slice."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from tqe.runtime.controlled_pass import evaluate_controlled_passes


REQUIRED_EVALUATION_FIELDS = {
    "anchor_id",
    "pass_episode_id",
    "event_anchor_frame_id",
    "physical_release_frame_id",
    "event_to_release_offset_ms",
    "release_detection_status",
    "release_detection_reason",
    "controlled_pass_status",
    "release_control_status",
    "controlled_reception_status",
    "possession_continuity_status",
    "forward_progression_m",
    "controlled_reception_frame_id",
    "passer_id",
    "receiver_id",
    "evaluation_status",
}


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def verify(*, contract_path: Path, out_json: Path, out_md: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    output = evaluate_controlled_passes(
        match_ids=tuple(contract["decision_scope"]["accepted_match_ids"]),
        periods=tuple(contract["decision_scope"]["accepted_periods"]),
    )
    output_dict = asdict(output)
    episodes = output_dict["episodes"]
    evaluations = output_dict["anchor_evaluations"]
    pass_evaluations = [item for item in evaluations if item["controlled_pass_status"] == "PASS"]
    non_pass = [item for item in evaluations if item["controlled_pass_status"] != "PASS"]

    checks = [
        {
            "check_id": "s0_contract_allows_s1",
            "status": "PASS" if contract["decision"] == "PROCEED_TO_S1" else "FAIL",
            "detail": contract["decision"],
        },
        {
            "check_id": "runtime_schema",
            "status": "PASS" if output.schema_version == "m2a.controlled_pass_episode.v1" else "FAIL",
            "detail": output.schema_version,
        },
        {
            "check_id": "episodes_exist",
            "status": "PASS" if episodes else "FAIL",
            "detail": f"{len(episodes)} PASS episodes",
        },
        {
            "check_id": "anchor_evaluations_cover_events",
            "status": "PASS" if len(evaluations) == int(output.summary["candidate_event_count"]) else "FAIL",
            "detail": f"evaluations={len(evaluations)} candidates={output.summary['candidate_event_count']}",
        },
        {
            "check_id": "required_fields_present",
            "status": "PASS"
            if all(REQUIRED_EVALUATION_FIELDS.issubset(item.keys()) for item in evaluations)
            else "FAIL",
            "detail": ",".join(sorted(REQUIRED_EVALUATION_FIELDS)),
        },
        {
            "check_id": "event_anchor_not_collapsed_to_physical_release",
            "status": "PASS"
            if any(
                item["event_anchor_frame_id"] != item["physical_release_frame_id"]
                for item in pass_evaluations
            )
            else "FAIL",
            "detail": "at least one PASS row has distinct event_anchor_frame_id and physical_release_frame_id",
        },
        {
            "check_id": "non_pass_rows_have_reasons",
            "status": "PASS"
            if all(
                item["release_detection_reason"] or item["controlled_reception_reason"]
                for item in non_pass
            )
            else "FAIL",
            "detail": f"{len(non_pass)} non-PASS rows",
        },
    ]
    decision = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    report = {
        "schema_version": "m2a.s1a.controlled_pass_verify.v1",
        "decision": decision,
        "s0_contract_path": str(contract_path),
        "s0_contract_sha256": contract["contract_sha256"],
        "checks": checks,
        "runtime_summary": output.summary,
        "accepted_scope": output.accepted_scope,
        "artifact_hash": stable_hash(
            {
                "episodes": episodes,
                "anchor_evaluations": evaluations,
                "config": output.config,
            }
        ),
        "sample_pass_episodes": episodes[:10],
        "sample_non_pass_evaluations": non_pass[:20],
        "output": output_dict,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(report, out_md)
    return report


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# M2A-S1A Controlled Pass Runtime Verification",
        "",
        f"Decision: **{report['decision']}**",
        "",
        f"S0 contract SHA-256: `{report['s0_contract_sha256']}`",
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
            f"- Candidate events: {report['runtime_summary']['candidate_event_count']}",
            f"- PASS episodes: {report['runtime_summary']['episode_count']}",
            f"- Controlled pass status counts: `{report['runtime_summary']['controlled_pass_status_counts']}`",
            f"- Release detection status counts: `{report['runtime_summary']['release_detection_status_counts']}`",
            f"- Reception status counts: `{report['runtime_summary']['reception_status_counts']}`",
            f"- Reason counts: `{report['runtime_summary']['reason_counts']}`",
            f"- Event-to-release offset ms: `{report['runtime_summary']['event_to_release_offset_ms']}`",
            f"- Release-to-reception seconds: `{report['runtime_summary']['release_to_reception_seconds']}`",
            f"- Forward progression m: `{report['runtime_summary']['forward_progression_m']}`",
            "",
            "## Boundary",
            "",
            "- This verifies `controlled_pass_episode` only.",
            "- It does not wire `opponents_bypassed_by_action` to real pass episodes.",
            "- It does not emit `high_bypass_completed_pass_v1` results.",
            "- It remains scoped to the S0C accepted match `J03WOY`.",
            "- Hermes exposure and all-corpus execution remain blocked.",
            "",
            "## Sample PASS Episodes",
            "",
        ]
    )
    for item in report["sample_pass_episodes"][:5]:
        lines.append(
            "- "
            f"{item['match_id']} {item['period']} row {item['event_row_index']} "
            f"{item['passer_id']}->{item['receiver_id']} "
            f"anchor={item['event_anchor_frame_id']} release={item['physical_release_frame_id']} "
            f"reception={item['controlled_reception_frame_id']} progression={item['forward_progression_m']}"
        )
    if not report["sample_pass_episodes"]:
        lines.append("- none")
    lines.extend(["", "## Sample Non-PASS Evaluations", ""])
    for item in report["sample_non_pass_evaluations"][:5]:
        lines.append(
            "- "
            f"{item['match_id']} {item['period']} row {item['event_row_index']} "
            f"status={item['controlled_pass_status']} "
            f"release_reason={item['release_detection_reason']} "
            f"reception_reason={item['controlled_reception_reason']}"
        )
    if not report["sample_non_pass_evaluations"]:
        lines.append("- none")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        default="delivery/m2a-high-bypass-completed-pass/s0-contract-freeze.json",
    )
    parser.add_argument("--out-json", default="artifacts/m2a/s1a-controlled-pass-verify.json")
    parser.add_argument(
        "--out-md",
        default="delivery/m2a-high-bypass-completed-pass/M2A_S1A_CONTROLLED_PASS.md",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = verify(
        contract_path=Path(args.contract),
        out_json=Path(args.out_json),
        out_md=Path(args.out_md),
    )
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
