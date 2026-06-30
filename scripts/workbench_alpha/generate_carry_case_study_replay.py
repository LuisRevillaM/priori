"""Generate a compact case-study replay for observed carry movement."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.workbench_alpha.generate_moment_zero import FRAME_RATE_HZ, replay_window  # noqa: E402
from tqe.runtime.binder import bind_document  # noqa: E402
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows  # noqa: E402
from tqe.runtime.ir import TacticalQueryDocument, stable_hash  # noqa: E402

PLAN_PATH = REPO_ROOT / "config/query-plans/carry_episode.experimental.v1.json"
OUT_PATH = REPO_ROOT / "apps/workbench-alpha/public/case-study-carry-replays.json"


def main() -> None:
    canonical_root = Path(os.environ.get("TQE_DATA_ROOT", "data/canonical/v1"))
    raw_root = Path(os.environ.get("TQE_RAW_ROOT", "data/raw/idsse/figshare-28196177-v1"))
    document_payload = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    document = TacticalQueryDocument.model_validate(document_payload)
    bound_plan = bind_document(document)
    executor = TacticalQueryExecutor(canonical_root=canonical_root, raw_root=raw_root)
    execution = executor.execute(bound_plan)
    rows = execution_result_rows(execution)
    pass_rows = [
        row
        for row in rows
        if row.get("requested_evidence", {}).get("carry_status") == "PASS"
        and row.get("requested_evidence", {}).get("control_continuity_status") == "PASS"
        and row.get("requested_evidence", {}).get("possession_continuity_status") == "PASS"
    ]
    if not pass_rows:
        raise RuntimeError("No PASS carry rows available for case-study replay.")

    selected = select_representative_row(pass_rows)
    payload = payload_from_row(selected, canonical_root=canonical_root)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "schema_version": "case_study_carry_replay_packet.v0",
                "source": {
                    "plan_path": str(PLAN_PATH.relative_to(REPO_ROOT)),
                    "plan_hash": stable_hash(document_payload),
                    "selection": "clear carry PASS with visible displacement and carried control evidence",
                },
                "replays": [{"index": 0, "payload": payload}],
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
                "match_id": payload["moment"]["match_id"],
                "period": payload["moment"]["period"],
                "carrier_id": payload["moment"]["carrier_id"],
                "carry_start_frame_id": payload["moment"]["carry_start_frame_id"],
                "carry_end_frame_id": payload["moment"]["carry_end_frame_id"],
                "duration_seconds": payload["moment"]["carry_duration_seconds"],
                "displacement_m": payload["moment"]["displacement_m"],
                "forward_progression_m": payload["moment"]["carry_forward_progression_m"],
                "frame_count": len(payload["replay"]["frames"]),
            },
            sort_keys=True,
        )
    )


def select_representative_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = []
    for row in rows:
        evidence = row["requested_evidence"]
        duration = float(evidence.get("carry_duration_seconds") or 0.0)
        displacement = float(evidence.get("displacement_m") or 0.0)
        forward = float(evidence.get("carry_forward_progression_m") or 0.0)
        if 2.0 <= duration <= 8.0 and 6.0 <= displacement <= 18.0 and forward >= 4.0:
            candidates.append(row)
    scored = candidates or rows
    return max(
        scored,
        key=lambda row: (
            float(row["requested_evidence"].get("carry_forward_progression_m") or 0.0),
            float(row["requested_evidence"].get("displacement_m") or 0.0),
            float(row["requested_evidence"].get("comoving_frame_ratio") or 0.0),
            -int(row.get("anchor_frame_id") or 0),
        ),
    )


def payload_from_row(row: dict[str, Any], *, canonical_root: Path) -> dict[str, Any]:
    evidence = row["requested_evidence"]
    start_frame_id = int(evidence["carry_start_frame_id"])
    end_frame_id = int(evidence["carry_end_frame_id"])
    replay = replay_window(
        canonical_root=canonical_root,
        match_id=str(row["match_id"]),
        period=str(row["period"]),
        start_frame_id=max(start_frame_id - 20, 0),
        end_frame_id=end_frame_id + 20,
        raw_root=None,
    )
    replay["replay_window_id"] = f"case_study_carry_{row['match_id']}_{row['period']}_{start_frame_id}_{end_frame_id}"
    replay["source_id"] = "case_study_carry"
    replay["generated_at"] = "deterministic_from_carry_episode_plan"
    replay["anchor_frame_id"] = end_frame_id
    return {
        "schema_version": "coach_moment.carry_episode.v0",
        "moment": {
            "result_id": row["result_id"],
            "match_id": row["match_id"],
            "period": row["period"],
            "team_role": evidence["team_role"],
            "anchor_frame_id": end_frame_id,
            "carry_episode_id": evidence["carry_episode_id"],
            "carrier_id": evidence["carrier_id"],
            "carry_status": evidence["carry_status"],
            "carry_reason": evidence["carry_reason"],
            "carry_start_frame_id": start_frame_id,
            "carry_end_frame_id": end_frame_id,
            "carry_duration_seconds": float(evidence["carry_duration_seconds"]),
            "start_point": evidence["start_point"],
            "end_point": evidence["end_point"],
            "displacement_m": float(evidence["displacement_m"]),
            "carry_forward_progression_m": float(evidence["carry_forward_progression_m"]),
            "possession_continuity_status": evidence["possession_continuity_status"],
            "control_continuity_status": evidence["control_continuity_status"],
            "controlled_frame_ratio": float(evidence["controlled_frame_ratio"]),
            "comoving_frame_ratio": float(evidence["comoving_frame_ratio"]),
            "control_distance_m": float(evidence["control_distance_m"]),
            "nearest_teammate_margin_m": float(evidence["nearest_teammate_margin_m"]),
            "maximum_ball_player_speed_delta_mps": float(evidence["maximum_ball_player_speed_delta_mps"]),
            "minimum_displacement_m": float(evidence["minimum_displacement_m"]),
            "maximum_carry_seconds": float(evidence["maximum_carry_seconds"]),
            "claim_boundary": (
                "Observed same-player movement under control between reception and next confirmed release; "
                "does not claim dribbling skill, pressure breaking, defender bypass, intent, or decision quality."
            ),
        },
        "replay": replay,
        "visual_contract": {
            "carry_interval": ["carrier_id", "carry_start_frame_id", "carry_end_frame_id"],
            "movement": ["start_point", "end_point", "displacement_m", "carry_forward_progression_m"],
            "control": ["controlled_frame_ratio", "comoving_frame_ratio", "control_distance_m"],
            "prohibited_visual_claims": [
                "dribbling skill",
                "pressure breaking",
                "defender bypass by carry",
                "player intent",
                "decision quality",
                "tactical causation",
            ],
        },
    }


if __name__ == "__main__":
    main()
