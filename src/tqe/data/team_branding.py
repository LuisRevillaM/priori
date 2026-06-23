"""Curated team branding metadata for canonical teams and the Workbench.

The IDSSE metadata gives us team IDs and names, but not display assets. Keep the
branding registry small, deterministic, and source-attributed so canonical data
can be enriched without committing trademarked logo binaries.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


WIKIMEDIA_SOURCE = "Wikimedia Commons"


@dataclass(frozen=True)
class TeamBranding:
    team_id: str
    team_name: str
    short_name: str
    abbreviation: str
    logo_url: str
    logo_source: str
    primary_color: str
    secondary_color: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


TEAM_BRANDING_BY_ID: dict[str, TeamBranding] = {
    "DFL-CLU-00000P": TeamBranding(
        team_id="DFL-CLU-00000P",
        team_name="Fortuna Düsseldorf",
        short_name="Fortuna",
        abbreviation="F95",
        logo_url="https://upload.wikimedia.org/wikipedia/commons/9/94/Fortuna_D%C3%BCsseldorf.svg",
        logo_source=WIKIMEDIA_SOURCE,
        primary_color="#d71920",
        secondary_color="#ffffff",
    ),
    "DFL-CLU-000011": TeamBranding(
        team_id="DFL-CLU-000011",
        team_name="SSV Jahn Regensburg",
        short_name="Jahn Regensburg",
        abbreviation="SSV",
        logo_url="https://upload.wikimedia.org/wikipedia/commons/5/5a/SSV_Jahn_Regensburg.svg",
        logo_source=WIKIMEDIA_SOURCE,
        primary_color="#d71920",
        secondary_color="#ffffff",
    ),
    "DFL-CLU-00000Q": TeamBranding(
        team_id="DFL-CLU-00000Q",
        team_name="F.C. Hansa Rostock",
        short_name="Hansa Rostock",
        abbreviation="FCH",
        logo_url="https://upload.wikimedia.org/wikipedia/commons/8/8f/F.C._Hansa_Rostock_Logo.svg",
        logo_source=WIKIMEDIA_SOURCE,
        primary_color="#005aaa",
        secondary_color="#ffffff",
    ),
    "DFL-CLU-000005": TeamBranding(
        team_id="DFL-CLU-000005",
        team_name="1. FC Nürnberg",
        short_name="Nürnberg",
        abbreviation="FCN",
        logo_url="https://upload.wikimedia.org/wikipedia/commons/f/fa/1._FC_N%C3%BCrnberg_logo.svg",
        logo_source=WIKIMEDIA_SOURCE,
        primary_color="#a6192e",
        secondary_color="#ffffff",
    ),
    "DFL-CLU-00000H": TeamBranding(
        team_id="DFL-CLU-00000H",
        team_name="FC St. Pauli",
        short_name="St. Pauli",
        abbreviation="STP",
        logo_url="https://upload.wikimedia.org/wikipedia/commons/b/b3/Fc_st_pauli_logo.svg",
        logo_source=WIKIMEDIA_SOURCE,
        primary_color="#6b3f2a",
        secondary_color="#ffffff",
    ),
    "DFL-CLU-00000I": TeamBranding(
        team_id="DFL-CLU-00000I",
        team_name="1. FC Kaiserslautern",
        short_name="Kaiserslautern",
        abbreviation="FCK",
        logo_url="https://upload.wikimedia.org/wikipedia/commons/d/d3/Logo_1_FC_Kaiserslautern.svg",
        logo_source=WIKIMEDIA_SOURCE,
        primary_color="#d71920",
        secondary_color="#ffffff",
    ),
    "DFL-CLU-00000G": TeamBranding(
        team_id="DFL-CLU-00000G",
        team_name="FC Bayern München",
        short_name="Bayern",
        abbreviation="FCB",
        logo_url="https://upload.wikimedia.org/wikipedia/commons/1/1b/FC_Bayern_M%C3%BCnchen_logo_%282017%29.svg",
        logo_source=WIKIMEDIA_SOURCE,
        primary_color="#dc052d",
        secondary_color="#0066b2",
    ),
    "DFL-CLU-000008": TeamBranding(
        team_id="DFL-CLU-000008",
        team_name="1. FC Köln",
        short_name="Köln",
        abbreviation="KOE",
        logo_url="https://upload.wikimedia.org/wikipedia/commons/0/01/1._FC_Koeln_Logo_2014%E2%80%93.svg",
        logo_source=WIKIMEDIA_SOURCE,
        primary_color="#ed1c24",
        secondary_color="#ffffff",
    ),
    "DFL-CLU-00000B": TeamBranding(
        team_id="DFL-CLU-00000B",
        team_name="Bayer 04 Leverkusen",
        short_name="Leverkusen",
        abbreviation="B04",
        logo_url="https://upload.wikimedia.org/wikipedia/commons/e/ee/Logo_TSV_Bayer_04_Leverkusen.svg",
        logo_source=WIKIMEDIA_SOURCE,
        primary_color="#e32221",
        secondary_color="#111111",
    ),
    "DFL-CLU-00000S": TeamBranding(
        team_id="DFL-CLU-00000S",
        team_name="VfL Bochum 1848",
        short_name="Bochum",
        abbreviation="BOC",
        logo_url="https://upload.wikimedia.org/wikipedia/commons/7/72/VfL_Bochum_logo.svg",
        logo_source=WIKIMEDIA_SOURCE,
        primary_color="#005ca9",
        secondary_color="#ffffff",
    ),
}


def team_branding_for(team_id: str | None, team_name: str | None = None) -> TeamBranding | None:
    if team_id and team_id in TEAM_BRANDING_BY_ID:
        return TEAM_BRANDING_BY_ID[team_id]
    normalized = normalize_team_name(team_name)
    if not normalized:
        return None
    for branding in TEAM_BRANDING_BY_ID.values():
        if normalize_team_name(branding.team_name) == normalized:
            return branding
    return None


def team_branding_fields(team_id: str | None, team_name: str | None = None) -> dict[str, Any]:
    branding = team_branding_for(team_id, team_name)
    if branding is None:
        return {
            "team_short_name": team_name,
            "team_abbreviation": initials(team_name),
            "logo_url": None,
            "logo_source": None,
            "primary_color": None,
            "secondary_color": None,
        }
    return {
        "team_short_name": branding.short_name,
        "team_abbreviation": branding.abbreviation,
        "logo_url": branding.logo_url,
        "logo_source": branding.logo_source,
        "primary_color": branding.primary_color,
        "secondary_color": branding.secondary_color,
    }


def normalize_team_name(value: str | None) -> str:
    return " ".join(str(value or "").replace(".", "").casefold().split())


def initials(value: str | None) -> str:
    parts = [part for part in str(value or "").replace(".", " ").split() if part]
    if not parts:
        return "?"
    return "".join(part[0].upper() for part in parts[:3])
