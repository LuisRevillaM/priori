"""Shared possession-identity helpers for runtime evidence."""

from __future__ import annotations

from typing import Any


_DEFAULT_UNOBSERVED = object()


def possession_identity_at_frame(
    state: Any,
    frame_id: int,
    team_role: str,
    *,
    unobserved_value: str | None | object = _DEFAULT_UNOBSERVED,
) -> str | None:
    """Return the observed same-team possession segment identity at a frame."""

    frame_ids = _sequence(getattr(state, "frame_ids", None))
    possession_role = _sequence(getattr(state, "possession_role", None))
    ball_alive = _sequence(getattr(state, "ball_alive", None))
    if not frame_ids or not possession_role or len(frame_ids) != len(possession_role):
        return _unobserved_identity(state, frame_id, team_role, unobserved_value)

    try:
        index = next(idx for idx, value in enumerate(frame_ids) if int(value) == int(frame_id))
    except StopIteration:
        return _unobserved_identity(state, frame_id, team_role, unobserved_value)

    if str(possession_role[index]) != str(team_role):
        return _unobserved_identity(state, frame_id, team_role, unobserved_value)
    if ball_alive and not bool(ball_alive[index]):
        return _unobserved_identity(state, frame_id, team_role, unobserved_value)

    start = index
    while start > 0 and str(possession_role[start - 1]) == str(team_role):
        if ball_alive and not bool(ball_alive[start - 1]):
            break
        start -= 1
    match_id = str(getattr(state, "match_id", ""))
    period = str(getattr(state, "period", ""))
    return f"possession:{match_id}:{period}:{team_role}:{int(frame_ids[start])}"


def _sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value)


def _unobserved_identity(
    state: Any,
    frame_id: int,
    team_role: str,
    unobserved_value: str | None | object,
) -> str | None:
    if unobserved_value is not _DEFAULT_UNOBSERVED:
        return unobserved_value  # type: ignore[return-value]
    match_id = str(getattr(state, "match_id", ""))
    period = str(getattr(state, "period", ""))
    return f"possession:{match_id}:{period}:{team_role}:unobserved:{int(frame_id)}"
