"""Generate the Workbench case-study part-two replay bundle."""

from __future__ import annotations

import json
import math
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
from tqe.runtime.controlled_pass import ControlledPassConfig  # noqa: E402
from tqe.runtime.executor import (  # noqa: E402
    TacticalQueryExecutor,
    execute_default_plan,
    execution_result_rows,
    runtime_parameters,
)
from tqe.runtime.ir import TacticalQueryDocument  # noqa: E402
from tqe.runtime.lane_geometry import partition_metadata  # noqa: E402
from tqe.runtime.relations import evaluate_geometric_progressive_corridors  # noqa: E402

OUT_PATH = REPO_ROOT / "apps/workbench-alpha/public/case-study-part-two-replays.json"
N1I_ORIGIN_BUNDLE = REPO_ROOT / "delivery/n1d/n1f-origin-bundle.json"
PITCH = {"length_m": 105.0, "width_m": 68.0, "coordinate_contract": "centered_metres"}
REVIEW_VERIFIED_TWELFTH_RESULT_ID = "854d129b6d14f7dd"


def main() -> None:
    canonical_root = Path(os.environ.get("TQE_DATA_ROOT", "data/canonical/v1"))
    raw_root = Path(os.environ.get("TQE_RAW_ROOT", "data/raw/idsse/figshare-28196177-v1"))
    payload = {
        "schema_version": "case_study_part_two_replay_packet.v0",
        "generated_from": {
            "canonical_root": str(canonical_root),
            "raw_root": str(raw_root),
            "script": str(Path(__file__).relative_to(REPO_ROOT)),
        },
        "exhibits": {
            "controlled_unknown": controlled_unknown_payload(canonical_root, raw_root),
            "corridor_duration": corridor_duration_payload(canonical_root),
            "twelfth_hero": twelfth_hero_payload(canonical_root, raw_root),
            "lane_partition": lane_partition_payload(),
        },
        "genealogy": [
            {
                "count": 14,
                "label": "June attestation",
                "cause": "Corridor duration still used pass-frame count.",
            },
            {
                "count": 11,
                "label": "Elapsed duration",
                "cause": "Three corridors that looked like 0.8s were honestly 0.6s.",
            },
            {
                "count": 12,
                "label": "Unified lanes",
                "cause": "One possession qualifies under the declared five-lane partition.",
            },
        ],
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(clean_json(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "path": str(OUT_PATH.relative_to(REPO_ROOT)),
                "controlled_unknown": payload["exhibits"]["controlled_unknown"]["moment"]["pass_episode_id"],
                "corridor_relation": payload["exhibits"]["corridor_duration"]["moment"]["relation_id"],
                "hero_relation": payload["exhibits"]["twelfth_hero"]["moment"]["relation_id"],
                "hero_live_count": payload["exhibits"]["twelfth_hero"]["moment"]["live_result_count"],
            },
            sort_keys=True,
        )
    )


def controlled_unknown_payload(canonical_root: Path, raw_root: Path) -> dict[str, Any]:
    document = controlled_pass_probe_document("Play_Pass")
    bound = bind_document(TacticalQueryDocument.model_validate(document))
    params = runtime_parameters(bound)
    executor = TacticalQueryExecutor(canonical_root=canonical_root, raw_root=raw_root, enable_node_cache=False)
    records: list[dict[str, Any]] = []
    for period in bound.periods:
        state = executor._execute_period(  # noqa: SLF001 - generation mirrors existing verifier probes.
            bound_plan=bound,
            match_id="J03WOY",
            period=period,
            params=params,
        )
        records.extend(state.signals["controlled"]["candidate_evaluations_records"])
    candidates = [
        record
        for record in records
        if record.get("event_type") == "Play_Pass"
        and record.get("controlled_pass_status") == "UNKNOWN"
        and record.get("release_detection_reason") == "release_not_confirmed"
    ]
    if not candidates:
        raise RuntimeError("No J03WOY Play_Pass release_not_confirmed UNKNOWN controlled-pass candidate found.")
    candidate = sorted(candidates, key=lambda item: (str(item["period"]), float(item["gameclock_seconds"])))[0]
    anchor_frame_id = int(candidate["event_anchor_frame_id"])
    config = ControlledPassConfig()
    search_start_frame_id = max(0, anchor_frame_id - math.ceil(config.release_search_before_seconds * FRAME_RATE_HZ))
    search_end_frame_id = anchor_frame_id + math.ceil(config.release_search_after_seconds * FRAME_RATE_HZ)
    replay = replay_window(
        canonical_root=canonical_root,
        match_id=str(candidate["match_id"]),
        period=str(candidate["period"]),
        start_frame_id=max(0, search_start_frame_id - 20),
        end_frame_id=search_end_frame_id + 20,
        raw_root=None,
    )
    return {
        "schema_version": "case_study_part_two.controlled_unknown.v0",
        "moment": {
            "match_id": candidate["match_id"],
            "period": candidate["period"],
            "team_role": candidate["team_role"],
            "event_type": candidate["event_type"],
            "event_row_index": candidate["event_row_index"],
            "pass_episode_id": candidate["pass_episode_id"],
            "passer_id": candidate["passer_id"],
            "receiver_id": candidate["receiver_id"],
            "anchor_frame_id": anchor_frame_id,
            "gameclock_seconds": round(float(candidate["gameclock_seconds"]), 3),
            "status": candidate["controlled_pass_status"],
            "release_detection_status": candidate["release_detection_status"],
            "release_detection_reason": candidate["release_detection_reason"],
            "controlled_reception_status": candidate["controlled_reception_status"],
            "old_semantics": "release_not_confirmed was part of the old FAIL bucket",
            "search_window": {
                "start_frame_id": search_start_frame_id,
                "end_frame_id": search_end_frame_id,
                "release_search_before_seconds": config.release_search_before_seconds,
                "release_search_after_seconds": config.release_search_after_seconds,
            },
        },
        "replay": replay,
    }


