# Learning - Runtime/Workshop Split

Date: 2026-06-19

## Fact

M1 proves a trusted first detector and evidence spine, but it remains a closed detector implementation. The next architectural gap is runtime composition of detector plans from approved primitives and relations.

## Decision

Split the originally proposed M1.1 into:

- M1.1: composable deterministic query runtime;
- M1.2: Hermes-driven query workshop and versioned feedback loop.

M1.1 must prove the typed IR, binder, executor, dynamic relation layer, no-code composition, and predicate traces without Hermes. M1.2 may then prove natural-language drafting, feedback, revision diffs, and immutable recipe saving as a bounded client of that runtime.

External review approved the split with required changes. The most important changes are: freeze M1 with a valid baseline before implementation, add reviewed semantic examples before treating M1 as an oracle, strengthen the binder type model, require tri-state predicates, formalize non-match evaluation, narrow `geometric_progressive_corridor`, and add quantitative M1.2 agent evaluation.

## Learning

Hermes should not author geometry algorithms. It should author detector plans over a bounded vocabulary of already-implemented measurements. If the requested concept needs a missing primitive, the correct output is a capability gap, not a silent approximation.

The compiler/binder stage is the safety boundary. Hermes produces draft plans; only deterministically bound plans execute.

## Evidence

- `docs/adr/0011-m1-1-m1-2-runtime-workshop-split.md`
- `delivery/m1.1/SPEC.md`
- `delivery/m1.2/SPEC.md`
- `MILESTONES.md`

## Follow-Up

Begin M1.1 with M1 oracle parity. Do not start Hermes/workshop implementation until the runtime proof passes.

Updated follow-up: before M1.1 implementation, establish the M1 baseline freeze and owner acceptance or explicit owner waiver.
