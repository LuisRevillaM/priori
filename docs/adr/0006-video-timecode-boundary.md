# ADR 0006 - Video and Timecode Boundary

Date: 2026-06-19

Status: Accepted for planning, amended by ADR 0008

## Context

The roadmap used the phrase "video-integrated delivery" for M4, which could imply that the public IDSSE/DFL dataset includes match footage or that the M1-M3 replay UI should be built around video.

The public IDSSE/DFL dataset does not include match video. It contains match metadata, event data, and tracking coordinates.

## Decision

M1-M3 are coordinate-replay milestones. They do not include match footage and do not require a video plugin.

The evidence model may later treat video as a first-class optional attachment:

```text
detected moment
-> tracking evidence
-> replay bundle
-> optional rights-cleared video asset or timecode
```

ADR 0008 removed provider adapter readiness and Priori integration from this project. ADR 0009 later expanded the independent-demo roadmap to six milestones. For the active roadmap, M6 is `Meeting-Ready Independent Demo Release`, and video/timecode ingestion is out of scope for the entire project.

## Consequences

- The current UI should render tracking-coordinate replay, not video.
- No implementation should search for or depend on public IDSSE video.
- Video/timecode support is not part of this project.
- Any future video/timecode work would be a separate project with a new charter.
