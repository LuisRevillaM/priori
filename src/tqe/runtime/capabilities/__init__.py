"""Capability dispatch registry metadata.

F2-0 formalizes the registry without moving implementations.  The executor
still owns the implementation functions in this packet; this module owns the
declared mapping from catalog identifiers to implementation function names so
tests can prove the dispatch surface is explicit and complete.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib import import_module
from typing import Any

Implementation = Callable[..., None]


PRIMITIVE_IMPLEMENTATION_NAMES: tuple[tuple[str, str], ...] = (
    ("fragile_carrier_episode", "primitive_fragile_carrier_episode"),
    ("possession_segment", "primitive_possession_segment"),
    ("transition_anchor", "primitive_transition_anchor"),
    ("structured_zone", "primitive_structured_zone"),
    ("space_region_generation", "primitive_space_region_generation"),
    ("outcome_window", "primitive_outcome_window"),
    ("action_event_anchor", "primitive_action_event_anchor"),
    ("action_chain", "primitive_action_chain"),
    ("tracking_quality", "primitive_tracking_quality"),
    ("pairwise_distance", "primitive_pairwise_distance"),
    ("marking", "primitive_marking"),
    ("cover_shadow", "primitive_cover_shadow"),
    ("velocity", "primitive_velocity"),
    ("acceleration", "primitive_acceleration"),
    ("off_ball_run", "primitive_off_ball_run"),
    ("off_ball_run_type", "primitive_off_ball_run_type"),
    ("set_piece_structure", "primitive_set_piece_structure"),
    ("time_to_arrival", "primitive_time_to_arrival"),
    ("carry_episode", "primitive_carry_episode"),
    ("join_episode_sets", "primitive_join_episode_sets"),
    ("team_compactness", "primitive_team_compactness"),
    ("switch_of_play", "primitive_switch_of_play"),
    ("change_across_anchor", "primitive_change_across_anchor"),
    ("controlled_pass_episode", "primitive_controlled_pass_episode"),
    ("one_touch_relay_episode", "primitive_one_touch_relay_episode"),
    ("defensive_line_model", "primitive_defensive_line_model"),
    ("multi_line_model", "primitive_multi_line_model"),
    ("relative_position_to_line", "primitive_relative_position_to_line"),
    ("receiver_line_transition_during_pass_leg", "primitive_receiver_line_transition_during_pass_leg"),
    ("pass_chain_episode", "primitive_pass_chain_episode"),
    ("controlled_line_break_episode", "primitive_controlled_line_break_episode"),
    ("lane_occupancy", "primitive_lane_occupancy"),
    ("ball_lateral_fraction", "primitive_ball_lateral_fraction"),
    ("defensive_outfield_centroid", "primitive_defensive_outfield_centroid"),
    ("signed_lateral_shift", "primitive_signed_lateral_shift"),
    ("outcome_classification", "primitive_outcome_classification"),
    ("relation_destination_entry", "primitive_relation_destination_entry_classification"),
    ("relation_destination_entry_classification", "primitive_relation_destination_entry_classification"),
)


RELATION_IMPLEMENTATION_NAMES: tuple[tuple[str, str], ...] = (
    ("geometric_progressive_corridor", "relation_geometric_progressive_corridor"),
    ("geometric_progressive_corridor_from_anchor_set", "relation_geometric_progressive_corridor"),
    ("opponents_bypassed_by_action", "relation_opponents_bypassed_by_action"),
    ("controlled_pass_team_keyed_anchors", "relation_controlled_pass_team_keyed_anchors"),
    ("possession_segment_team_keyed_episodes", "relation_possession_segment_team_keyed_episodes"),
    ("support_arrival_relation", "relation_support_arrival"),
    ("support_arrival_point_pair", "relation_support_arrival_point_pair"),
    ("pressure_on_carrier", "relation_pressure_on_carrier"),
    ("defender_distance_candidate_set", "relation_defender_distance_candidate_set"),
    ("team_press", "relation_team_press"),
    ("local_number_relation", "relation_local_number"),
)


RELOCATED_IMPLEMENTATION_MODULES: dict[str, str] = {
    "primitive_fragile_carrier_episode": "tqe.runtime.capabilities.possession_family",
    "primitive_possession_segment": "tqe.runtime.capabilities.possession_family",
    "primitive_transition_anchor": "tqe.runtime.capabilities.possession_family",
    "primitive_structured_zone": "tqe.runtime.capabilities.possession_family",
    "primitive_space_region_generation": "tqe.runtime.capabilities.possession_family",
    "primitive_outcome_window": "tqe.runtime.capabilities.possession_family",
    "primitive_action_event_anchor": "tqe.runtime.capabilities.pass_family",
    "primitive_action_chain": "tqe.runtime.capabilities.sequence_family",
    "primitive_tracking_quality": "tqe.runtime.capabilities.kinematics_family",
    "primitive_pairwise_distance": "tqe.runtime.capabilities.kinematics_family",
    "primitive_velocity": "tqe.runtime.capabilities.kinematics_family",
    "primitive_acceleration": "tqe.runtime.capabilities.kinematics_family",
    "primitive_set_piece_structure": "tqe.runtime.capabilities.possession_family",
    "primitive_carry_episode": "tqe.runtime.capabilities.sequence_family",
    "primitive_join_episode_sets": "tqe.runtime.capabilities.kinematics_family",
    "primitive_switch_of_play": "tqe.runtime.capabilities.sequence_family",
    "primitive_controlled_pass_episode": "tqe.runtime.capabilities.pass_family",
    "primitive_one_touch_relay_episode": "tqe.runtime.capabilities.pass_family",
    "primitive_pass_chain_episode": "tqe.runtime.capabilities.sequence_family",
    "primitive_lane_occupancy": "tqe.runtime.capabilities.kinematics_family",
    "primitive_outcome_classification": "tqe.runtime.capabilities.possession_family",
    "relation_possession_segment_team_keyed_episodes": "tqe.runtime.capabilities.possession_family",
    "relation_opponents_bypassed_by_action": "tqe.runtime.capabilities.pass_family",
    "relation_controlled_pass_team_keyed_anchors": "tqe.runtime.capabilities.pass_family",
    "relation_geometric_progressive_corridor": "tqe.runtime.capabilities.corridor_family",
    "primitive_relation_destination_entry_classification": "tqe.runtime.capabilities.corridor_family",
    "primitive_defensive_line_model": "tqe.runtime.capabilities.lines_family",
    "primitive_multi_line_model": "tqe.runtime.capabilities.lines_family",
    "primitive_relative_position_to_line": "tqe.runtime.capabilities.lines_family",
    "primitive_receiver_line_transition_during_pass_leg": "tqe.runtime.capabilities.lines_family",
    "primitive_controlled_line_break_episode": "tqe.runtime.capabilities.lines_family",
    "primitive_marking": "tqe.runtime.capabilities.offball_family",
    "primitive_off_ball_run": "tqe.runtime.capabilities.offball_family",
    "primitive_off_ball_run_type": "tqe.runtime.capabilities.offball_family",
    "primitive_time_to_arrival": "tqe.runtime.capabilities.offball_family",
    "relation_support_arrival": "tqe.runtime.capabilities.offball_family",
    "relation_support_arrival_point_pair": "tqe.runtime.capabilities.offball_family",
    "primitive_team_compactness": "tqe.runtime.capabilities.teamshape_family",
    "primitive_change_across_anchor": "tqe.runtime.capabilities.teamshape_family",
    "primitive_cover_shadow": "tqe.runtime.capabilities.teamshape_family",
    "primitive_ball_lateral_fraction": "tqe.runtime.capabilities.teamshape_family",
    "primitive_defensive_outfield_centroid": "tqe.runtime.capabilities.teamshape_family",
    "primitive_signed_lateral_shift": "tqe.runtime.capabilities.teamshape_family",
    "relation_pressure_on_carrier": "tqe.runtime.capabilities.teamshape_family",
    "relation_defender_distance_candidate_set": "tqe.runtime.capabilities.teamshape_family",
    "relation_team_press": "tqe.runtime.capabilities.teamshape_family",
    "relation_local_number": "tqe.runtime.capabilities.teamshape_family",
}


def build_primitive_registry(namespace: Mapping[str, Any]) -> dict[str, Implementation]:
    return _build_registry(PRIMITIVE_IMPLEMENTATION_NAMES, namespace)


def build_relation_registry(namespace: Mapping[str, Any]) -> dict[str, Implementation]:
    return _build_registry(RELATION_IMPLEMENTATION_NAMES, namespace)


def _build_registry(
    mappings: tuple[tuple[str, str], ...],
    namespace: Mapping[str, Any],
) -> dict[str, Implementation]:
    registry: dict[str, Implementation] = {}
    for capability_name, implementation_name in mappings:
        implementation = _implementation_callable(implementation_name, namespace)
        if not callable(implementation):
            raise RuntimeError(f"Missing implementation callable {implementation_name}")
        if capability_name in registry:
            raise RuntimeError(f"Duplicate capability registration for {capability_name}")
        registry[capability_name] = implementation
    return registry


def _implementation_callable(implementation_name: str, namespace: Mapping[str, Any]) -> Any:
    module_name = RELOCATED_IMPLEMENTATION_MODULES.get(implementation_name)
    if module_name is None:
        return namespace.get(implementation_name)
    return getattr(import_module(module_name), implementation_name)
