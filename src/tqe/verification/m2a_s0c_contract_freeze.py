"""M2A-S0C integrated data-truth contract freeze.

This gate consumes the S0A event/tracking preflight, S0B active-player
preflight, and the pure bypass evaluator. It either emits PROCEED_TO_S1 for a
bounded accepted scope or STOP_AND_REPORT_DATA_GAP.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tqe.runtime.bypass import evaluate_opponents_bypassed_by_action


@dataclass(frozen=True)
class GateCheck:
    check_id: str
    status: str
    detail: str


def stable_json_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def bypass_smoke() -> dict[str, Any]:
    evaluation = evaluate_opponents_bypassed_by_action(
        release_ball_x_m=0.0,
        reception_ball_x_m=12.0,
        attack_x_sign=1,
        expected_active_opponent_ids={"a", "b", "c"},
        release_opponent_positions={
            "a": (3.0, 0.0),
            "b": (5.0, 0.0),
            "c": (-2.0, 0.0),
        },
        reception_opponent_positions={
            "a": (3.0, 0.0),
            "b": (5.0, 0.0),
            "c": (-2.0, 0.0),
        },
    )
    return evaluation.to_dict()


def build_contract(
    *,
    s0a_path: Path,
    s0b_path: Path,
    s0a: dict[str, Any],
    s0b: dict[str, Any],
) -> dict[str, Any]:
    checks: list[GateCheck] = []
    s0a_summary = s0a["summary"]
    s0b_pass_windows = s0b["pass_window_analysis"]
    bypass = bypass_smoke()

    checks.append(
        GateCheck(
            check_id="s0a_schema",
            status="PASS" if s0a.get("schema_version") == "m2a.s0a.event_preflight.v1" else "FAIL",
            detail=str(s0a.get("schema_version")),
        )
    )
    pass_count = int(s0a_summary["controlled_pass_status_counts"].get("PASS", 0))
    checks.append(
        GateCheck(
            check_id="s0a_positive_controlled_passes",
            status="PASS" if pass_count > 0 else "FAIL",
            detail=f"{pass_count} provisional controlled-pass PASS records",
        )
    )
    event_offset_p95 = float(s0a_summary["event_frame_offset_ms"]["p95"])
    checks.append(
        GateCheck(
            check_id="s0a_timestamp_alignment",
            status="PASS" if abs(event_offset_p95) <= 25.0 else "FAIL",
            detail=f"event-frame offset p95={event_offset_p95}ms",
        )
    )
    release_delta_p50 = float(s0a_summary["release_delta_seconds_from_event"]["p50"])
    checks.append(
        GateCheck(
            check_id="s0a_event_is_not_release_frame",
            status="PASS" if release_delta_p50 != 0.0 else "FAIL",
            detail=f"physical release delta p50={release_delta_p50}s; S1 must derive release from tracking",
        )
    )
    checks.append(
        GateCheck(
            check_id="s0b_schema",
            status="PASS" if s0b.get("schema_version") == "m2a.s0b.active_players.v1" else "FAIL",
            detail=str(s0b.get("schema_version")),
        )
    )
    checks.append(
        GateCheck(
            check_id="s0b_j03woy_pass_window_count_matches_s0a",
            status="PASS" if int(s0b_pass_windows["window_count"]) == pass_count else "FAIL",
            detail=f"S0B windows={s0b_pass_windows['window_count']} S0A pass={pass_count}",
        )
    )
    checks.append(
        GateCheck(
            check_id="s0b_no_active_change_in_accepted_scope",
            status="PASS" if int(s0b_pass_windows["windows_with_active_set_change"]) == 0 else "FAIL",
            detail=f"{s0b_pass_windows['windows_with_active_set_change']} J03WOY pass windows cross active-set changes",
        )
    )
    checks.append(
        GateCheck(
            check_id="s0b_no_unusable_denominator_in_accepted_scope",
            status="PASS"
            if int(s0b_pass_windows["windows_with_unusable_defending_outfield_denominator"]) == 0
            else "FAIL",
            detail=(
                f"{s0b_pass_windows['windows_with_unusable_defending_outfield_denominator']} "
                "J03WOY pass windows have empty/unusable defending denominator"
            ),
        )
    )
    checks.append(
        GateCheck(
            check_id="s0b_full_corpus_caution_recorded",
            status="PASS" if int(s0b["summary"]["frame_count_deviation_count"]) > 0 else "FAIL",
            detail=f"{s0b['summary']['frame_count_deviation_count']} full-corpus frame/team count deviations require coverage policy",
        )
    )
    checks.append(
        GateCheck(
            check_id="s0c_bypass_smoke",
            status="PASS"
            if bypass["evaluation_status"] == "PASS"
            and bypass["opponents_bypassed_count"] == 2
            and bypass["bypassed_player_ids"] == ("a", "b")
            else "FAIL",
            detail=json.dumps(bypass, sort_keys=True),
        )
    )

    decision = "PROCEED_TO_S1" if all(check.status == "PASS" for check in checks) else "STOP_AND_REPORT_DATA_GAP"
    contract = {
        "schema_version": "m2a.s0.contract_freeze.v1",
        "decision": decision,
        "decision_scope": {
            "accepted_match_ids": ["J03WOY"],
            "accepted_periods": ["firstHalf", "secondHalf"],
            "accepted_scope_reason": (
                "J03WOY has successful event/tracking pass reconstruction and no active-set "
                "or unusable-denominator issues in the 593 provisional controlled pass windows."
            ),
            "excluded_until_reclassified": [
                "Full-corpus periods with reduced player counts or incomplete tracking must not be treated as complete denominators without S0C-equivalent coverage classification."
            ],
        },
        "source_artifacts": {
            "s0a_event_preflight_path": str(s0a_path),
            "s0a_event_preflight_sha256": file_sha256(s0a_path),
            "s0b_active_players_path": str(s0b_path),
            "s0b_active_players_sha256": file_sha256(s0b_path),
        },
        "gate_checks": [asdict(check) for check in checks],
        "evidence_summary": {
            "candidate_completed_pass_events": s0a_summary["candidate_completed_pass_events"],
            "controlled_pass_status_counts": s0a_summary["controlled_pass_status_counts"],
            "event_frame_offset_ms": s0a_summary["event_frame_offset_ms"],
            "release_delta_seconds_from_event": s0a_summary["release_delta_seconds_from_event"],
            "reception_delta_seconds_from_release": s0a_summary["reception_delta_seconds_from_release"],
            "j03woy_pass_window_analysis": s0b_pass_windows,
            "full_corpus_frame_count_deviation_count": s0b["summary"]["frame_count_deviation_count"],
            "full_corpus_incomplete_period_role_samples": [
                item
                for item in s0b["period_summaries"]
                if item["active_players_at_period_start"] != 11
                or item["active_players_at_period_end"] != 11
                or item["outfield_at_period_start"] != 10
                or item["outfield_at_period_end"] != 10
            ],
            "bypass_smoke": bypass,
        },
        "frozen_contract": {
            "event_timestamp_policy": {
                "alignment_source": "events.timestamp",
                "alignment_method": "nearest canonical frame timestamp in UTC",
                "observed_j03woy_p95_offset_ms": event_offset_p95,
                "not_release_frame": True,
                "gameclock_seconds_usage": "reporting/fallback only; not primary alignment",
            },
            "controlled_pass_episode_schema": {
                "rich_record": "ControlledPassEpisode",
                "predicate_record": "ControlledPassEvaluation",
                "required_anchor_relative_output": "controlled_pass_episode.anchor_evaluations",
                "identity": "pass_episode_id, not frame-only correlation",
                "required_fields": [
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
                ],
            },
            "release_control_policy": {
                "event_anchor_frame_id_definition": "nearest canonical frame to events.timestamp in UTC",
                "physical_release_frame_id_definition": (
                    "last frame in the bounded action window where the named passer uniquely controls the ball "
                    "before the ball-departure transition toward the completed pass"
                ),
                "search_window_seconds_from_event": [-1.0, 3.0],
                "control_distance_m": 2.5,
                "nearest_teammate_margin_m": 1.0,
                "pass_condition": (
                    "named passer controls ball in the event-derived action window and a unique physical "
                    "release transition is identified"
                ),
                "fail_condition": (
                    "complete tracking coverage proves passer does not control ball in window or transition "
                    "evidence contradicts the event"
                ),
                "unknown_condition": "event frame, passer identity, ball, or passer tracking unavailable",
                "s0a_preflight_limitation": (
                    "S0A release_frame_id is a provisional passer-control proxy. S1 must emit "
                    "physical_release_frame_id only after transition detection and must keep event_anchor_frame_id separate."
                ),
                "required_reason_codes": [
                    "release_not_confirmed",
                    "unique_release_transition_not_found",
                    "missing_tracking",
                    "identity_unresolved",
                    "excessive_frame_gap",
                ],
            },
            "controlled_reception_policy": {
                "search_window_seconds_after_release": 6.0,
                "control_distance_m": 2.5,
                "nearest_teammate_margin_m": 1.0,
                "minimum_dwell_seconds": 0.24,
                "termination_order": [
                    "controlled reception by named receiver",
                    "another player controls ball first with incompatible possession evidence",
                    "known stoppage or incompatible event before reception",
                    "period end",
                    "maximum search window",
                ],
                "pass_condition": "named receiver controls ball for the dwell window before a disqualifying stop",
                "fail_condition": "complete coverage and contradictory evidence prove no controlled reception",
                "unknown_condition": "release not proven, missing tracking coverage, ambiguous first controller, or unresolved event conflict",
                "required_reason_codes": [
                    "receiver_controlled_first",
                    "another_player_controlled_first",
                    "possession_definitively_broke",
                    "reception_window_expired",
                    "missing_tracking",
                    "identity_unresolved",
                    "excessive_frame_gap",
                ],
            },
            "active_player_policy": {
                "denominator_source": (
                    "initial accepted scope uses tracking-derived active on-pitch players cross-checked with "
                    "players.parquet metadata; all-corpus expansion should reconcile lineup/substitution/dismissal "
                    "events as the authoritative roster-change explanation"
                ),
                "expected_opposition_set": "active defending outfield players at release and reception",
                "roster_not_denominator": True,
                "goalkeeper_policy": "exclude known goalkeepers; unknown goalkeeper metadata makes denominator UNKNOWN",
                "active_set_change_inside_pass_window": "UNKNOWN",
                "reduced_player_period_policy": (
                    "A reduced active outfield denominator may be valid after dismissal, but S1 accepted scope "
                    "is J03WOY only. Other periods require explicit coverage classification before acceptance."
                ),
            },
            "bypass_measurement_policy": {
                "capability": "opponents_bypassed_by_action",
                "threshold_free": True,
                "goal_side_buffer_m": 1.0,
                "bypassed_buffer_m": 1.0,
                "opponent_bypassed_definition": (
                    "opponent is goal-side of the ball at release AND behind the ball at controlled reception"
                ),
                "missing_expected_active_opponent": "UNKNOWN, never silently reduced count",
                "recipe_thresholds_owned_by": "high_bypass_completed_pass_v1",
            },
            "high_bypass_recipe_policy": {
                "recipe_id": "high_bypass_completed_pass_v1",
                "conditions": [
                    "controlled_pass_episode.anchor_evaluations.controlled_pass_status == PASS",
                    "controlled_pass_episode.anchor_evaluations.forward_progression_m >= 8.0",
                    "opponents_bypassed_by_action.anchor_evaluations.opponents_bypassed_count >= 5",
                ],
                "classification_label": "HIGH_BYPASS_COMPLETED_PASS",
                "more_than_four_translation": ">= 5",
            },
            "decision_table": [
                {
                    "case": "all required evidence proven",
                    "controlled_pass_status": "PASS",
                    "bypass_coverage_status": "PASS",
                    "result": "PASS or FAIL according to recipe thresholds",
                },
                {
                    "case": "complete evidence contradicts pass, reception, or threshold",
                    "result": "FAIL",
                },
                {
                    "case": "missing/insufficient tracking, metadata, active-set, orientation, or endpoint evidence could change answer",
                    "result": "UNKNOWN",
                },
                {
                    "case": "active-player membership changes between release and reception",
                    "result": "UNKNOWN",
                },
            ],
            "explicit_non_claims": [
                "Does not prove a formal defensive line was broken.",
                "Does not prove the pass alone caused every highlighted opponent to be bypassed.",
                "Does not infer player intent, optimality, pass probability, body orientation, or scanning.",
            ],
        },
        "s1_unlock": {
            "unlocked": decision == "PROCEED_TO_S1",
            "allowed_initial_runtime_scope": [
                "controlled_pass_episode for J03WOY accepted scope",
                "opponents_bypassed_by_action using active defending outfield sets",
                "high_bypass_completed_pass_v1 result emission",
            ],
            "blocked_until_later": [
                "all-corpus M2A execution without reduced-player/tracking-gap coverage classification",
                "Hermes exposure",
                "defensive-line or support-response semantics",
            ],
        },
    }
    contract["contract_sha256"] = stable_json_hash({k: v for k, v in contract.items() if k != "contract_sha256"})
    return contract


def write_markdown(contract: dict[str, Any], path: Path) -> None:
    checks = contract["gate_checks"]
    lines = [
        "# M2A-S0C Contract Freeze",
        "",
        f"Decision: **{contract['decision']}**",
        "",
        f"Contract SHA-256: `{contract['contract_sha256']}`",
        "",
        "## Accepted Scope",
        "",
        f"- Match IDs: `{contract['decision_scope']['accepted_match_ids']}`",
        f"- Periods: `{contract['decision_scope']['accepted_periods']}`",
        f"- Reason: {contract['decision_scope']['accepted_scope_reason']}",
        "",
        "## Gate Checks",
        "",
    ]
    for check in checks:
        lines.append(f"- `{check['check_id']}`: **{check['status']}** - {check['detail']}")
    lines.extend(
        [
            "",
            "## Evidence Summary",
            "",
            f"- Candidate completed pass events: {contract['evidence_summary']['candidate_completed_pass_events']}",
            f"- Controlled pass status counts: `{contract['evidence_summary']['controlled_pass_status_counts']}`",
            f"- Event-frame offset ms: `{contract['evidence_summary']['event_frame_offset_ms']}`",
            f"- Release delta from event seconds: `{contract['evidence_summary']['release_delta_seconds_from_event']}`",
            f"- Reception delta from release seconds: `{contract['evidence_summary']['reception_delta_seconds_from_release']}`",
            f"- J03WOY pass-window analysis: `{contract['evidence_summary']['j03woy_pass_window_analysis']}`",
            f"- Full-corpus frame/team count deviations: {contract['evidence_summary']['full_corpus_frame_count_deviation_count']}",
            "",
            "## Frozen Policies",
            "",
            "- Event timestamp is the action anchor, not physical release.",
            "- Physical release must be derived from tracking around the event.",
            "- Controlled reception must be derived from receiver control in tracking.",
            "- Expected opposition denominator is active defending outfield players at release and reception.",
            "- Active-set changes inside the pass window become `UNKNOWN`.",
            "- Missing expected active opponents become `UNKNOWN`; counts are never silently reduced.",
            "- Bypass measurement is threshold-free; the recipe owns `>= 5` and `forward_progression_m >= 8`.",
            "",
            "## S1 Boundary",
            "",
            f"- S1 unlocked: `{contract['s1_unlock']['unlocked']}`",
            f"- Allowed initial runtime scope: `{contract['s1_unlock']['allowed_initial_runtime_scope']}`",
            f"- Still blocked: `{contract['s1_unlock']['blocked_until_later']}`",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s0a", default="artifacts/m2a/s0a-event-preflight-J03WOY.json")
    parser.add_argument("--s0b", default="artifacts/m2a/s0b-active-player-timeline-all.json")
    parser.add_argument("--out-json", default="artifacts/m2a/s0-contract-freeze.json")
    parser.add_argument(
        "--out-md",
        default="delivery/m2a-high-bypass-completed-pass/M2A_S0C_CONTRACT_FREEZE.md",
    )
    parser.add_argument(
        "--out-pinned-json",
        default="delivery/m2a-high-bypass-completed-pass/s0-contract-freeze.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    s0a_path = Path(args.s0a)
    s0b_path = Path(args.s0b)
    s0a = load_json(s0a_path)
    s0b = load_json(s0b_path)
    contract = build_contract(s0a_path=s0a_path, s0b_path=s0b_path, s0a=s0a, s0b=s0b)

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_pinned_json = Path(args.out_pinned_json)
    for path in (out_json, out_md, out_pinned_json):
        path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(contract, indent=2, sort_keys=True)
    out_json.write_text(encoded, encoding="utf-8")
    out_pinned_json.write_text(encoded, encoding="utf-8")
    write_markdown(contract, out_md)
    print(
        json.dumps(
            {
                "decision": contract["decision"],
                "contract_sha256": contract["contract_sha256"],
                "checks": contract["gate_checks"],
                "out_json": str(out_json),
                "out_pinned_json": str(out_pinned_json),
                "out_md": str(out_md),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if contract["decision"] == "PROCEED_TO_S1" else 1


if __name__ == "__main__":
    raise SystemExit(main())
