# ADR 0008 - Independent Demo Scope

Date: 2026-06-19

Status: Accepted for planning

## Context

The roadmap still implied future provider or Priori integration work. The actual project goal is narrower: build a completely independent demo ahead of the Priori meeting, using public data, and end the project there.

## Decision

Remove provider adapter readiness and Priori integration from the planned milestone sequence.

M4 becomes `Meeting-Ready Independent Demo Package`. It is the end of the project as envisioned, not a placeholder for later integration work.

ADR 0009 later expands the completion sequence from four milestones to six so query breadth, workbench product flow, optional assistant behavior, visual delight, and release reliability are not conflated.

The active project completion milestones are:

```text
M1  Verified Ball-Side Block-Shift Evidence Spine
M2  Deterministic Tactical Query Catalog v1
M3  Analyst Workbench v1
M4  Grounded Query Assistant Pilot
M5  Demo Experience, Motion, and Visual QA
M6  Meeting-Ready Independent Demo Release
```

M6 is complete when the demo can be run, reset, explained, and reviewed without Priori access, private provider data, video assets, production credentials, or manual operator repair. It must feel like a finished vertical slice, not just a proof bundle.

## Historical M4 Acceptance

The former four-milestone M4 acceptance has been superseded by M5 and M6 in ADR 0009:

- one-command local demo startup;
- pinned demo dataset/artifacts;
- 3-5 verified demo scenarios;
- replayable coordinate evidence for every showcased moment;
- polished UI with smooth replay motion, tactical emphasis animations, clean transitions, and no rough placeholder states;
- guided path from question -> result list -> replay -> evidence -> conclusion;
- deterministic rebuild/reset path;
- meeting script;
- claim-boundary page or slide;
- fallback screenshots or generated screen recording from coordinate replay;
- visual QA evidence for the main demo viewport(s);
- final proof packet with tests, review notes, known limitations, and non-claims;
- explicit statement that there is no Priori integration and no match video.

## Consequences

- No worker should build provider adapter readiness in this project.
- No worker should implement Priori-specific code.
- No worker should implement video/timecode ingestion.
- Any future integration would be a separate project with a new charter and ADR.
