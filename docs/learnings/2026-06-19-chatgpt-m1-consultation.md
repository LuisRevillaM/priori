# Learning - ChatGPT M1 Consultation

Date: 2026-06-19

## Fact

The context-rich ChatGPT conversation recommended tightening the first milestone from a generic data spine to a verified vertical slice through the data spine.

## Decision

M1 was initially planned as `Verified Tactical Evidence Spine: Block Shift -> Switch`, then refined to `Verified Ball-Side Block-Shift Evidence Spine`.

The milestone must prove real data -> canonical store -> tactical primitives -> frozen query -> real moments -> replayable evidence -> independent review.

## Rationale

A data spine can be internally consistent while still tactically wrong. Replay and independent predicate recomputation are required to expose errors in orientation, goalkeeper handling, timing windows, threshold artifacts, and classification logic.

## Additional Controller Decision

The controller will consult the same context-rich ChatGPT conversation at significant gates: spec freeze, data source lock, query freeze, proof-pack review, and next-milestone selection. Each consultation must use a self-contained, evidence-indexed packet.

## Follow-Up

- Use `delivery/m1/SPEC.md` as the controlling refined M1 spec.
- Build Gate A before any primitive or detector implementation.
- Use `delivery/CONTROLLER_PROTOCOL.md` for future consultation packets.