def corridor_duration_payload(canonical_root: Path) -> dict[str, Any]:
    _bound, execution = execute_default_plan()
    rows = execution_result_rows(execution)
    report = evaluate_geometric_progressive_corridors(results=rows, canonical_root=canonical_root)
    candidates = [
        episode
        for episode in report["episodes"]
        if abs(float(episode["duration_seconds"]) - 0.6) < 1e-9
        and int(episode.get("pass_frame_count") or 0) == 4
    ]
    if not candidates:
        raise RuntimeError("No 0.6s / four-pass-frame corridor episode found.")
    episode = sorted(
        candidates,
        key=lambda item: (
            str(item["match_id"]),
            str(item["period"]),
            int(item["open_frame_id"]),
            str(item["relation_id"]),
        ),
    )[0]
    replay = replay_window(
        canonical_root=canonical_root,
        match_id=str(episode["match_id"]),
        period=str(episode["period"]),
        start_frame_id=max(0, int(episode["open_frame_id"]) - 20),
        end_frame_id=int(episode["close_frame_id"]) + 25,
        raw_root=None,
    )
    old_counted_duration_seconds = round(int(episode["pass_frame_count"]) / 5.0, 3)
    return {
        "schema_version": "case_study_part_two.corridor_duration.v0",
        "moment": {
            **episode,
            "old_counted_duration_seconds": old_counted_duration_seconds,
            "honest_elapsed_duration_seconds": float(episode["duration_seconds"]),
            "old_threshold_seconds": 0.8,
            "duration_fix": "old pass_frame_count / 5Hz counted four states as 0.8s; elapsed frame span is 0.6s",
        },
        "replay": replay,
    }


def twelfth_hero_payload(canonical_root: Path, raw_root: Path) -> dict[str, Any]:
    document = n1i_attested_document()
    bound = bind_document(TacticalQueryDocument.model_validate(document))
    params = runtime_parameters(bound)
    executor = TacticalQueryExecutor(canonical_root=canonical_root, raw_root=raw_root, enable_node_cache=False)
    state = executor._execute_period(  # noqa: SLF001 - generation needs relation episodes for the visual.
        bound_plan=bound,
        match_id="J03WOY",
        period="firstHalf",
        params=params,
    )
    execution_rows = execution_result_rows(executor.execute(bound))
    # DOC-1 round-1 review verified this result id by diffing the archived
    # F1-C-era engine (`d006780`, 11 rows) against the live F1-D engine
    # (12 rows). The exhibit must show that set-difference row, not a
    # heuristic lane-boundary proxy.
    final_row = next(
        (row for row in execution_rows if str(row["result_id"]) == REVIEW_VERIFIED_TWELFTH_RESULT_ID),
        None,
    )
    if final_row is None:
        raise RuntimeError(f"Verified twelfth hero result {REVIEW_VERIFIED_TWELFTH_RESULT_ID} not found.")
    verified_relation_id = str(final_row["requested_evidence"]["relation_id"])
    entry = next(
        (
            record
            for record in state.signals["destination_entry"]["entry_status_records"]
            if str(record.get("entry_status")) == "PASS"
            and str(record.get("relation_id")) == verified_relation_id
        ),
        None,
    )
    if entry is None:
        raise RuntimeError(f"Entry evidence for verified relation {verified_relation_id} not found.")
    episode = next(
        item
        for item in state.signals["progressive_corridor"]["episodes"]
        if str(item["relation_id"]) == str(entry["relation_id"])
    )
    replay = replay_window(
        canonical_root=canonical_root,
        match_id=str(entry["match_id"]),
        period=str(entry["period"]),
        start_frame_id=max(0, min(int(entry["anchor_frame_id"]), int(entry["relation_open_frame_id"])) - 20),
        end_frame_id=max(int(entry["relation_close_frame_id"]), int(entry["destination_entry_frame_id"])) + 40,
        raw_root=None,
    )
    return {
        "schema_version": "case_study_part_two.twelfth_hero.v0",
        "moment": {
            **entry,
            "final_result_id": final_row["result_id"],
            "live_result_count": len(execution_rows),
            "hero_genealogy": "14 -> 11 -> 12",
            "set_difference_provenance": {
                "archived_f1c_engine_commit": "d006780",
                "review_commit": "283dd42",
                "added_result_id": REVIEW_VERIFIED_TWELFTH_RESULT_ID,
                "added_relation_id": verified_relation_id,
            },
            "unified_lane_note": "The destination point is the reviewed set-difference row admitted after lane unification.",
            "relation_episode": episode,
        },
        "replay": replay,
    }


