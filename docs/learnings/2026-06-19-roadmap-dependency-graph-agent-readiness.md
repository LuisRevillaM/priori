# Learning - Roadmap Dependency Graph and Agent Readiness

Date: 2026-06-19

## Fact

External review recommended keeping the six milestone names while changing the sequencing and readiness rules.

## Decision

Treat M4 and M5 as parallel branches after M3. Make the assistant architecturally first-class through the capability catalog and query trace, but not release-critical.

Add cross-cutting safeguards:

- capability catalog mandatory in M2;
- second query must work before shared abstraction;
- semantic gold set for each query family;
- query trace for every execution;
- M4 ship/cut decision before M6;
- no analytical changes once M5 begins except verified defect fixes.

## Follow-Up

- Add detailed executable specs only for the active milestone.
- Start implementation at M1 Gate A.
- Do not create M2 abstractions until the second query proves itself.
