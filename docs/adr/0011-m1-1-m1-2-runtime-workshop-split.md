# ADR 0011 - Split Composable Runtime from Grounded Workshop

Date: 2026-06-19

## Status

Accepted

Planning review: `APPROVE_WITH_REQUIRED_CHANGES`, integrated 2026-06-19.

## Context

After M1 passed controller-only verification, planner review identified the next architectural gap: the system can run a closed catalog of implemented detectors, but it cannot yet author materially new tactical detector plans at runtime from approved primitives.

The first proposed M1.1 bundled four hard problems:

- typed tactical-query representation;
- generic temporal-spatial executor;
- dynamic relation model;
- Hermes-driven feedback and versioning interface.

That is too much for one acceptance boundary. Failure would be hard to localize across analytics, compiler/binder behavior, relation modeling, LLM interpretation, persistence, or UI.

## Decision

Insert two milestones after M1:

```text
M1.1 - Composable Tactical Query Runtime
M1.2 - Grounded Tactical Query Workshop
```

M1.1 proves:

- M1 baseline freeze and reviewed semantic gold set;
- `DraftQueryPlan`;
- deterministic compiler/binder;
- `BoundQueryPlan`;
- generic executor;
- primitive and relation catalog;
- M1 oracle parity;
- one dynamic relation primitive;
- one no-code experimental composition;
- predicate traces and non-match inspection.

M1.2 proves:

- Hermes as a bounded client of M1.1;
- recipe search and draft-plan authoring;
- visible interpretation and confirmation;
- structured analyst feedback;
- known-miss inspection;
- AST-aware revision diffs;
- immutable recipe versions;
- thin workshop loop.

The durable core is:

```text
primitives and relations
-> DraftQueryPlan
-> deterministic compiler / binder
-> BoundQueryPlan
-> generic executor
-> predicate traces
-> evidence
```

Hermes may author and revise tactical definitions using approved measurements. The deterministic engine measures the game. The analyst decides whether the definition captured intent.

## Consequences

- M1.1 can fail independently of Hermes or UI.
- M1.2 can fail without invalidating the deterministic runtime.
- The generic executor cannot contain query-ID branches or hidden custom handlers.
- Runtime authorship can compose and parameterize approved measurements, but development-time work is required to add new measurable vocabulary.
- M2 becomes the second approved tactical family on top of the M1.1 runtime, not another bespoke detector followed by speculative extraction.
- M4 becomes agent reliability and tactical lexicon hardening, not the first assistant milestone.

## Guardrails

- Do not begin M1.1 implementation until a valid M1 Git baseline exists or the owner explicitly waives that requirement.
- M1 parity is measured against the complete frozen result set and reviewed semantic examples.
- Separate `RecipeDefinition`, `QueryInvocation`, `BoundQueryPlan`, and `QueryExecution`.
- Predicate evaluation is tri-state: `TRUE`, `FALSE`, `UNKNOWN`.
- Missing data never silently evaluates as false.
- No arbitrary Python, SQL, generated code, or custom expressions in query plans.
- No Hermes access to complete raw coordinate dumps.
- No silent threshold tuning.
- No unsupported concept may execute as a nearby supported substitute.
- Experimental recipes remain distinct from approved recipes.
- Analyst feedback cannot delete results; it can only inform a new version.
- `geometric_progressive_corridor` V1 remains a narrow geometric relation, not a pass-quality or optimality model.

## Evidence

- `delivery/m1.1/SPEC.md`
- `delivery/m1.2/SPEC.md`
- `MILESTONES.md`
- `delivery/status.yaml`
- `docs/learnings/2026-06-19-runtime-workshop-split.md`
- `docs/reviews/2026-06-19-m1-1-m1-2-external-review.md`
