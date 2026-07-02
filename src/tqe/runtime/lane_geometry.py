"""Shared lateral lane geometry for runtime lane consumers.

The runtime uses a five-equal-lanes model over a 68m pitch width. Boundary
ties go toward the centerline, symmetrically for positive and negative y.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


LEFT_WIDE = "LEFT_WIDE"
LEFT_HALF_SPACE = "LEFT_HALF_SPACE"
CENTRAL = "CENTRAL"
RIGHT_HALF_SPACE = "RIGHT_HALF_SPACE"
RIGHT_WIDE = "RIGHT_WIDE"

DEFAULT_PITCH_WIDTH_M = 68.0
DEFAULT_TIE_EPSILON_M = 1e-9
DEFAULT_LANE_IDS = (LEFT_WIDE, LEFT_HALF_SPACE, CENTRAL, RIGHT_HALF_SPACE, RIGHT_WIDE)
BOUNDARY_POLICY = "five_equal_lanes_abs_y_ties_toward_center"
COORDINATE_SYSTEM = "centered_pitch_y_negative_left_positive_right"


@dataclass(frozen=True)
class LaneBand:
    lane_id: str
    min_y_m: float
    max_y_m: float
    includes_min_y: bool
    includes_max_y: bool
    ordinal: int


def lane_bands(pitch_width_m: float = DEFAULT_PITCH_WIDTH_M) -> tuple[LaneBand, ...]:
    """Return five equal lane bands with declared tie-to-center boundaries."""

    half_width = float(pitch_width_m) / 2.0
    lane_width = float(pitch_width_m) / len(DEFAULT_LANE_IDS)
    left_half_edge = round(-half_width + lane_width, 10)
    central_left_edge = round(-half_width + 2.0 * lane_width, 10)
    central_right_edge = round(half_width - 2.0 * lane_width, 10)
    right_half_edge = round(half_width - lane_width, 10)
    return (
        LaneBand(LEFT_WIDE, round(-half_width, 10), left_half_edge, True, False, 0),
        LaneBand(LEFT_HALF_SPACE, left_half_edge, central_left_edge, True, False, 1),
        LaneBand(CENTRAL, central_left_edge, central_right_edge, True, True, 2),
        LaneBand(RIGHT_HALF_SPACE, central_right_edge, right_half_edge, False, True, 3),
        LaneBand(RIGHT_WIDE, right_half_edge, round(half_width, 10), False, True, 4),
    )


def classify_lane_y(
    y_m: float | None,
    *,
    pitch_width_m: float = DEFAULT_PITCH_WIDTH_M,
    tie_epsilon_m: float = DEFAULT_TIE_EPSILON_M,
) -> str | None:
    """Classify a y-coordinate into the shared five-lane model."""

    if y_m is None:
        return None
    try:
        y_value = float(y_m)
        pitch_width = float(pitch_width_m)
        tie_epsilon = float(tie_epsilon_m)
    except (TypeError, ValueError):
        return None
    if not isfinite(y_value) or not isfinite(pitch_width) or not isfinite(tie_epsilon) or pitch_width <= 0.0:
        return None
    half_width = pitch_width / 2.0
    if abs(y_value) > half_width + tie_epsilon:
        return None
    lane_width = pitch_width / len(DEFAULT_LANE_IDS)
    central_edge = lane_width / 2.0
    half_space_edge = central_edge + lane_width
    abs_y = abs(y_value)
    if abs_y <= central_edge + tie_epsilon:
        return CENTRAL
    if abs_y <= half_space_edge + tie_epsilon:
        return RIGHT_HALF_SPACE if y_value > 0.0 else LEFT_HALF_SPACE
    return RIGHT_WIDE if y_value > 0.0 else LEFT_WIDE


def lane_family(lane_id: str) -> str:
    if lane_id == CENTRAL:
        return "central"
    if lane_id in {LEFT_HALF_SPACE, RIGHT_HALF_SPACE}:
        return "half_space"
    if lane_id in {LEFT_WIDE, RIGHT_WIDE}:
        return "wide"
    raise ValueError(f"Unsupported lane_id {lane_id}")


def lane_side(lane_id: str) -> str:
    if lane_id == CENTRAL:
        return "central"
    if lane_id in {LEFT_HALF_SPACE, LEFT_WIDE}:
        return "left"
    if lane_id in {RIGHT_HALF_SPACE, RIGHT_WIDE}:
        return "right"
    raise ValueError(f"Unsupported lane_id {lane_id}")


def lane_bounds(lane_id: str, pitch_width_m: float = DEFAULT_PITCH_WIDTH_M) -> dict[str, float]:
    for band in lane_bands(pitch_width_m):
        if band.lane_id == lane_id:
            return {"min_y_m": round(float(band.min_y_m), 3), "max_y_m": round(float(band.max_y_m), 3)}
    raise ValueError(f"Unsupported lane_id {lane_id}")


def lane_id_for_side_family(destination_side: str, destination_lane: str) -> str:
    if destination_lane == "central":
        return CENTRAL
    if destination_side == "left" and destination_lane == "half_space":
        return LEFT_HALF_SPACE
    if destination_side == "right" and destination_lane == "half_space":
        return RIGHT_HALF_SPACE
    if destination_side == "left" and destination_lane == "wide":
        return LEFT_WIDE
    if destination_side == "right" and destination_lane == "wide":
        return RIGHT_WIDE
    raise ValueError(f"Unsupported side/lane pair {destination_side}/{destination_lane}")


def partition_metadata(pitch_width_m: float = DEFAULT_PITCH_WIDTH_M) -> dict[str, object]:
    return {
        "model": "five_equal_lanes",
        "pitch_width_m": float(pitch_width_m),
        "lane_count": len(DEFAULT_LANE_IDS),
        "lane_width_m": float(pitch_width_m) / len(DEFAULT_LANE_IDS),
        "boundary_policy": BOUNDARY_POLICY,
        "tie_epsilon_m": DEFAULT_TIE_EPSILON_M,
        "coordinate_system": COORDINATE_SYSTEM,
        "lane_ids": list(DEFAULT_LANE_IDS),
        "bands": [band.__dict__ for band in lane_bands(pitch_width_m)],
    }