def lane_partition_payload() -> dict[str, Any]:
    metadata = partition_metadata()
    return {
        "schema_version": "case_study_part_two.lane_partition.v0",
        "moment": {
            "marker_y_m": 8.0,
            "old_fractional_model": "old fractional destination model",
            "old_fractional_abs_central_bound_m": 11.22,
            "old_fractional_classification": "central",
            "old_occupancy_model": "old lane occupancy model",
            "old_occupancy_classification": "RIGHT_HALF_SPACE",
            "current_model": "five_equal_lanes_abs_y_ties_toward_center",
            "current_classification": "right_half_space",
            "current_band_min_y_m": 6.8,
            "current_band_max_y_m": 20.4,
        },
        "partition": metadata,
        "replay": {"pitch": PITCH, "frames": []},
    }


def n1i_attested_document() -> dict[str, Any]:
    bundle = json.loads(N1I_ORIGIN_BUNDLE.read_text(encoding="utf-8"))
    return bundle["host_augmentation"]["augmented_document"]


def controlled_pass_probe_document(event_type_filter: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": "case_study_part_two_controlled_probe_v1",
            "recipe_version": "0.0.0-doc",
            "display_name": "Case Study Controlled Pass Probe",
            "description": "Documentation-only controlled-pass probe.",
            "default_unknown_evidence_policy": "include_with_warning",
            "allowed_claims": [],
            "disallowed_claims": [],
            "limitations": [],
            "output_classifications": ["STATUS_PASS"],
            "parameters": [],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": "case_study_part_two_controlled_probe",
            "match_ids": ["J03WOY"],
            "periods": ["firstHalf", "secondHalf"],
            "perspective_team_role": "home",
            "parameters": {},
            "max_results": 100,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": "case_study_part_two_controlled_probe",
            "plan_version": "0.0.0-doc",
            "recipe_id": "case_study_part_two_controlled_probe_v1",
            "recipe_version": "0.0.0-doc",
            "status": "experimental",
            "unknown_evidence_policy": "include_with_warning",
            "classification_mode": "partial_declared",
            "nodes": [
                {
                    "kind": "primitive",
                    "node_id": "controlled",
                    "catalog_ref": "controlled_pass_episode",
                    "version": "0.1.0",
                    "parameters": {
                        "event_type_filter": {
                            "payload_type": "enum",
                            "unit": "none",
                            "value": event_type_filter,
                        },
                    },
                },
                {
                    "kind": "predicate",
                    "node_id": "status_pass",
                    "input": {"source_node_id": "controlled", "output_name": "controlled_pass_status"},
                    "operator": {"name": "eq", "version": "1.0.0"},
                    "compare": {"payload_type": "enum", "unit": "none", "value": "PASS"},
                },
            ],
            "classification_rules": [
                {"label": "STATUS_PASS", "predicate_ids": ["status_pass"], "description": "Status is PASS."}
            ],
            "anchor_source": {"source_node_id": "controlled", "output_name": "anchors"},
            "requested_evidence": [],
        },
    }


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): clean_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_json(item) for item in value]
    if isinstance(value, tuple):
        return [clean_json(item) for item in value]
    if hasattr(value, "item"):
        return clean_json(value.item())
    return value


if __name__ == "__main__":
    main()
