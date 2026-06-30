"""Generate the Workbench high-bypass completed-pass replay bundle."""

from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.coverage_map import compiler_search_reachability as search  # noqa: E402
from scripts.coverage_map.semantic_contract_scl0 import generate_contract_from_meaning  # noqa: E402
from scripts.workbench_alpha.generate_moment_zero import (  # noqa: E402
    FRAME_RATE_HZ,
    clean_control_retention_sequence,
    observed_ball_outcome_sequence,
    raw_possession_retention_not_evaluated,
    replay_window,
)
from tqe.runtime.binder import bind_document  # noqa: E402
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows  # noqa: E402
from tqe.runtime.ir import TacticalQueryDocument, stable_hash  # noqa: E402
from tqe.runtime.pass_bypass import attack_x_sign_for  # noqa: E402

OUT_PATH = REPO_ROOT / "apps/workbench-alpha/src/generated/moment-high-bypass.json"
CATALOG_OUT_PATH = REPO_ROOT / "apps/workbench-alpha/src/generated/moment-high-bypass-catalog.json"
PLAN_DIR = REPO_ROOT / "generated/workbench-alpha-moment-plans"
TARGET_ID = "high_bypass_completed_pass"
HIGH_BYPASS_DEFINITION = (
    "A high-bypass completed pass is a completed controlled pass that progresses the ball forward "
    "and bypasses at least five opposition outfield players."
)


def main() -> None:
    canonical_root = Path(os.environ.get("TQE_DATA_ROOT", "data/canonical/v1"))
    raw_root = Path(os.environ.get("TQE_RAW_ROOT", "data/raw/idsse/figshare-28196177-v1"))
    contract, _traces = generate_contract_from_meaning(HIGH_BYPASS_DEFINITION)
    plan_payload = synthesize_plan(contract, canonical_root=canonical_root, raw_root=raw_root)
    bound_plan = bind_document(TacticalQueryDocument.model_validate(plan_payload))
    execution = TacticalQueryExecutor(canonical_root=canonical_root, raw_root=raw_root).execute(bound_plan)
    rows = execution_result_rows(execution)
    candidates = [
        row
        for row in rows
        if row["requested_evidence"].get("evaluation_status") == "PASS"
        and float(row["requested_evidence"].get("opponents_bypassed_count") or 0) >= 5
        and float(row["requested_evidence"].get("forward_progression_m") or 0) >= 8
    ]
    if not candidates:
        raise RuntimeError("High-bypass contract compiled but returned no candidate rows.")
    source_plan = {
        "path": str((PLAN_DIR / f"{TARGET_ID}.json").relative_to(REPO_ROOT)),
        "document_hash": stable_hash(plan_payload),
        "plan_id": bound_plan.plan_id,
    }
    payloads = [
        payload_from_moment(moment, canonical_root=canonical_root, raw_root=raw_root, source_plan=source_plan)
        for moment in candidates
    ]
    payloads.sort(key=high_bypass_payload_sort_key)
    payload = payloads[0]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    CATALOG_OUT_PATH.write_text(
        json.dumps(
            {
                "schema_version": "coach_moment_catalog.high_bypass_completed_pass.v0",
                "moment_kind": "high_bypass_completed_pass",
                "count": len(payloads),
                "moments": payloads,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "path": str(OUT_PATH.relative_to(REPO_ROOT)),
                "catalog_path": str(CATALOG_OUT_PATH.relative_to(REPO_ROOT)),
                "result_id": payload["moment"]["result_id"],
                "frame_count": len(payload["replay"]["frames"]),
                "opponents_bypassed_count": payload["moment"]["opponents_bypassed_count"],
                "catalog_count": len(payloads),
                "clean_control_pass_count": sum(
                    1
                    for item in payloads
                    if item["moment"]["clean_control_retention"]["status"] == "PASS"
                ),
            },
            sort_keys=True,
        )
    )


