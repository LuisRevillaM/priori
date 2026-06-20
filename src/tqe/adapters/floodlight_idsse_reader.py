"""Floodlight-backed IDSSE reader adapter.

Floodlight objects are returned only through the Gate A reader boundary and are
converted to canonical Parquet immediately by the build step.
"""

from __future__ import annotations

from floodlight.io import dfl

from tqe.ports.idsse_reader import IDSSEEventRead, IDSSEMatchFiles, IDSSEPositionRead


class FloodlightIDSSEReader:
    """Read source-locked DFL XML through Floodlight's parser."""

    def read_teamsheets(self, files: IDSSEMatchFiles):
        return dfl.read_teamsheets_from_mat_info_xml(files.metadata_xml)

    def read_positions(self, files: IDSSEMatchFiles) -> IDSSEPositionRead:
        xy, possession, ballstatus, teamsheets, pitch = dfl.read_position_data_xml(
            files.tracking_xml,
            files.metadata_xml,
        )
        return IDSSEPositionRead(
            xy=xy,
            possession=possession,
            ballstatus=ballstatus,
            teamsheets=teamsheets,
            pitch=pitch,
        )

    def read_events(self, files: IDSSEMatchFiles) -> IDSSEEventRead:
        events, teamsheets, pitch = dfl.read_event_data_xml(
            files.events_xml,
            files.metadata_xml,
        )
        return IDSSEEventRead(events=events, teamsheets=teamsheets, pitch=pitch)
