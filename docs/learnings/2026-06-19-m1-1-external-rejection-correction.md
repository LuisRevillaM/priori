# M1.1 External Rejection And Correction

Date: 2026-06-19

## Fact

External implementation review rejected the first M1.1 implementation.

## Decision

M1.2 is blocked. M1.1R must correct the runtime architecture before Hermes, feedback, or workshop UX work starts.

## Learning

Passing parity and metadata gates is not sufficient proof of composability. A runtime can look generic at the API level while still hiding query-specific orchestration in node IDs, mutable state fields, result dictionaries, no-op catalog entries, and hand-authored traces.

Future gates must prove graph semantics directly:

- node-ID opacity;
- typed input wiring;
- runtime output conformance;
- plan-driven classification;
- plan-driven evidence projection;
- operational unknown policy;
- invocation enforcement;
- relation execution over explicit anchors;
- a materially different non-M1 plan path.

## Evidence

- `docs/reviews/2026-06-19-m1-1-implementation-external-review.md`
- `delivery/m1.1/CORRECTIVE_SPEC.md`
- `delivery/m1.1/status.yaml`

## Follow-Up

Implement M1.1R Gates R1-R5, preserve M1 parity, and package a new external review packet before starting M1.2.
