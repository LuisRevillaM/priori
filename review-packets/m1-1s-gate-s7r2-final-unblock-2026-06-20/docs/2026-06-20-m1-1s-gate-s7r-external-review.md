# M1.1S Gate S7R External Review

## Decision

`APPROVE_WITH_REQUIRED_CHANGES_BEFORE_M1_2`

The external reviewer preserved S7R but required one final focused correction before M1.2.

## Required Corrections

- Mixed known and unknown relation states must become `UNKNOWN` when missing evidence could change relation existence.
- Witness selection must be scoped to the requested relation source, not global across all relation nodes.
- Agent-visible `exists` and `count_at_least` must reject raw relation episode inputs or make them genuinely anchor-relative.
- Complexity limits must be constrained by trusted host ceilings, not only self-declared plan values.
- The reviewed implementation must be committed before M1.2 starts.

## Boundary

The reviewer explicitly rejected another architecture cycle. S7R2 is a small agent-safety correction only.
