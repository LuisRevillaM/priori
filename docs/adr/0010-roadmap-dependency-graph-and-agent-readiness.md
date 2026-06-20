# ADR 0010 - Roadmap Dependency Graph and Agent Readiness

Date: 2026-06-19

Status: Accepted for planning

## Context

External review agreed with the six milestone names but found that the roadmap should not be treated as a strictly linear sequence. It also identified missing safeguards around agent readiness, premature abstraction, semantic regression, and hidden query substitutions.

## Decision

Keep the six milestone names, but treat them as a dependency graph:

```text
M1 -> M2 -> M3
              |-> M4 Grounded Query Assistant Pilot
              |-> M5 Demo Experience, Motion, and Visual QA
M4 ship/cut + M5 -> M6
```

M4 may run in parallel with M5 after M3. It is architecturally first-class but not release-critical.

The roadmap now requires:

- generated capability catalog by the end of M2;
- one shared deterministic query validator/executor used by manual UI, CLI/tests, and assistant tools;
- second-query-first rule before shared abstraction;
- semantic gold set for each query family;
- query trace for every manual or assistant execution;
- no analytical changes once M5 begins, except verified defect fixes.

## Consequences

- The assistant can be cut without delaying demo polish.
- The assistant cannot use separate query logic.
- Abstractions must be justified by two working query families.
- Query semantics gain reviewed regression examples beyond formula-level tests.
- M6 integrates only the assistant state decided by M4.
