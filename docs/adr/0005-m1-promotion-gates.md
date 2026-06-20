# ADR 0005 - M1 Uses Hard Promotion Gates

Date: 2026-06-19

Status: Accepted for planning

## Context

Processing all seven matches and building primitives before proving the ingestion and replay stack would create unnecessary autonomous-execution risk.

## Decision

M1 is split into hard internal gates:

- Gate A: one-match viability proof on `J03WOH`.
- Gate B: corpus proof across all seven matches.
- Gate C: tactical proof with frozen query, evidence bundles, replay, and independent review.

No primitive or detector work may begin until Gate A is accepted. No query calibration may begin until Gate B is accepted.

Expose:

```bash
make gate-a-verify
make gate-b-verify
make gate-c-verify
make m1-verify
```

Each command must emit a machine-readable verification report and fail nonzero when a condition is unmet.

## Alternatives Considered

- Treat source lock, corpus ingestion, and tactical proof as one implementation push.
- Process all seven matches before proving one-match parser and replay viability.
- Make Gate A an informal checklist rather than a promotion gate.

## Consequences

- The first implementation task is sharply bounded.
- Agents cannot spend effort on tactical semantics before proving source/canonical/replay integrity.
- Gate A artifacts become the first independent review package.
