"""Tri-state CAR fragile-state eligibility over certified episode evidence."""

from __future__ import annotations

from typing import Any, Iterable

from tqe.runtime.ir import stable_hash


DEFINITION_VERSION = "0.1.0"
DEFINITION_HASH = stable_hash({"primitive": "fragile_state_eligibility", "version": DEFINITION_VERSION})


def evaluate_fragile_state_eligibility(
    episodes: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Evaluate eligibility without recreating pressure or episode geometry."""
    evaluations: list[dict[str, Any]] = []
    for raw in episodes:
        episode = dict(raw)
        status, reason = _status_and_reason(episode)
        evaluations.append({
            **episode,
            "fragile_state_eligibility_id": stable_hash({
                "definition_hash": DEFINITION_HASH,
                "episode_id": episode.get("episode_id"),
            }),
            "fragile_state_eligibility_version": DEFINITION_VERSION,
            "fragile_state_eligibility_definition_hash": DEFINITION_HASH,
            "fragile_state_status": status,
            "fragile_state_reason": reason,
            "entry_dwell_seconds": _entry_dwell(episode),
            "same_episode_gap_tolerance_s": episode.get("same_episode_gap_tolerance_s"),
            "pressure_source_signature": episode.get("pressure_source_signature"),
            "optional_context_required": False,
            "continuity_status": "NOT_EVALUATED",
        })
    return sorted(evaluations, key=lambda item: (
        str(item.get("match_id")), int(item.get("period") or 0),
        str(item.get("team_role")), int(item.get("onset_match_time_ms") or 0),
        str(item.get("episode_id")),
    ))


def _entry_dwell(episode: dict[str, Any]) -> float | None:
    echo = episode.get("pressure_parameter_echo")
    if not isinstance(echo, dict):
        return None
    value = echo.get("minimum_pressure_duration_seconds")
    return None if value is None else float(value)


def _status_and_reason(episode: dict[str, Any]) -> tuple[str, str]:
    if not episode.get("episode_id"):
        return "UNKNOWN", "episode_identity_missing"
    if str(episode.get("definition_version")) != "0.1.0":
        return "UNKNOWN", "episode_definition_not_certified"
    if str(episode.get("coverage_status", "PASS")) == "UNKNOWN":
        return "UNKNOWN", "pressure_coverage_unknown"
    if not episode.get("pressure_source_signature"):
        return "UNKNOWN", "pressure_source_signature_missing"
    if _entry_dwell(episode) is None:
        return "UNKNOWN", "pressure_entry_dwell_echo_missing"
    gap = episode.get("same_episode_gap_tolerance_s")
    if gap is None or float(gap) < 0.0:
        return "UNKNOWN", "episode_gap_tolerance_missing_or_invalid"
    attribution = str(episode.get("attribution_status", "UNKNOWN"))
    carrier = episode.get("onset_carrier_id")
    candidates = episode.get("onset_carrier_candidate_ids")
    if attribution == "UNKNOWN" or carrier is None:
        return "UNKNOWN", str(episode.get("attribution_reason") or "onset_carrier_unknown")
    if attribution != "PASS" or not isinstance(candidates, list) or len(candidates) != 1:
        return "UNKNOWN", "onset_control_evidence_ambiguous"
    return "PASS", "certified_possession_control_and_pressure"
