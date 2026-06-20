"""Runtime value wrappers and catalog conformance checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from tqe.runtime.ir import Cardinality, CatalogOutput, PayloadType, TemporalContainer


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


def runtime_value_from_raw(
    *,
    node_id: str,
    output: CatalogOutput,
    raw_value: Any,
) -> RuntimeValue:
    value = normalize_value(node_id=node_id, output=output, raw_value=raw_value)
    assert_value_conforms(node_id=node_id, output=output, value=value)
    return RuntimeValue(
        output=output,
        value=value,
        provenance={"node_id": node_id, "output_name": output.name},
    )


def normalize_value(*, node_id: str, output: CatalogOutput, raw_value: Any) -> Any:
    if output.temporal_type == TemporalContainer.FRAME_SIGNAL and isinstance(
        raw_value, bool | int | float | str
    ):
        return [raw_value]
    if isinstance(raw_value, np.ndarray):
        return raw_value.tolist()
    if isinstance(raw_value, pd.Series):
        return raw_value.dropna().tolist()
    if output.temporal_type == TemporalContainer.FRAME_SIGNAL and isinstance(raw_value, list):
        if output.payload_type == PayloadType.NUMBER:
            return [
                item.get("signed_shift_metres")
                for item in raw_value
                if isinstance(item, dict) and item.get("signed_shift_metres") is not None
            ]
        if output.payload_type == PayloadType.ENUM:
            return [
                item.get("classification")
                for item in raw_value
                if isinstance(item, dict) and item.get("classification") is not None
            ]
        if output.payload_type == PayloadType.BOOLEAN:
            key = f"{node_id}_passed"
            return [
                bool(item.get(key))
                for item in raw_value
                if isinstance(item, dict) and key in item
            ]
    return raw_value


def assert_value_conforms(*, node_id: str, output: CatalogOutput, value: Any) -> None:
    if output.temporal_type == TemporalContainer.SCALAR:
        _assert_payload(node_id=node_id, output=output, value=value)
        return
    if output.temporal_type in {
        TemporalContainer.FRAME_SIGNAL,
        TemporalContainer.EPISODE_SET,
        TemporalContainer.RELATION_EPISODE_SET,
    }:
        if not isinstance(value, list):
            raise RuntimeError(
                f"{node_id}.{output.name} must be a list for {output.temporal_type.value}"
            )
        if output.temporal_type == TemporalContainer.FRAME_SIGNAL:
            for item in value:
                _assert_payload(node_id=node_id, output=output, value=item)
        elif output.temporal_type == TemporalContainer.EPISODE_SET:
            for item in value:
                if not isinstance(item, dict | list | tuple):
                    raise RuntimeError(f"{node_id}.{output.name} episode entries must be structured")
        elif output.temporal_type == TemporalContainer.RELATION_EPISODE_SET:
            for item in value:
                if not isinstance(item, dict) or "relation_id" not in item:
                    raise RuntimeError(f"{node_id}.{output.name} relation episodes need relation_id")
        return
    raise RuntimeError(f"Unsupported temporal type {output.temporal_type.value}")


def _assert_payload(*, node_id: str, output: CatalogOutput, value: Any) -> None:
    if output.payload_type == PayloadType.BOOLEAN and isinstance(value, bool):
        return
    if output.payload_type == PayloadType.NUMBER and not isinstance(value, bool) and isinstance(
        value, int | float
    ):
        return
    if output.payload_type in {
        PayloadType.ENUM,
        PayloadType.ENTITY_REF,
        PayloadType.TEAM_REF,
        PayloadType.REGION_REF,
        PayloadType.RELATION_REF,
    } and isinstance(value, str):
        return
    if output.payload_type == PayloadType.POINT and isinstance(value, dict):
        if {"x_m", "y_m"}.issubset(value) and all(
            isinstance(value[key], int | float) for key in ("x_m", "y_m")
        ):
            return
    if output.payload_type == PayloadType.ENTITY_SET and isinstance(value, list):
        if all(isinstance(item, str) for item in value):
            return
    raise RuntimeError(
        f"{node_id}.{output.name} does not conform to payload {output.payload_type.value}"
    )
