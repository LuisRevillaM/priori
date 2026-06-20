"""Runtime value wrappers and catalog conformance checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from tqe.runtime.ir import Cardinality, CatalogOutput, EntityScope, PayloadType, TemporalContainer, Unit


@dataclass(frozen=True)
class FrameSignal:
    frame_ids: list[int]
    values: list[Any]
    unknown_mask: list[bool]
    unit: Unit
    entity_scope: EntityScope

    def __post_init__(self) -> None:
        if not (len(self.frame_ids) == len(self.values) == len(self.unknown_mask)):
            raise RuntimeError("frame signal frame_ids, values, and unknown_mask lengths must match")


@dataclass(frozen=True)
class RuntimeValue:
    output: CatalogOutput
    value: Any
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def temporal_type(self) -> TemporalContainer:
        return self.output.temporal_type

    @property
    def payload_type(self) -> PayloadType:
        return self.output.payload_type

    @property
    def cardinality(self) -> Cardinality:
        return self.output.cardinality

    @property
    def frame_values(self) -> list[Any]:
        if not isinstance(self.value, FrameSignal):
            raise RuntimeError(f"{self.output.name} is not a frame signal")
        return self.value.values


def runtime_value_from_raw(
    *,
    node_id: str,
    output: CatalogOutput,
    raw_value: Any,
    frame_ids: list[int] | None = None,
    records: list[dict[str, Any]] | None = None,
) -> RuntimeValue:
    value = normalize_value(
        node_id=node_id,
        output=output,
        raw_value=raw_value,
        frame_ids=frame_ids,
    )
    assert_value_conforms(node_id=node_id, output=output, value=value)
    return RuntimeValue(
        output=output,
        value=value,
        provenance={
            "node_id": node_id,
            "output_name": output.name,
            "temporal_type": output.temporal_type.value,
            "payload_type": output.payload_type.value,
            "unit": output.unit.value,
            "entity_scope": output.entity_scope.value,
            "records": records,
        },
    )


def normalize_value(
    *,
    node_id: str,
    output: CatalogOutput,
    raw_value: Any,
    frame_ids: list[int] | None = None,
) -> Any:
    if output.temporal_type == TemporalContainer.FRAME_SIGNAL:
        return normalize_frame_signal(
            node_id=node_id,
            output=output,
            raw_value=raw_value,
            frame_ids=frame_ids,
        )
    if isinstance(raw_value, np.ndarray):
        return raw_value.tolist()
    return raw_value


def normalize_frame_signal(
    *,
    node_id: str,
    output: CatalogOutput,
    raw_value: Any,
    frame_ids: list[int] | None = None,
) -> FrameSignal:
    if isinstance(raw_value, FrameSignal):
        return raw_value
    if isinstance(raw_value, pd.Series):
        if frame_ids is None:
            ordered = raw_value.sort_index()
            signal_frame_ids = [int(item) for item in ordered.index.tolist()]
            values = [_normalize_missing(item) for item in ordered.tolist()]
        else:
            signal_frame_ids = [int(item) for item in frame_ids]
            ordered = raw_value.reindex(signal_frame_ids)
            values = [_normalize_missing(item) for item in ordered.tolist()]
        return frame_signal_from_values(output=output, frame_ids=signal_frame_ids, values=values)
    if isinstance(raw_value, np.ndarray):
        raw_value = raw_value.tolist()
    if isinstance(raw_value, bool | int | float | str) or raw_value is None:
        signal_frame_ids = [int(frame_ids[0])] if frame_ids else [0]
        return frame_signal_from_values(output=output, frame_ids=signal_frame_ids, values=[raw_value])
    if isinstance(raw_value, list):
        if any(isinstance(item, dict | list | tuple) for item in raw_value):
            raise RuntimeError(
                f"{node_id}.{output.name} frame signal must contain scalar payload values, not structured records"
            )
        if frame_ids is not None and len(frame_ids) == len(raw_value):
            signal_frame_ids = [int(item) for item in frame_ids]
        else:
            signal_frame_ids = list(range(len(raw_value)))
        return frame_signal_from_values(output=output, frame_ids=signal_frame_ids, values=raw_value)
    raise RuntimeError(f"{node_id}.{output.name} cannot normalize {type(raw_value).__name__} as frame signal")


def frame_signal_from_values(
    *,
    output: CatalogOutput,
    frame_ids: list[int],
    values: list[Any],
) -> FrameSignal:
    normalized = [_normalize_missing(item) for item in values]
    return FrameSignal(
        frame_ids=frame_ids,
        values=normalized,
        unknown_mask=[item is None for item in normalized],
        unit=output.unit,
        entity_scope=output.entity_scope,
    )


def _normalize_missing(value: Any) -> Any:
    if value is None:
        return None
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        return value
    return value


def assert_value_conforms(*, node_id: str, output: CatalogOutput, value: Any) -> None:
    if output.temporal_type == TemporalContainer.SCALAR:
        _assert_payload(node_id=node_id, output=output, value=value)
        return
    if output.temporal_type in {
        TemporalContainer.FRAME_SIGNAL,
        TemporalContainer.EPISODE_SET,
        TemporalContainer.RELATION_EPISODE_SET,
    }:
        if output.temporal_type == TemporalContainer.FRAME_SIGNAL:
            if not isinstance(value, FrameSignal):
                raise RuntimeError(f"{node_id}.{output.name} must be a FrameSignal")
            for item in value.values:
                _assert_payload(node_id=node_id, output=output, value=item, allow_unknown=True)
            return
        if not isinstance(value, list):
            raise RuntimeError(
                f"{node_id}.{output.name} must be a list for {output.temporal_type.value}"
            )
        if output.temporal_type == TemporalContainer.EPISODE_SET:
            for item in value:
                assert_episode_record(node_id=node_id, output=output, item=item)
        elif output.temporal_type == TemporalContainer.RELATION_EPISODE_SET:
            for item in value:
                assert_relation_episode_record(node_id=node_id, output=output, item=item)
        return
    raise RuntimeError(f"Unsupported temporal type {output.temporal_type.value}")


def assert_episode_record(*, node_id: str, output: CatalogOutput, item: Any) -> None:
    if not isinstance(item, dict):
        raise RuntimeError(f"{node_id}.{output.name} episode entries must be dictionaries")
    has_standard_window = {"start_frame_id", "end_frame_id"}.issubset(item)
    has_possession_window = {"possession_start_frame_id", "possession_end_frame_id"}.issubset(item)
    has_anchor_window = "anchor_frame_id" in item or "wide_entry_frame_id" in item
    if not (has_standard_window or has_possession_window or has_anchor_window):
        raise RuntimeError(f"{node_id}.{output.name} episode entries need frame identity")


def assert_relation_episode_record(*, node_id: str, output: CatalogOutput, item: Any) -> None:
    if not isinstance(item, dict) or "relation_id" not in item:
        raise RuntimeError(f"{node_id}.{output.name} relation episodes need relation_id")
    if not (
        {"open_frame_id", "close_frame_id"}.issubset(item)
        or {"start_frame_id", "end_frame_id"}.issubset(item)
    ):
        raise RuntimeError(f"{node_id}.{output.name} relation episodes need frame window")


def _assert_payload(
    *,
    node_id: str,
    output: CatalogOutput,
    value: Any,
    allow_unknown: bool = False,
) -> None:
    if _matches_payload(output.payload_type, value, allow_unknown=allow_unknown):
        return
    raise RuntimeError(
        f"{node_id}.{output.name} does not conform to payload {output.payload_type.value}"
    )


def _matches_payload(
    payload_type: PayloadType,
    value: Any,
    *,
    allow_unknown: bool = False,
) -> bool:
    if value is None:
        return allow_unknown
    if payload_type == PayloadType.BOOLEAN and isinstance(value, bool):
        return True
    if payload_type == PayloadType.NUMBER and not isinstance(value, bool) and isinstance(
        value, int | float
    ):
        return True
    if payload_type in {
        PayloadType.ENUM,
        PayloadType.ENTITY_REF,
        PayloadType.TEAM_REF,
        PayloadType.REGION_REF,
        PayloadType.RELATION_REF,
    } and isinstance(value, str):
        return True
    if payload_type == PayloadType.POINT and isinstance(value, dict):
        if {"x_m", "y_m"}.issubset(value) and all(
            isinstance(value[key], int | float) for key in ("x_m", "y_m")
        ):
            return True
    if payload_type == PayloadType.ENTITY_SET and isinstance(value, list):
        if all(isinstance(item, str) for item in value):
            return True
    return False
