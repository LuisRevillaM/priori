"""Provider-neutral exchange contract for canonical tracking adapters."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


EvidenceStatus = Literal["KNOWN", "UNKNOWN"]
TeamRole = Literal["home", "away"]


class CanonicalTrackingTeam(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_id: str = Field(min_length=1)
    team_name: str = Field(min_length=1)
    team_role: TeamRole


class CanonicalTrackingEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str = Field(min_length=1)
    team_role: TeamRole
    shirt_number: int | None = None
    is_goalkeeper: bool = False


class CanonicalTrackingPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str = Field(min_length=1)
    x_m: float
    y_m: float


class CanonicalTrackingFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frame_id: int = Field(ge=0)
    timestamp_utc: str = Field(min_length=1)
    position_evidence: EvidenceStatus
    position_gate_reasons: list[str] = Field(default_factory=list)
    positions: list[CanonicalTrackingPosition] = Field(default_factory=list)
    possession_team_role: TeamRole | None = None
    possession_evidence: EvidenceStatus
    ball_alive: bool | None = None
    ball_evidence: EvidenceStatus
    ball_x_m: float | None = None
    ball_y_m: float | None = None

    @model_validator(mode="after")
    def validate_unknowns(self) -> CanonicalTrackingFrame:
        if self.position_evidence == "UNKNOWN" and self.positions:
            raise ValueError("UNKNOWN frame positions must be withheld")
        if self.possession_evidence == "UNKNOWN" and self.possession_team_role is not None:
            raise ValueError("UNKNOWN possession evidence cannot carry a team role")
        if self.ball_evidence == "UNKNOWN" and any(
            value is not None for value in (self.ball_alive, self.ball_x_m, self.ball_y_m)
        ):
            raise ValueError("UNKNOWN ball evidence cannot carry state or coordinates")
        if (self.ball_x_m is None) != (self.ball_y_m is None):
            raise ValueError("ball coordinates must be both present or both absent")
        return self


class CanonicalTrackingMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: str = Field(min_length=1)
    period: str = Field(min_length=1)
    frame_rate_hz: int = Field(gt=0)
    pitch_length_m: float = Field(gt=0)
    pitch_width_m: float = Field(gt=0)
    teams: list[CanonicalTrackingTeam]
    entities: list[CanonicalTrackingEntity]
    frames: list[CanonicalTrackingFrame]

    @model_validator(mode="after")
    def validate_references(self) -> CanonicalTrackingMatch:
        roles = [team.team_role for team in self.teams]
        if sorted(roles) != ["away", "home"]:
            raise ValueError("matches require exactly one home and one away team")
        entity_ids = [entity.entity_id for entity in self.entities]
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("entity_id values must be unique per match")
        frame_ids = [frame.frame_id for frame in self.frames]
        if frame_ids != sorted(set(frame_ids)):
            raise ValueError("frame_id values must be unique and ascending")
        known_entities = set(entity_ids)
        for frame in self.frames:
            position_ids = [position.entity_id for position in frame.positions]
            if len(position_ids) != len(set(position_ids)):
                raise ValueError(f"duplicate position entity in frame {frame.frame_id}")
            unknown = sorted(set(position_ids) - known_entities)
            if unknown:
                raise ValueError(f"frame {frame.frame_id} references unknown entities {unknown}")
        return self


class CanonicalTrackingExchange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["canonical_tracking_exchange.v1"]
    source_adapter: str = Field(min_length=1)
    matches: list[CanonicalTrackingMatch]

    @model_validator(mode="after")
    def validate_match_ids(self) -> CanonicalTrackingExchange:
        match_ids = [match.match_id for match in self.matches]
        if len(match_ids) != len(set(match_ids)):
            raise ValueError("match_id values must be unique")
        return self