def synthesize_plan(contract: dict[str, Any], *, canonical_root: Path, raw_root: Path) -> dict[str, Any]:
    old_plan_dir = search.PLAN_DIR
    old_match_ids = search.MATCH_IDS
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    search.PLAN_DIR = PLAN_DIR
    search.MATCH_IDS = catalog_match_ids()
    try:
        result = search.evaluate_target(
            target={"target_id": TARGET_ID, "concept": TARGET_ID, "target_contract": contract},
            row={"concept": TARGET_ID, "classification": "coach_prompt"},
            catalog=search.CatalogIndex(excluded_refs={"relation_destination_entry_classification", "outcome_classification"}),
            executor=TacticalQueryExecutor(canonical_root=canonical_root, raw_root=raw_root),
        )
        if result.get("result") != "compiler_reachable" or int(result.get("result_count") or 0) <= 0:
            raise RuntimeError(f"High-bypass moment did not compile to a found result: {result}")
        return json.loads((PLAN_DIR / f"{TARGET_ID}.json").read_text(encoding="utf-8"))
    finally:
        search.PLAN_DIR = old_plan_dir
        search.MATCH_IDS = old_match_ids


def high_bypass_payload_sort_key(payload: dict[str, Any]) -> tuple[int, int, float, int]:
    moment = payload["moment"]
    clean = moment["clean_control_retention"]
    clean_rank = 0 if clean["status"] == "PASS" else 1
    return (
        clean_rank,
        -int(moment.get("opponents_bypassed_count") or 0),
        -float(moment.get("forward_progression_m") or 0),
        int(moment["anchor_frame_id"]),
    )


