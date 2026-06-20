# Source Excerpts

## M1.1 Outcome

A developer can add a validated tactical detector plan, bind it against an approved primitive/relation catalog, execute it over the real IDSSE corpus through a generic deterministic runtime, inspect every predicate trace, and replay the resulting moments without adding query-specific backend code.

## M1.1 Architecture

```text
IDSSE tracking/events
        ↓
Canonical match store
        ↓
Primitive and relation catalog
        ↓
DraftQueryPlan
        ↓
Deterministic compiler / binder
        ↓
BoundQueryPlan
        ↓
Generic deterministic executor
        ↓
QueryExecution + predicate traces
        ↓
Evidence bundles + replay inspector
```

## M1.1 Gates

- Gate A: M1 oracle parity.
- Gate B: minimal type system and binder.
- Gate C: dynamic relation proof using `geometric_progressive_corridor`.
- Gate D: no-code experimental composition.
- Gate E: predicate trace and non-match inspection.

## M1.2 Outcome

A soccer expert can describe a positional process, inspect Hermes's interpretation, execute the bound query plan, review real moments and non-matches, label good and bad results, approve an explicit revision, and save a new immutable experimental recipe version.

## M1.2 Gates

- Gate A: tool boundary and capability context.
- Gate B: draft, bind, confirm, execute.
- Gate C: feedback and non-match inspection.
- Gate D: revision and versioning.
- Gate E: workshop thin slice.

## Roadmap After Split

```text
M1      Completed evidence spine and trusted first detector
M1.1    Composable query runtime
M1.2    Grounded tactical query workshop
M2      Second approved tactical family and capability catalog
M3      Analyst workbench v1
M4      Agent reliability and tactical lexicon hardening
M5      Demo experience, motion, and visual QA
M6      Meeting-ready independent demo release
```
