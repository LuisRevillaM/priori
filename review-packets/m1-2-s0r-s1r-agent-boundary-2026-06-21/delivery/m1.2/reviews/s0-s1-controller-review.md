# M1.2 S0/S1 Controller Review

Date: 2026-06-20

Decision: PASS_CONTROLLER_PENDING_EXTERNAL_REVIEW

## Scope Reviewed

This review covers only:

- S0 capability and tool boundary;
- S1 manual reference workshop;
- manual typed-plan validation and execution;
- result trace inspection;
- coordinate replay retrieval;
- known-timestamp non-match inspection;
- feedback recording;
- immutable experimental recipe saving.

Hermes drafting, prompt evaluation, automatic revisions, and second tactical
family work remain out of scope.

## Evidence

- S0 report: `artifacts/m1.2/gate-s0-verification-report.json`
- S1 report: `artifacts/m1.2/gate-s1-verification-report.json`
- Aggregate report: `artifacts/m1.2/verification-report.json`
- Capability context: `generated/capability-context.json`
- Manual workshop: `artifacts/m1.2/workshop/index.html`
- Workshop data: `artifacts/m1.2/workshop/manual-workshop-data.json`
- Feedback store: `artifacts/m1.2/workshop/feedback-records.jsonl`
- Saved recipe: `artifacts/m1.2/workshop/recipes/92769e17bb25b809.json`

## Controller Findings

S0 passes because the Hermes-visible surface is bounded to the approved ten
tools, forbidden execution and mutation surfaces are explicitly unavailable,
host-owned complexity ceilings are exposed, unsupported concepts return
capability gaps, and unsafe raw `EpisodeSet` usage with `exists` is rejected by
the workshop boundary.

S1 passes because the manual flow can validate and execute one approved M1
recipe and one experimental corridor recipe, inspect returned results, open
coordinate replay artifacts, inspect a known non-match timestamp, record all
required feedback labels, and save an immutable experimental recipe version.

The manual workshop is intentionally plain. It is a reference/debugging surface,
not the final M3/M5 interface.

## Required External Review Question

Before S2, review whether this S0/S1 slice is sufficient to make Hermes a client
of the existing tool surface, or whether any additional S0/S1 guard is required
before natural-language drafting begins.

