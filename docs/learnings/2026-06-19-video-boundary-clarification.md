# Learning - Video Boundary Clarification

Date: 2026-06-19

## Fact

The public IDSSE/DFL dataset does not contain match video. It provides metadata, event data, and tracking coordinates.

## Decision

M1-M3 are coordinate-replay milestones only. The UI being built for those milestones is not a video player and does not plug into public-dataset footage.

ADR 0008 and ADR 0009 later superseded this optional-video framing for the current project. Video/timecode support is out of scope for the independent demo.

## Follow-Up

- Do not implement video UI or video ingestion in this project.
- Any future video/timecode work needs a separate project charter.
