"""Identity and onset attribution for fragile-carrier episodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from tqe.runtime.ir import stable_hash


DEFINITION_VERSION = "0.1.0"
DEFINITION_HASH = stable_hash({"primitive": "fragile_carrier_episode", "version": DEFINITION_VERSION})


@dataclass(frozen=True)
class EpisodeIdentityConfig:
    same_episode_gap_tolerance_s: float = 0.40
    refractory_after_resolution_s: float = 1.00


def build_fragile_carrier_episodes(
    observations: Iterable[dict[str, Any]],
    config: EpisodeIdentityConfig = EpisodeIdentityConfig(),
) -> list[dict[str, Any]]:
    """Collapse certified pressure observations into carrier-independent IDs."""
    unique = {stable_hash(item): dict(item) for item in observations}
    ordered = sorted(unique.values(), key=_sort_key)
    groups: dict[tuple[str, int, str, str], list[dict[str, Any]]] = {}
    for item in ordered:
        key = (str(item.get("match_id")), int(item.get("period") or 0),
               str(item.get("team_role")), str(item.get("possession_id")))
        groups.setdefault(key, []).append(item)
    episodes: list[dict[str, Any]] = []
    for key, rows in groups.items():
        episodes.extend(_episodes_for_possession(key, rows, config))
    return sorted(episodes, key=lambda item: (item["onset_match_time_ms"], item["episode_id"]))


def _sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (str(item.get("match_id")), int(item.get("period") or 0),
            str(item.get("team_role")), str(item.get("possession_id")),
            int(item.get("match_time_ms") or 0), int(item.get("pressure_frame_id") or 0), stable_hash(item))


def _episodes_for_possession(
    key: tuple[str, int, str, str], rows: list[dict[str, Any]], config: EpisodeIdentityConfig
) -> list[dict[str, Any]]:
    frames: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in rows:
        frame_key = (int(row.get("match_time_ms") or 0), int(row.get("pressure_frame_id") or 0))
        frames.setdefault(frame_key, []).append(row)
    result: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    boundary_ms: int | None = None
    release_start_ms: int | None = None
    for (time_ms, frame_id), frame_rows in sorted(frames.items()):
        boundary = any(str(row.get("episode_boundary_status", "FAIL")) == "PASS" for row in frame_rows)
        statuses = {str(row.get("pressure_status", "UNKNOWN")) for row in frame_rows}
        qualified = "PASS" in statuses and any(_qualified(row) for row in frame_rows)
        certified_fail = statuses == {"FAIL"} and all(
            str(row.get("coverage_status", "PASS")) != "UNKNOWN" for row in frame_rows)
        if boundary and active is not None:
            active.update(identity_end_frame_id=frame_id, identity_end_match_time_ms=time_ms,
                          identity_boundary_kind=next((str(row.get("episode_boundary_kind"))
                          for row in frame_rows if row.get("episode_boundary_kind")), "declared_boundary"))
            boundary_ms, release_start_ms, active = time_ms, None, None
        if certified_fail:
            release_start_ms = time_ms if release_start_ms is None else release_start_ms
            continue
        if not qualified:
            if "UNKNOWN" in statuses:
                release_start_ms = None
            continue
        if active is not None:
            active["last_pressure_frame_id"] = frame_id
            active["last_pressure_match_time_ms"] = time_ms
            hashes = sorted(stable_hash(row) for row in frame_rows)
            active["source_observation_hashes"] = sorted(set(active["source_observation_hashes"] + hashes))
            active["reentry_carrier_ids"] = sorted(set(active["reentry_carrier_ids"]) | _candidates(frame_rows))
            continue
        if boundary_ms is not None:
            refractory_ok = (time_ms - boundary_ms) / 1000.0 >= config.refractory_after_resolution_s
            release_ok = release_start_ms is not None and (
                (time_ms - release_start_ms) / 1000.0 > config.same_episode_gap_tolerance_s)
            if not (refractory_ok and release_ok):
                continue
        active = _new_episode(key, time_ms, frame_id, frame_rows, config)
        result.append(active)
        release_start_ms = None
    return result


def _qualified(row: dict[str, Any]) -> bool:
    return (str(row.get("possession_status")) == "PASS"
            and str(row.get("pressure_status")) == "PASS"
            and str(row.get("coverage_status", "PASS")) != "UNKNOWN"
            and float(row.get("pressure_duration_seconds") or 0.0) + 1e-9
            >= float(row.get("minimum_pressure_duration_seconds") or 0.0))


def _candidates(rows: list[dict[str, Any]]) -> set[str]:
    values: set[str] = set()
    for row in rows:
        candidates = row.get("carrier_candidate_ids")
        if isinstance(candidates, list):
            values.update(str(value) for value in candidates if value is not None)
        elif row.get("carrier_id") is not None:
            values.add(str(row["carrier_id"]))
    return values


def _new_episode(key: tuple[str, int, str, str], time_ms: int, frame_id: int,
                 rows: list[dict[str, Any]], config: EpisodeIdentityConfig) -> dict[str, Any]:
    candidates = _candidates(rows)
    known = len(candidates) == 1 and all(
        str(row.get("carrier_control_status", "UNKNOWN")) == "PASS" for row in rows)
    source_signature = stable_hash({"primitive": "pressure_on_carrier", "version": "0.1.0",
        "parameters": [{name: row.get(name) for name in (
            "maximum_pressure_distance_m", "minimum_closing_speed_mps",
            "maximum_approach_angle_degrees", "minimum_pressure_duration_seconds", "lookback_seconds")}
            for row in rows]})
    pressure_parameter_echo = {
        name: rows[0].get(name) for name in (
            "maximum_pressure_distance_m", "minimum_closing_speed_mps",
            "maximum_approach_angle_degrees", "minimum_pressure_duration_seconds", "lookback_seconds")
    }
    preimage = {"definition_hash": DEFINITION_HASH, "pressure_source_signature": source_signature,
        "match_id": key[0], "period": key[1], "team_role": key[2], "possession_id": key[3],
        "onset_frame_id": frame_id, "onset_match_time_ms": time_ms}
    return {"episode_id": stable_hash(preimage), "definition_version": DEFINITION_VERSION,
        "definition_hash": DEFINITION_HASH, "pressure_source_signature": source_signature,
        "match_id": key[0], "period": key[1], "team_role": key[2], "possession_id": key[3],
        "onset_frame_id": frame_id, "onset_match_time_ms": time_ms,
        "last_pressure_frame_id": frame_id, "last_pressure_match_time_ms": time_ms,
        "identity_end_frame_id": None, "identity_end_match_time_ms": None,
        "identity_boundary_kind": None,
        "onset_carrier_id": next(iter(candidates)) if known else None,
        "attribution_status": "PASS" if known else "UNKNOWN",
        "attribution_reason": "unique_controlled_onset_carrier" if known else "onset_carrier_not_unique_or_control_unknown",
        "onset_carrier_candidate_ids": sorted(candidates), "reentry_carrier_ids": sorted(candidates),
        "same_episode_gap_tolerance_s": config.same_episode_gap_tolerance_s,
        "refractory_after_resolution_s": config.refractory_after_resolution_s,
        "continuity_status": "NOT_EVALUATED",
        "pressure_parameter_echo": pressure_parameter_echo,
        "source_anchor_ids": sorted({str(row["anchor_id"]) for row in rows if row.get("anchor_id")}),
        "deduplicated_source_row_count": len({stable_hash(row) for row in rows}),
        "source_observation_hashes": sorted(stable_hash(row) for row in rows)}
