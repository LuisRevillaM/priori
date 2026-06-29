"""Generate the Workbench high-bypass completed-pass replay bundle."""

from __future__ import annotations

import json
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
    replay_window,
)
from tqe.runtime.binder import bind_document  # noqa: E402
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows  # noqa: E402
from tqe.runtime.ir import TacticalQueryDocument, stable_hash  # noqa: E402
from tqe.runtime.pass_bypass import attack_x_sign_for  # noqa: E402

OUT_PATH = REPO_ROOT / "apps/workbench-alpha/src/generated/moment-high-bypass.json"
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
    moment = sorted(
        candidates,
        key=lambda row: (
            -int(row["requested_evidence"].get("opponents_bypassed_count") or 0),
            -float(row["requested_evidence"].get("forward_progression_m") or 0),
            int(row["anchor_frame_id"]),
        ),
    )[0]
    payload = payload_from_moment(
        moment,
        canonical_root=canonical_root,
        source_plan={
            "path": str((PLAN_DIR / f"{TARGET_ID}.json").relative_to(REPO_ROOT)),
            "document_hash": stable_hash(plan_payload),
            "plan_id": bound_plan.plan_id,
        },
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "path": str(OUT_PATH.relative_to(REPO_ROOT)),
                "result_id": moment["result_id"],
                "frame_count": len(payload["replay"]["frames"]),
                "opponents_bypassed_count": payload["moment"]["opponents_bypassed_count"],
            },
            sort_keys=True,
        )
    )


def synthesize_plan(contract: dict[str, Any], *, canonical_root: Path, raw_root: Path) -> dict[str, Any]:
    old_plan_dir = search.PLAN_DIR
    old_match_ids = search.MATCH_IDS
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    search.PLAN_DIR = PLAN_DIR
    search.MATCH_IDS = ["J03WOH"]
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


def payload_from_moment(moment: dict[str, Any], *, canonical_root: Path, source_plan: dict[str, Any]) -> dict[str, Any]:
    evidence = moment["requested_evidence"]
    release_frame_id = int(evidence["release_frame_id"])
    reception_frame_id = int(evidence["reception_frame_id"])
    start_frame_id = max(release_frame_id - 20, 0)
    end_frame_id = reception_frame_id + 28
    replay = replay_window(
        canonical_root=canonical_root,
        match_id=str(moment["match_id"]),
        period=str(moment["period"]),
        start_frame_id=start_frame_id,
        end_frame_id=end_frame_id,
    )
    orientation_rows = pd.read_parquet(canonical_root / "orientation.parquet")
    attacking_direction = attack_x_sign_for(
        orientation_rows,
        str(moment["match_id"]),
        str(moment["period"]),
        str(moment["perspective_team_role"]),
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
            "requested_evidence": evidence,
        },
        "replay": {
            **replay,
            "source_id": "moment_high_bypass_completed_pass",
            "generated_at": "deterministic_from_high_bypass_contract",
        },
        "visual_contract": {
            "completed_pass_path": ["release_frame_id", "reception_frame_id", "release_ball_point", "reception_ball_point"],
            "actors": ["passer_id", "receiver_id"],
            "bypassed_opponents": ["opponents_bypassed_count", "bypassed_player_ids", "candidate_goal_side_player_ids"],
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


if __name__ == "__main__":
    main()
