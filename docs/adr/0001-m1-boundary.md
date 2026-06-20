# ADR 0001 - M1 Boundary Is a Verified Ball-Side Block-Shift Slice

Date: 2026-06-19

Status: Accepted for planning

## Context

The initial intuition was to start with the backend data spine: download data, normalize it, define primitives, and prepare for future query/UI work. ChatGPT challenged that boundary because a data spine can be internally consistent while producing no tactically credible proof.

## Decision

M1 will be `Verified Ball-Side Block-Shift Evidence Spine`.

The milestone must run real IDSSE tracking data through canonicalization, derive only the needed tactical primitives, execute one frozen query-specific model, produce real moments where the defensive block shifts toward the ball side, classify the subsequent outcome, and render those moments in a minimal replay surface for verification.

## Alternatives Considered

- Generic data spine only.
- "Block Shift -> Switch" naming that implies the switch necessarily follows.
- Polished replay/workbench first.
- Hermes/natural-language query workshop first.
- Harder first query such as unsupported winger or missed crossing opportunity.

## Consequences

- Replay UI is required as verification, not polish.
- M1 remains deterministic and excludes Hermes.
- The first query is narrow enough to verify from tracking data.
- The query name no longer overclaims switch availability, intent, or opportunity.
- Implementation agents get concrete acceptance gates instead of broad infrastructure tasks.
