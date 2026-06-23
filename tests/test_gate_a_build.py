from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tqe.data.gate_a_build import MatchMeta, TeamMeta, extract_orientation, extract_raw_samples
from tqe.data.gate_b_build import metadata_rows


class GateABuildTests(unittest.TestCase):
    def test_extract_orientation_ignores_kickoffs_without_game_section(self) -> None:
        events_xml = """<?xml version="1.0" encoding="UTF-8"?>
<PutDataRequest>
  <Event EventId="first"><KickOff GameSection="firstHalf" TeamLeft="away" TeamRight="home"/></Event>
  <Event EventId="noise"><KickOff TeamLeft="home" TeamRight="away"/></Event>
  <Event EventId="second"><KickOff GameSection="secondHalf" TeamLeft="home" TeamRight="away"/></Event>
</PutDataRequest>
"""
        match_meta = type(
            "MatchMetaStub",
            (),
            {
                "match_id": "TEST",
                "teams": {
                    "home": TeamMeta("home", "Home", "home", "Home"),
                    "away": TeamMeta("away", "Away", "away", "Away"),
                }
            },
        )()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.xml"
            path.write_text(events_xml, encoding="utf-8")

            rows = extract_orientation(path, match_meta)

        self.assertEqual(4, len(rows))
        self.assertEqual({"firstHalf", "secondHalf"}, {row["period"] for row in rows})

    def test_extract_raw_samples_skips_non_canonical_referee_framesets(self) -> None:
        tracking_xml = """<?xml version="1.0" encoding="UTF-8"?>
<PutDataRequest>
  <Positions>
    <FrameSet GameSection="firstHalf" TeamId="home" PersonId="p1">
      <Frame N="1" T="t1" X="1.0" Y="2.0"/>
    </FrameSet>
    <FrameSet GameSection="firstHalf" TeamId="referee" PersonId="r1">
      <Frame N="1" T="t1" X="3.0" Y="4.0"/>
    </FrameSet>
    <FrameSet GameSection="firstHalf" TeamId="BALL" PersonId="DFL-OBJ-0000XT">
      <Frame N="1" T="t1" X="5.0" Y="6.0"/>
    </FrameSet>
  </Positions>
</PutDataRequest>
"""
        match_meta = type(
            "MatchMetaStub",
            (),
            {
                "teams": {
                    "home": TeamMeta("home", "Home", "home", "Home"),
                    "away": TeamMeta("away", "Away", "away", "Away"),
                }
            },
        )()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tracking.xml"
            path.write_text(tracking_xml, encoding="utf-8")

            samples = extract_raw_samples(path, match_meta)

        self.assertEqual(["home", "BALL"], [sample.team_id for sample in samples])

    def test_metadata_rows_enriches_known_team_branding(self) -> None:
        match_meta = MatchMeta(
            match_id="TEST",
            competition_id=None,
            competition_name=None,
            season=None,
            match_day=None,
            match_title="Fortuna Düsseldorf:F.C. Hansa Rostock",
            kickoff_time_utc=None,
            result=None,
            pitch_length_m=105.0,
            pitch_width_m=68.0,
            teams={
                "home": TeamMeta("DFL-CLU-00000P", "Fortuna Düsseldorf", "home", "Home"),
                "away": TeamMeta("DFL-CLU-00000Q", "F.C. Hansa Rostock", "away", "Away"),
            },
            players=[],
        )

        rows = metadata_rows(match_meta)
        home = next(team for team in rows["teams"] if team["team_role"] == "home")
        away = next(team for team in rows["teams"] if team["team_role"] == "away")

        self.assertEqual("Fortuna", home["team_short_name"])
        self.assertEqual("F95", home["team_abbreviation"])
        self.assertIn("Fortuna_D%C3%BCsseldorf.svg", home["logo_url"])
        self.assertEqual("Hansa Rostock", away["team_short_name"])
        self.assertIn("F.C._Hansa_Rostock_Logo.svg", away["logo_url"])


if __name__ == "__main__":
    unittest.main()
