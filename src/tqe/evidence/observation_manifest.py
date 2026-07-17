"""Observation-coverage law for absence-sensitive runtime evidence.

An observation manifest certifies that a producer covered a modality over a
declared match-period frame interval.  It does not claim that an event occurred
or that a player was present.  It only licenses the runtime to treat an absence
inside the certified interval as negative evidence.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ObservationModality(StrEnum):
    EVENT = "event"
    BALL = "ball"
    POSSESSION = "possession"
    PLAYER_TRACK = "player_track"


class ObservationWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start_frame_id: int = Field(ge=0)
    end_frame_id: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_order(self) -> ObservationWindow:
        if self.end_frame_id < self.start_frame_id:
            raise ValueError("observation window end_frame_id precedes start_frame_id")
        return self


class ObservationCoverageRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    row_id: str = Field(min_length=1)
    modality: ObservationModality
    match_id: str = Field(min_length=1)
    period: str = Field(min_length=1)
    window: ObservationWindow
    status: Literal["CERTIFIED", "UNCERTIFIED"]
    reason: str = Field(min_length=1)
    provenance_token: str = Field(min_length=1)


class ObservationManifestDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["tqe.observation_manifest.v1"]
    manifest_id: str = Field(min_length=1)
    producer: str = Field(min_length=1)
    rows: tuple[ObservationCoverageRow, ...]

    @model_validator(mode="after")
    def validate_rows(self) -> ObservationManifestDocument:
        row_ids = [row.row_id for row in self.rows]
        if len(row_ids) != len(set(row_ids)):
            raise ValueError("observation manifest row_id values must be unique")
        by_scope: dict[tuple[ObservationModality, str, str], list[ObservationCoverageRow]] = {}
        for row in self.rows:
            by_scope.setdefault((row.modality, row.match_id, row.period), []).append(row)
        for scope, rows in by_scope.items():
            ordered = sorted(rows, key=lambda row: row.window.start_frame_id)
            for previous, current in zip(ordered, ordered[1:], strict=False):
                if current.window.start_frame_id <= previous.window.end_frame_id:
                    raise ValueError(f"observation manifest rows overlap for scope {scope}")
        return self


@dataclass(frozen=True)
class CoverageDecision:
    modality: ObservationModality
    match_id: str
    period: str
    window: ObservationWindow
    certified: bool
    reason: str
    row_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class AbsenceGateDecision:
    status: str
    reason: str
    coverage: tuple[CoverageDecision, ...]


class ObservationCoverage:
    """Fail-closed coverage lookup over one observation manifest."""

    def __init__(
        self,
        document: ObservationManifestDocument | None,
        *,
        manifest_path: Path | None,
        unavailable_reason: str | None = None,
    ) -> None:
        self.document = document
        self.manifest_path = manifest_path
        self.unavailable_reason = unavailable_reason

    @classmethod
    def from_path(cls, path: Path | None) -> ObservationCoverage:
        if path is None or not path.is_file():
            return cls(
                None,
                manifest_path=path,
                unavailable_reason="observation_manifest_absent",
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            document = ObservationManifestDocument.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            return cls(
                None,
                manifest_path=path,
                unavailable_reason=f"observation_manifest_invalid:{type(error).__name__}",
            )
        return cls(document, manifest_path=path)

    @classmethod
    def for_canonical_root(
        cls,
        canonical_root: Path,
        *,
        manifest_path: Path | None = None,
    ) -> ObservationCoverage:
        configured = manifest_path
        if configured is None and os.environ.get("TQE_OBSERVATION_MANIFEST_PATH"):
            configured = Path(os.environ["TQE_OBSERVATION_MANIFEST_PATH"])
        return cls.from_path(configured or canonical_root / "observation-manifest.json")

    def decision(
        self,
        *,
        modality: ObservationModality | str,
        match_id: str,
        period: str,
        window: ObservationWindow,
    ) -> CoverageDecision:
        resolved_modality = ObservationModality(modality)
        if self.document is None:
            return CoverageDecision(
                modality=resolved_modality,
                match_id=match_id,
                period=period,
                window=window,
                certified=False,
                reason=self.unavailable_reason or "observation_manifest_unavailable",
            )
        rows = sorted(
            (
                row
                for row in self.document.rows
                if row.modality == resolved_modality
                and row.match_id == match_id
                and row.period == period
            ),
            key=lambda row: row.window.start_frame_id,
        )
        if not rows:
            return CoverageDecision(
                modality=resolved_modality,
                match_id=match_id,
                period=period,
                window=window,
                certified=False,
                reason="observation_coverage_row_absent",
            )
        overlapping = [
            row
            for row in rows
            if row.window.end_frame_id >= window.start_frame_id
            and row.window.start_frame_id <= window.end_frame_id
        ]
        explicit_unknown = [row for row in overlapping if row.status == "UNCERTIFIED"]
        if explicit_unknown:
            return CoverageDecision(
                modality=resolved_modality,
                match_id=match_id,
                period=period,
                window=window,
                certified=False,
                reason="observation_coverage_explicitly_uncertified",
                row_ids=tuple(row.row_id for row in explicit_unknown),
            )
        certified_rows = [row for row in overlapping if row.status == "CERTIFIED"]
        cursor = window.start_frame_id
        used: list[str] = []
        for row in certified_rows:
            if row.window.start_frame_id > cursor:
                break
            if row.window.end_frame_id < cursor:
                continue
            used.append(row.row_id)
            cursor = row.window.end_frame_id + 1
            if cursor > window.end_frame_id:
                return CoverageDecision(
                    modality=resolved_modality,
                    match_id=match_id,
                    period=period,
                    window=window,
                    certified=True,
                    reason="observation_coverage_certified",
                    row_ids=tuple(used),
                )
        return CoverageDecision(
            modality=resolved_modality,
            match_id=match_id,
            period=period,
            window=window,
            certified=False,
            reason="observation_coverage_window_not_certified",
            row_ids=tuple(used),
        )


def gate_absence_status(
    *,
    coverage: ObservationCoverage,
    match_id: str,
    period: str,
    start_frame_id: int,
    end_frame_id: int,
    modalities: tuple[ObservationModality | str, ...],
    status: str,
    reason: str,
    absence_statuses: tuple[str, ...] = ("FAIL",),
) -> AbsenceGateDecision:
    """Force an absence-derived status to UNKNOWN unless all coverage is certified."""

    window = ObservationWindow(
        start_frame_id=min(start_frame_id, end_frame_id),
        end_frame_id=max(start_frame_id, end_frame_id),
    )
    decisions = tuple(
        coverage.decision(
            modality=modality,
            match_id=match_id,
            period=period,
            window=window,
        )
        for modality in dict.fromkeys(ObservationModality(item) for item in modalities)
    )
    if status not in absence_statuses or all(item.certified for item in decisions):
        return AbsenceGateDecision(status=status, reason=reason, coverage=decisions)
    failures = ",".join(
        f"{item.modality.value}:{item.reason}" for item in decisions if not item.certified
    )
    return AbsenceGateDecision(
        status="UNKNOWN",
        reason=f"uncertified_observation_coverage[{failures}];would_be={reason}",
        coverage=decisions,
    )


def gate_state_absence_status(
    *,
    state: Any,
    start_frame_id: int,
    end_frame_id: int,
    modalities: tuple[ObservationModality | str, ...],
    status: str,
    reason: str,
    absence_statuses: tuple[str, ...] = ("FAIL",),
) -> AbsenceGateDecision:
    coverage = getattr(state, "observation_coverage", None)
    if not isinstance(coverage, ObservationCoverage):
        coverage = ObservationCoverage.from_path(None)
    return gate_absence_status(
        coverage=coverage,
        match_id=str(getattr(state, "match_id")),
        period=str(getattr(state, "period")),
        start_frame_id=start_frame_id,
        end_frame_id=end_frame_id,
        modalities=modalities,
        status=status,
        reason=reason,
        absence_statuses=absence_statuses,
    )
