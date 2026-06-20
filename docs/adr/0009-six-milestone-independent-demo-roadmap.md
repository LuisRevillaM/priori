# ADR 0009 - Six-Milestone Independent Demo Roadmap

Date: 2026-06-19

Status: Accepted for planning

## Context

The four-milestone roadmap conflated query breadth, workbench product architecture, optional assistant behavior, visual delight, and release reliability. That made M2 too broad, made the assistant feel like the product, and left final UI quality as a vague packaging concern.

The project still ends at an independent public-data demo. There is no Priori integration, provider adapter readiness, production deployment, private data, or match-video ingestion.

## Decision

Replace the four-milestone roadmap with six milestones:

```text
M1  Verified Ball-Side Block-Shift Evidence Spine
M2  Deterministic Tactical Query Catalog v1
M3  Analyst Workbench v1
M4  Grounded Query Assistant Pilot
M5  Demo Experience, Motion, and Visual QA
M6  Meeting-Ready Independent Demo Release
```

The governing principle is:

```text
M1 proves truth.
M2 proves breadth.
M3 proves product completeness.
M4 optionally proves grounded language access.
M5 proves delight.
M6 proves meeting reliability.
```

## Key Decisions

- Build two fully verified query families, not one hardcoded detector and not three under-verified families.
- Treat the assistant as conditional and removable; the manual workbench must remain complete without it.
- Give motion, visual hierarchy, guided narrative, and visual QA their own milestone.
- Make the final milestone release/rehearsal/proof focused, with no new feature development after code freeze.

## Consequences

- Agents cannot hide analytical weakness behind UI polish.
- Agents cannot hide UI weakness behind a proof pack.
- The assistant cannot become a brittle scripted demo layer.
- The final release is self-contained, reproducible, and meeting-ready.
- Any future integration work would require a separate project charter.
