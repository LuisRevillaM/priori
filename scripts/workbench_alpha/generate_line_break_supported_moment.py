"""Generate the Workbench positive line-break-with-support replay bundle."""

from __future__ import annotations

import json
import math
import os
import sys
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
    entity_point_at_frame,
    observed_ball_outcome_sequence,
    pass_actor_ids,
    raw_possession_retention_not_evaluated,
    replay_window,
)
from tqe.runtime.binder import bind_document  # noqa: E402
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows  # noqa: E402
from tqe.runtime.ir import TacticalQueryDocument, stable_hash  # noqa: E402
from tqe.runtime.pass_bypass import attack_x_sign_for  # noqa: E402

OUT_PATH = REPO_ROOT / "apps/workbench-alpha/src/generated/moment-line-break-supported.json"
CATALOG_OUT_PATH = REPO_ROOT / "apps/workbench-alpha/src/generated/moment-line-break-supported-catalog.json"
PLAN_DIR = REPO_ROOT / "generated/workbench-alpha-moment-plans"
TARGET_ID = "line_break_with_underneath_support"
SUPPORT_DEFINITION = (
    "A controlled pass where the receiver moves beyond the observed second defending line and "
    "an underneath support outlet arrives in the behind-ball support region after reception."
)


def main() -> None:
    canonical_root = Path(os.environ.get("TQE_DATA_ROOT", "data/canonical/v1"))
    raw_root = Path(os.environ.get("TQE_RAW_ROOT", "data/raw/idsse/figshare-28196177-v1"))
    contract, _traces = generate_contract_from_meaning(SUPPORT_DEFINITION)
    plan_payload = synthesize_plan(contract, canonical_root=canonical_root, raw_root=raw_root)
    bound_plan = bind_document(TacticalQueryDocument.model_validate(plan_payload))
    execution = TacticalQueryExecutor(canonical_root=canonical_root, raw_root=raw_root).execute(bound_plan)
    rows = execution_result_rows(execution)
    candidates = [
        row
        for row in rows
        if row["requested_evidence"].get("support_arrival_status") == "PASS"
        and row["requested_evidence"].get("line_break_status") == "PASS"
        and row["requested_evidence"].get("coverage_status") == "COMPLETE"
        and row["requested_evidence"].get("supporting_player_ids")
    ]
    if not candidates:
        raise RuntimeError("No line-break-with-underneath-support candidates found.")
    source_plan = {
        "path": str((PLAN_DIR / f"{TARGET_ID}.json").relative_to(REPO_ROOT)),
        "document_hash": stable_hash(plan_payload),
        "plan_id": bound_plan.plan_id,
    }
    payloads = [
        payload_from_moment(moment, canonical_root=canonical_root, raw_root=raw_root, source_plan=source_plan)
        for moment in candidates
    ]
    payloads.sort(key=line_break_supported_payload_sort_key)
    payload = payloads[0]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    CATALOG_OUT_PATH.write_text(
        json.dumps(
            {
                "schema_version": "coach_moment_catalog.line_break_with_underneath_support.v0",
                "moment_kind": "line_break_with_underneath_outlet",
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
            raise RuntimeError(f"Supported line-break moment did not compile to a found result: {result}")
        return json.loads((PLAN_DIR / f"{TARGET_ID}.json").read_text(encoding="utf-8"))
    finally:
        search.PLAN_DIR = old_plan_dir
        search.MATCH_IDS = old_match_ids


def payload_from_moment(
    moment: dict[str, Any],
    *,
    canonical_root: Path,
    raw_root: Path,
    source_plan: dict[str, Any],
) -> dict[str, Any]:
    evidence = moment["requested_evidence"]
    release_frame_id = int(evidence["physical_release_frame_id"])
    reception_frame_id = int(evidence["controlled_reception_frame_id"])
    support_window_end_frame_id = reception_frame_id + math.ceil(float(evidence["maximum_arrival_seconds"]) * FRAME_RATE_HZ)
    start_frame_id = max(release_frame_id - 20, 0)
    end_frame_id = max(support_window_end_frame_id + 18, reception_frame_id + FRAME_RATE_HZ * 8)
    replay = replay_window(
        canonical_root=canonical_root,
        match_id=str(moment["match_id"]),
        period=str(moment["period"]),
        start_frame_id=start_frame_id,
        end_frame_id=end_frame_id,
        raw_root=None,
    )
    receiver_id = str(evidence["receiver_id"])
    passer_id = pass_actor_ids(str(evidence["pass_episode_id"]))[0]
    reference_point = entity_point_at_frame(replay["frames"], reception_frame_id, receiver_id)
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
        end_frame_id=min(support_window_end_frame_id + 18, reception_frame_id + FRAME_RATE_HZ * 4),
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
        receiver_id=receiver_id,
    )
    return {
        "schema_version": "moment_zero.line_break_with_underneath_support.v0",
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
            "support_window_end_frame_id": support_window_end_frame_id,
            "passer_id": passer_id,
            "receiver_id": receiver_id,
            "defensive_line_player_ids": evidence["defensive_line_player_ids"],
            "line_x_m": float(evidence["line_x_m"]),
            "observed_lines": evidence["observed_lines"],
            "support_region": {
                "mode": evidence["support_region_mode"],
                "reference_point": reference_point,
                "maximum_support_distance_m": float(evidence["maximum_support_distance_m"]),
                "maximum_arrival_seconds": float(evidence["maximum_arrival_seconds"]),
                "attacking_direction": attacking_direction,
                "candidate_player_ids": evidence["candidate_player_ids"],
                "supporting_player_ids": evidence["supporting_player_ids"],
                "support_arrival_status": evidence["support_arrival_status"],
                "support_arrival_reason": evidence["support_arrival_reason"],
                "coverage_status": evidence["coverage_status"],
            },
            "outcome_sequence": outcome_sequence,
            "possession_retention": possession_retention,
            "clean_control_retention": clean_control_retention,
            "requested_evidence": evidence,
        },
        "replay": {
            **replay,
            "source_id": "moment_line_break_with_underneath_support",
            "generated_at": "deterministic_from_supported_line_break_contract",
        },
        "visual_contract": {
            "defensive_line": ["line_x_m", "observed_lines", "defensive_line_player_ids"],
            "pass_path": ["physical_release_frame_id", "controlled_reception_frame_id", "pass_episode_id"],
            "receiver_crossing": ["receiver_id", "release_relative_position_status", "reception_relative_position_status"],
            "support_region": [
                "support_region_mode",
                "maximum_support_distance_m",
                "supporting_player_ids",
                "support_arrival_status",
                "coverage_status",
            ],
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
                "who should have supported",
            ],
        },
    }


def pass_team_role(pass_episode_id: str) -> str | None:
    parts = pass_episode_id.split(":")
    return parts[2] if len(parts) >= 3 else None


def line_break_supported_payload_sort_key(payload: dict[str, Any]) -> tuple[int, int, int, int]:
    moment = payload["moment"]
    clean_rank = 0 if moment["clean_control_retention"]["status"] == "PASS" else 1
    retention_rank = 0 if moment["possession_retention"]["status"] == "PASS" else 1
    same_team_rank = (
        pass_team_role(str(moment["requested_evidence"].get("pass_episode_id", "")))
        != moment.get("perspective_team_role")
    )
    return (
        clean_rank,
        retention_rank,
        1 if same_team_rank else 0,
        int(moment["anchor_frame_id"]),
    )


def catalog_match_ids() -> list[str]:
    raw_value = os.environ.get(
        "TQE_WORKBENCH_MATCH_IDS",
        "J03WOH,J03WOY,J03WPY,J03WQQ,J03WR9,J03WMX,J03WN1",
    )
    return [item.strip() for item in raw_value.split(",") if item.strip()]


if __name__ == "__main__":
    main()
