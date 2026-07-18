from __future__ import annotations

from copy import deepcopy
import unittest

from tqe.runtime.catalog import default_catalog
from tqe.runtime.fragile_carrier_episode import build_fragile_carrier_episodes


def obs(t: int, status: str = "PASS", carrier: str | None = "p1", **extra):
    row = {"match_id": "m1", "period": 1, "team_role": "home", "possession_id": "pos1",
        "pressure_frame_id": t // 40, "match_time_ms": t, "pressure_status": status,
        "coverage_status": "PASS", "carrier_id": carrier, "carrier_control_status": "PASS",
        "pressure_duration_seconds": 0.4, "minimum_pressure_duration_seconds": 0.4,
        "maximum_pressure_distance_m": 4.0, "minimum_closing_speed_mps": 0.2,
        "maximum_approach_angle_degrees": 100.0, "lookback_seconds": 0.4}
    row.update(extra)
    return row


class FragileCarrierEpisodeTests(unittest.TestCase):
    def test_frame_farming_duplicate_and_order_attacks_do_not_multiply_identity(self):
        rows = [obs(t) for t in (0, 40, 80, 120)]
        expected = build_fragile_carrier_episodes(rows)
        farmed = build_fragile_carrier_episodes(list(reversed(rows)) + [deepcopy(rows[0])] * 20)
        assert len(expected) == len(farmed) == 1
        assert expected[0]["episode_id"] == farmed[0]["episode_id"]
    
    
    def test_flicker_and_unknown_do_not_rearm_episode(self):
        rows = [obs(0), obs(200, "FAIL"), obs(440), obs(600, "UNKNOWN"), obs(900)]
        episodes = build_fragile_carrier_episodes(rows)
        assert len(episodes) == 1
        assert episodes[0]["onset_match_time_ms"] == 0
    
    
    def test_boundary_requires_refractory_and_certified_release_both(self):
        rows = [obs(0), obs(100, episode_boundary_status="PASS"), obs(200),
                obs(300, "FAIL"), obs(800, "FAIL"), obs(1200)]
        episodes = build_fragile_carrier_episodes(rows)
        assert len(episodes) == 2
        assert episodes[0]["identity_end_match_time_ms"] == 100
        assert episodes[1]["onset_match_time_ms"] == 1200
        assert all(item["continuity_status"] == "NOT_EVALUATED" for item in episodes)
    
    
    def test_continuous_pressure_across_boundary_never_rearms_by_time_alone(self):
        rows = [obs(0), obs(100, episode_boundary_status="PASS"), obs(1200), obs(3000)]
        assert len(build_fragile_carrier_episodes(rows)) == 1
    
    
    def test_ambiguous_onset_carrier_stays_in_ledger_with_unknown_attribution(self):
        rows = [obs(0, carrier=None, carrier_candidate_ids=["p1", "p2"]), obs(40, carrier="p1")]
        episode = build_fragile_carrier_episodes(rows)[0]
        assert episode["attribution_status"] == "UNKNOWN"
        assert episode["onset_carrier_id"] is None
        assert episode["onset_carrier_candidate_ids"] == ["p1", "p2"]
    
    
    def test_later_carrier_cannot_steal_frozen_onset_attribution(self):
        episode = build_fragile_carrier_episodes([obs(0, carrier="p1"), obs(40, carrier="p2")])[0]
        assert episode["onset_carrier_id"] == "p1"
        assert episode["reentry_carrier_ids"] == ["p1", "p2"]
    
    
    def test_entry_dwell_is_reused_from_certified_pressure_echo(self):
        rows = [obs(0, pressure_duration_seconds=0.2), obs(400, pressure_duration_seconds=0.4)]
        assert build_fragile_carrier_episodes(rows)[0]["onset_match_time_ms"] == 400
    
    
    def test_possessions_are_distinct_and_carrier_is_not_part_of_id_preimage(self):
        assert len(build_fragile_carrier_episodes([obs(0), obs(0, possession_id="pos2")])) == 2
        assert (build_fragile_carrier_episodes([obs(0, carrier="other")])[0]["episode_id"]
                == build_fragile_carrier_episodes([obs(0)])[0]["episode_id"])
    
    
    def test_catalog_has_only_car_owned_identity_timing_parameters(self):
        entry = next(item for item in default_catalog().primitives if item.name == "fragile_carrier_episode")
        numeric = {p.name for p in entry.parameters if p.payload_type.value == "number"}
        assert numeric == {"same_episode_gap_tolerance_s", "refractory_after_resolution_s"}
        refs = {p.name: p.field_reference_kind.value for p in entry.parameters if p.payload_type.value == "field_ref"}
        assert refs == {"observation_frame_field": "frame", "onset_carrier_id_field": "entity",
            "possession_id_field": "provenance", "pressure_status_field": "status",
            "carrier_control_status_field": "status", "boundary_status_field": "status"}
