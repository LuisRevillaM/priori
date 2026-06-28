"""Generate the Workbench Moment-0 line-break replay bundle."""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import pyarrow.compute as pc
import pyarrow.parquet as pq
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tqe.runtime.binder import bind_document  # noqa: E402
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows  # noqa: E402
from tqe.runtime.ir import TacticalQueryDocument, stable_hash  # noqa: E402
from tqe.runtime.pass_bypass import attack_x_sign_for  # noqa: E402

PLAN_PATH = REPO_ROOT / "config/query-plans/q3_receiver_second_line_no_underneath_support.experimental.v1.json"
OUT_PATH = REPO_ROOT / "apps/workbench-alpha/src/generated/moment-zero.json"
FRAME_RATE_HZ = 25
PITCH = {"length_m": 105.0, "width_m": 68.0, "coordinate_contract": "centered_metres"}


def main() -> None:
    canonical_root = Path(os.environ.get("TQE_DATA_ROOT", "data/canonical/v1"))
    document_payload = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    bound_plan = bind_document(TacticalQueryDocument.model_validate(document_payload))
    execution = TacticalQueryExecutor().execute(bound_plan)
    rows = execution_result_rows(execution)
    moment = next(
        row
        for row in rows
        if row["requested_evidence"].get("support_arrival_status") == "FAIL"
        and row["requested_evidence"].get("line_break_status") == "PASS"
        and row["requested_evidence"].get("coverage_status") == "COMPLETE"
    )
    evidence = moment["requested_evidence"]
    release_frame_id = int(evidence["physical_release_frame_id"])
    reception_frame_id = int(evidence["controlled_reception_frame_id"])
    support_window_end_frame_id = reception_frame_id + math.ceil(float(evidence["maximum_arrival_seconds"]) * FRAME_RATE_HZ)
    start_frame_id = max(release_frame_id - 20, 0)
    end_frame_id = support_window_end_frame_id + 18
    replay = replay_window(
        canonical_root=canonical_root,
        match_id=str(moment["match_id"]),
        period=str(moment["period"]),
        start_frame_id=start_frame_id,
        end_frame_id=end_frame_id,
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
    payload = {
        "schema_version": "moment_zero.line_break_no_underneath_support.v0",
        "source_plan": {
            "path": str(PLAN_PATH.relative_to(REPO_ROOT)),
            "document_hash": stable_hash(document_payload),
            "plan_id": bound_plan.plan_id,
        },
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
            "requested_evidence": evidence,
        },
        "replay": replay,
        "visual_contract": {
            "defensive_line": ["line_x_m", "observed_lines", "defensive_line_player_ids"],
            "pass_path": ["physical_release_frame_id", "controlled_reception_frame_id", "pass_episode_id"],
            "receiver_crossing": ["receiver_id", "release_relative_position_status", "reception_relative_position_status"],
            "empty_support_region": [
                "support_region_mode",
                "maximum_support_distance_m",
                "supporting_player_ids",
                "support_arrival_status",
                "coverage_status",
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
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(OUT_PATH.relative_to(REPO_ROOT)), "result_id": moment["result_id"], "frame_count": len(replay["frames"])}, sort_keys=True))


def replay_window(*, canonical_root: Path, match_id: str, period: str, start_frame_id: int, end_frame_id: int) -> dict[str, Any]:
    frame_path = canonical_root / "frames" / f"match_id={match_id}" / f"period={period}.parquet"
    position_path = canonical_root / "positions" / f"match_id={match_id}" / f"period={period}.parquet"
    frames = filter_frame_window(pq.ParquetFile(frame_path).read(), start_frame_id, end_frame_id)
    positions = filter_frame_window(pq.ParquetFile(position_path).read(), start_frame_id, end_frame_id)
    positions_by_frame: dict[int, list[dict[str, Any]]] = {}
    for row in positions.to_pylist():
        positions_by_frame.setdefault(int(row["frame_id"]), []).append(
            {
                "team_id": row["team_id"],
                "team_role": row["team_role"],
                "entity_id": row["entity_id"],
                "entity_type": row["entity_type"],
                "x_m": round(float(row["x_m"]), 3),
                "y_m": round(float(row["y_m"]), 3),
            }
        )
    replay_frames = []
    for frame in frames.to_pylist():
        frame_id = int(frame["frame_id"])
        replay_frames.append(
            {
                "frame_id": frame_id,
                "timestamp_utc": frame.get("timestamp_utc"),
                "entities": positions_by_frame.get(frame_id, []),
            }
        )
    return {
        "schema_version": "1.0",
        "replay_window_id": f"moment_zero_{match_id}_{period}_{start_frame_id}_{end_frame_id}",
        "source_kind": "result",
        "source_id": "moment_zero",
        "match_id": match_id,
        "period": period,
        "frame_rate_hz": FRAME_RATE_HZ,
        "generated_at": "deterministic_from_q3_plan",
        "start_frame_id": start_frame_id,
        "end_frame_id": end_frame_id,
        "anchor_frame_id": replay_frames[min(len(replay_frames) - 1, max(0, FRAME_RATE_HZ * 3))]["frame_id"],
        "pitch": PITCH,
        "canonical_sources": {
            "frames": canonical_source_id(frame_path, canonical_root),
            "positions": canonical_source_id(position_path, canonical_root),
            "frames_sha256": sha256_file(frame_path),
            "positions_sha256": sha256_file(position_path),
        },
        "frames": replay_frames,
    }


def filter_frame_window(table: Any, start_frame_id: int, end_frame_id: int) -> Any:
    mask = pc.and_(
        pc.greater_equal(table["frame_id"], start_frame_id),
        pc.less_equal(table["frame_id"], end_frame_id),
    )
    return table.filter(mask)


def pass_actor_ids(pass_episode_id: str) -> tuple[str, str]:
    parts = pass_episode_id.split(":")
    if len(parts) < 2:
        raise ValueError(f"Unexpected pass episode id: {pass_episode_id}")
    return parts[-2], parts[-1]


def entity_point_at_frame(frames: list[dict[str, Any]], frame_id: int, entity_id: str) -> dict[str, float]:
    for frame in frames:
        if int(frame["frame_id"]) != frame_id:
            continue
        for entity in frame["entities"]:
            if entity["entity_id"] == entity_id:
                return {"x_m": float(entity["x_m"]), "y_m": float(entity["y_m"])}
    raise RuntimeError(f"Missing {entity_id} at frame {frame_id}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_source_id(path: Path, canonical_root: Path) -> str:
    return str(Path("data/canonical/v1") / path.relative_to(canonical_root))


if __name__ == "__main__":
    main()
