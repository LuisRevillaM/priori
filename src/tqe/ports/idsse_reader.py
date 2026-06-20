"""Minimal IDSSE reader port used by the M1 Gate A canonicalizer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from floodlight.core.code import Code
from floodlight.core.events import Events
from floodlight.core.pitch import Pitch
from floodlight.core.teamsheet import Teamsheet
from floodlight.core.xy import XY


@dataclass(frozen=True)
class IDSSEMatchFiles:
    """Local raw files for one source-locked IDSSE match."""

    match_id: str
    metadata_xml: Path
    events_xml: Path
    tracking_xml: Path


@dataclass(frozen=True)
class IDSSEPositionRead:
    """Floodlight's parsed position output behind a project-owned boundary."""

    xy: dict[str, dict[str, XY]]
    possession: dict[str, Code]
    ballstatus: dict[str, Code]
    teamsheets: dict[str, Teamsheet]
    pitch: Pitch


@dataclass(frozen=True)
class IDSSEEventRead:
    """Floodlight's parsed event output behind a project-owned boundary."""

    events: dict[str, dict[str, Events]]
    teamsheets: dict[str, Teamsheet]
    pitch: Pitch


class IDSSEReader(Protocol):
    """Provider-neutral interface for raw IDSSE reads."""

    def read_teamsheets(self, files: IDSSEMatchFiles) -> dict[str, Teamsheet]: ...

    def read_positions(self, files: IDSSEMatchFiles) -> IDSSEPositionRead: ...

    def read_events(self, files: IDSSEMatchFiles) -> IDSSEEventRead: ...
