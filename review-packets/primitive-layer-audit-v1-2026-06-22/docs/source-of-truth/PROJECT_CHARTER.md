# Priori Tactical Evidence Explorer

## Product Thesis

Build a soccer tactical evidence system that turns real tracking data into replayable, auditable tactical moments. The system should eventually let an analyst ask tactical questions, compile them into typed queries, run deterministic measurements, and inspect spatial evidence through a replay/workbench surface.

## Current Product Boundary

The first milestone is not a generic data backend. It is a verified vertical slice through the evidence spine:

```text
real tracking data
-> canonical representation
-> tactical primitives
-> one frozen typed query
-> real result moments
-> replayable evidence bundles
-> independent review
```

## Primary Dataset

M1 uses the IDSSE / Sportec Open DFL Tracking and Event Data as the only accepted match-evidence source. It is the recommended dataset because it provides synchronized event and full-pitch tracking data for seven German Bundesliga / 2. Bundesliga matches, including all players and the ball at 25 Hz.

SkillCorner, broadcast-derived tracking, synthetic data, or hand-authored fixtures are out of scope for accepted M1 evidence.

M1 is named `Verified Ball-Side Block-Shift Evidence Spine`. It proves moments where the ball enters a wide area, the defending block shifts toward it, and the attack subsequently switches, retains without switching, or loses possession.

After M1, the roadmap inserts two architecture milestones before broadening the product:

```text
M1.1  prove a composable deterministic tactical-query runtime
M1.2  prove Hermes and analyst feedback as clients of that runtime
```

This split is intentional. The runtime/compiler proof must succeed without Hermes before the natural-language and feedback workshop becomes an acceptance boundary.

## Core Principles

- Real evidence only: accepted tactical moments must trace back to pinned raw IDSSE files.
- Deterministic before agentic: M1 contains no Hermes, no natural-language query compiler, and no LLM runtime.
- Replay is verification: a minimal replay surface is required because coordinates and tactical classifications must be visibly inspectable.
- Claims stay narrow: M1 may prove that a defensive block shifted and an outcome followed; it may not claim intent, causation, optimality, or missed opportunity.
- Promotion gates are hard: no primitive or detector work begins until Gate A is accepted.
- Use strict contracts and proof gates, not a single implementation language, as the safety mechanism.
- State is explicit: planned, implemented, verified, reviewed, and accepted are different states.

## Demo Completion Shape

This project ends at an independent pre-meeting demo. It does not assume or require Priori SDK access, Priori API access, private Priori data, production deployment, provider adapter readiness, or rights-cleared video.

The final demo should be an end-to-end vertical slice with a polished, delightful UI: smooth coordinate replay, tactical emphasis animations, clear evidence panels, clean transitions, and no rough placeholder states. It must show enough breadth to be credible: two fully verified tactical query families, a reusable workbench shell, and a grounded assistant only if it passes strict ship gates.

The completion sequence is:

```text
M1  prove the real-data evidence spine
M1.1 prove the composable query runtime and dynamic relation layer
M1.2 prove the grounded tactical query workshop and versioned feedback loop
M2  prove breadth with a second approved tactical family
M3  make the evidence usable in a complete analyst workbench
M4  harden grounded natural-language access over deterministic tools
M5  make the experience delightful and visually QA'd
M6  freeze a polished meeting-ready independent demo release
```

M4 and M5 are parallel branches after M3. The assistant is architecturally first-class because it uses the same bound query plans, capability catalog, recipe versions, and query traces as the manual workbench, but it is not release-critical; M6 includes it only if it passes a strict ship/cut gate.

The public IDSSE/DFL dataset does not contain match video. Replay work is coordinate replay only. The demo may mention that video/timecode could be modeled later, but it must not implement or imply video integration.
