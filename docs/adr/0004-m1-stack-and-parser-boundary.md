# ADR 0004 - M1 Stack and Parser Boundary

Date: 2026-06-19

Status: Accepted for planning

## Context

The project considered whether stricter language guarantees should push M1 toward Go or TypeScript end to end. The material M1 risks are semantic and evidentiary: wrong attacking direction, goalkeeper inclusion, possession-boundary errors, noisy one-frame shifts, late outcome classification, or replay evidence that does not match source coordinates.

## Decision

Use Python for the analytical spine and TypeScript for the replay proof. Do not introduce Go in M1.

Use Floodlight as the primary IDSSE/DFL parser behind a replaceable port:

```text
src/tqe/ports/idsse_reader.py
src/tqe/adapters/floodlight_idsse_reader.py
src/tqe/adapters/kloppy_idsse_reader.py
```

Floodlight objects must be converted immediately into provider-neutral canonical records. They may not cross into primitives, query execution, evidence generation, replay, or contract models.

## Alternatives Considered

- Go analytical pipeline.
- TypeScript end to end.
- Custom full-match XML parser first.
- Floodlight objects as internal domain model.

## Consequences

- M1 benefits from Python-native IDSSE/DFL parsing and numerical tooling.
- Safety comes from strict contracts, invariants, property tests, independent recomputation, and replay review.
- Go remains available later for measured production-service needs.
- If Floodlight fails explicit resource or fidelity gates, a streaming parser can be justified by ADR.
