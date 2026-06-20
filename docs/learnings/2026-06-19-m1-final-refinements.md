# Learning - M1 Final Refinements

Date: 2026-06-19

## Fact

The final ChatGPT refinement recommended locking M1 around a more precise name, hard internal promotion gates, a Floodlight parser boundary, a query-specific model, and revised result-count gates.

## Decision

M1 is now `Verified Ball-Side Block-Shift Evidence Spine`.

The first implementation task is Gate A: provision and source-lock `J03WOH`; parse through an isolated Floodlight adapter; emit canonical Parquet; independently compare raw XML samples with canonical output; verify both-half orientation; record peak memory and runtime; and render one real 30-second sequence using only canonical files.

## Evidence

- `delivery/m1/SPEC.md`
- `MILESTONES.md`
- `docs/adr/0004-m1-stack-and-parser-boundary.md`
- `docs/adr/0005-m1-promotion-gates.md`

## Follow-Up

- Start implementation at Gate A only.
- Do not build primitives or detector logic before Gate A is accepted.
- Prepare the next ChatGPT consultation packet after Gate A evidence exists.