def payload_from_moment(moment: dict[str, Any], *, canonical_root: Path, raw_root: Path, source_plan: dict[str, Any]) -> dict[str, Any]:
    evidence = moment["requested_evidence"]
    release_frame_id = int(evidence["release_frame_id"])
    reception_frame_id = int(evidence["reception_frame_id"])
    event_context = pass_event_context(
        canonical_root=canonical_root,
        match_id=str(moment["match_id"]),
        period=str(moment["period"]),
        team_role=str(moment["perspective_team_role"]),
        pass_episode_id=str(evidence["pass_episode_id"]),
    )
    start_frame_id = max(release_frame_id - 20, 0)
    end_frame_id = reception_frame_id + FRAME_RATE_HZ * 8
    replay = replay_window(
        canonical_root=canonical_root,
        match_id=str(moment["match_id"]),
        period=str(moment["period"]),
        start_frame_id=start_frame_id,
        end_frame_id=end_frame_id,
        raw_root=None,
    )
    orientation_rows = pd.read_parquet(canonical_root / "orientation.parquet")
    attacking_direction = attack_x_sign_for(
        orientation_rows,
        str(moment["match_id"]),
        str(moment["period"]),
        str(moment["perspective_team_role"]),
    )
    outcome_sequence = observed_ball_outcome_sequence(
        replay=replay,
        start_frame_id=reception_frame_id,
        end_frame_id=reception_frame_id + FRAME_RATE_HZ * 4,
        attacking_direction=attacking_direction,
    )
    possession_retention = raw_possession_retention_not_evaluated(
        start_frame_id=reception_frame_id,
        end_frame_id=reception_frame_id + FRAME_RATE_HZ * 4,
        perspective_team_role=str(moment["perspective_team_role"]),
    )
    clean_control_retention = clean_control_retention_sequence(
        replay=replay,
        start_frame_id=reception_frame_id,
        end_frame_id=reception_frame_id + FRAME_RATE_HZ * 4,
        perspective_team_role=str(moment["perspective_team_role"]),
        defending_team_role=str(moment["defending_team_role"]),
        receiver_id=str(evidence["receiver_id"]),
    )
    return {
        "schema_version": "coach_moment.high_bypass_completed_pass.v0",
        "source_plan": source_plan,
        "moment": {
            "result_id": moment["result_id"],
            "classification": moment["classification"],
            "match_id": moment["match_id"],
            "period": moment["period"],
            "perspective_team_role": moment["perspective_team_role"],
            "defending_team_role": moment["defending_team_role"],
            "anchor_frame_id": int(moment["anchor_frame_id"]),
            "release_frame_id": release_frame_id,
            "reception_frame_id": reception_frame_id,
            "passer_id": str(evidence["passer_id"]),
            "receiver_id": str(evidence["receiver_id"]),
            "event_type": event_context["event_type"],
            "restart_type": event_context["restart_type"],
            "open_play_status": event_context["open_play_status"],
            "event_context": event_context,
            "release_ball_point": evidence["release_ball_point"],
            "reception_ball_point": evidence["reception_ball_point"],
            "release_passer_point": evidence["release_passer_point"],
            "reception_receiver_point": evidence["reception_receiver_point"],
            "forward_progression_m": round(float(evidence["forward_progression_m"]), 2),
            "opponents_bypassed_count": int(evidence["opponents_bypassed_count"]),
            "bypassed_player_ids": evidence["bypassed_player_ids"],
            "candidate_goal_side_player_ids": evidence["candidate_goal_side_player_ids"],
            "evaluated_opponent_ids": evidence["evaluated_opponent_ids"],
            "attacking_direction": attacking_direction,
            "outcome_sequence": outcome_sequence,
            "possession_retention": possession_retention,
            "clean_control_retention": clean_control_retention,
            "requested_evidence": evidence,
        },
        "replay": {
            **replay,
            "source_id": "moment_high_bypass_completed_pass",
            "generated_at": "deterministic_from_high_bypass_contract",
        },
        "visual_contract": {
            "completed_pass_path": ["release_frame_id", "reception_frame_id", "release_ball_point", "reception_ball_point"],
            "observed_pass_event_context": [
                "event_type",
                "restart_type",
                "open_play_status",
                "event_context.from_open_play",
                "event_context.event_row_index",
            ],
            "actors": ["passer_id", "receiver_id"],
            "bypassed_opponents": ["opponents_bypassed_count", "bypassed_player_ids", "candidate_goal_side_player_ids"],
            "observed_outcome_sequence": [
                "outcome_sequence.start_frame_id",
                "outcome_sequence.end_frame_id",
                "outcome_sequence.ball_start_point",
                "outcome_sequence.ball_end_point",
                "outcome_sequence.forward_progression_m",
                "outcome_sequence.progression_status",
                "outcome_sequence.final_third_status",
                "outcome_sequence.final_third_outcome",
            ],
            "observed_possession_retention": [
                "possession_retention.status",
                "possession_retention.start_frame_id",
                "possession_retention.end_frame_id",
                "possession_retention.observed_seconds_after_reception",
                "possession_retention.perspective_team_role",
                "possession_retention.possession_team_role_at_end",
            ],
            "observed_clean_control_retention": [
                "clean_control_retention.status",
                "clean_control_retention.start_frame_id",
                "clean_control_retention.end_frame_id",
                "clean_control_retention.receiver_clean_control_max_seconds",
                "clean_control_retention.team_clean_control_max_seconds",
                "clean_control_retention.provider_loss_frame_count",
            ],
            "prohibited_visual_claims": [
                "intent",
                "quality",
                "causation",
                "optimality",
                "defensive line broken",
                "pass probability",
            ],
        },
}


def pass_event_context(
    *,
    canonical_root: Path,
    match_id: str,
    period: str,
    team_role: str,
    pass_episode_id: str,
) -> dict[str, Any]:
    parsed = parse_pass_episode_id(pass_episode_id)
    row_index = parsed.get("row_index")
    if row_index is None:
        return unknown_event_context(pass_episode_id, "pass_episode_id_parse_failed")

    events = events_for_match(str(canonical_root), match_id)
    if events.empty:
        return unknown_event_context(pass_episode_id, "event_table_missing")
    rows = events[
        (events["period"].astype(str) == period)
        & (events["team_role"].astype(str) == team_role)
        & (events["row_index"].astype(int) == int(row_index))
    ]
    if rows.empty:
        return unknown_event_context(pass_episode_id, "event_row_not_found", row_index=row_index)

    row = rows.iloc[0]
    event_type = str(row.get("event_type") or "")
    from_open_play = qualifier_bool(row.get("qualifier_json"), "FromOpenPlay")
    restart_type = restart_type_for_event_type(event_type)
    if restart_type is not None:
        open_play_status = "restart"
    elif from_open_play is True:
        open_play_status = "open_play"
    elif from_open_play is False:
        open_play_status = "not_open_play"
    elif event_type.startswith("Play_"):
        open_play_status = "open_play"
    else:
        open_play_status = "unknown"

    return {
        "status": "PASS" if open_play_status != "unknown" else "UNKNOWN",
        "source": "canonical_event_row",
        "pass_episode_id": pass_episode_id,
        "event_row_index": int(row_index),
        "event_type": event_type,
        "restart_type": restart_type,
        "from_open_play": from_open_play,
        "open_play_status": open_play_status,
        "claim_boundary": "Observed provider event type and FromOpenPlay flag only; no pass quality, intent, set-piece routine, or tactical causation claim.",
    }


def parse_pass_episode_id(pass_episode_id: str) -> dict[str, Any]:
    parts = str(pass_episode_id).split(":")
    if len(parts) < 4:
        return {}
    try:
        row_index = int(parts[3])
    except ValueError:
        return {}
    return {
        "match_id": parts[0],
        "period": parts[1],
        "team_role": parts[2],
        "row_index": row_index,
    }


def unknown_event_context(pass_episode_id: str, reason: str, *, row_index: int | None = None) -> dict[str, Any]:
    return {
        "status": "UNKNOWN",
        "source": "canonical_event_row",
        "pass_episode_id": pass_episode_id,
        "event_row_index": row_index,
        "event_type": None,
        "restart_type": None,
        "from_open_play": None,
        "open_play_status": "unknown",
        "reason": reason,
        "claim_boundary": "Observed provider event type and FromOpenPlay flag only; no pass quality, intent, set-piece routine, or tactical causation claim.",
    }


@lru_cache(maxsize=16)
def events_for_match(canonical_root: str, match_id: str) -> pd.DataFrame:
    path = Path(canonical_root) / "events" / f"match_id={match_id}.parquet"
    if not path.exists():
        return pd.DataFrame(columns=["period", "team_role", "row_index", "event_type", "qualifier_json"])
    return pd.read_parquet(path, columns=["period", "team_role", "row_index", "event_type", "qualifier_json"])


def qualifier_bool(qualifier_json: Any, key: str) -> bool | None:
    if not isinstance(qualifier_json, str) or not qualifier_json.strip():
        return None
    try:
        payload = json.loads(qualifier_json)
    except json.JSONDecodeError:
        return None
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return None


def restart_type_for_event_type(event_type: str) -> str | None:
    if event_type.startswith("CornerKick"):
        return "corner_kick"
    if event_type.startswith("FreeKick"):
        return "free_kick"
    if event_type.startswith("GoalKick"):
        return "goal_kick"
    if event_type.startswith("ThrowIn"):
        return "throw_in"
    if event_type.startswith("KickOff"):
        return "kick_off"
    if event_type.startswith("Penalty_"):
        return "penalty"
    return None


def catalog_match_ids() -> list[str]:
    raw_value = os.environ.get(
        "TQE_WORKBENCH_MATCH_IDS",
        "J03WOH,J03WOY,J03WPY,J03WQQ,J03WR9,J03WMX,J03WN1",
    )
    return [item.strip() for item in raw_value.split(",") if item.strip()]


if __name__ == "__main__":
    main()
