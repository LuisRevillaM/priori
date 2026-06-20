# External Review Prompt - M1.1 Completed Implementation

You are reviewing a completed implementation packet for a tactical soccer visualization/demo system. You do not have access to the live repository, so use the packet contents as your evidence.

## Context

The project is building an independent demo over public/open IDSSE-style tracking/event data. There is no Priori SDK/API integration, no match video integration, and no production cloud boundary in scope. The demo roadmap is intended to culminate in a full vertical slice with a delightful analyst-facing UI, but M1.1 is intentionally a backend/runtime foundation milestone.

M1 produced a hard-coded but verified tactical proof for a "ball-side block shift" query over Fortuna Duesseldorf Bundesliga data. M1.1 was introduced after M1 to avoid building future AI/UX layers on a narrow detector. The M1.1 goal was to prove a composable tactical query runtime before M1.2 adds the Hermes/natural-language workshop loop.

## M1.1 Product Outcome

A developer can add a validated tactical detector plan, bind it against an approved primitive/relation catalog, execute it over the real IDSSE corpus through a generic deterministic runtime, inspect every predicate trace, and replay the resulting moments without adding query-specific backend code.

M1.1 proves this chain:

```text
RecipeDefinition
-> QueryInvocation
-> DraftQueryPlan
-> deterministic compiler / binder
-> BoundQueryPlan
-> generic executor
-> QueryExecution
-> predicate traces
-> evidence bundles
-> developer inspector
```

## Implemented Scope

The completed implementation claims to include:

- typed Tactical Query IR v1 using Pydantic as the authority;
- explicit separation of recipe definition, query invocation, draft plan, bound plan, and query execution;
- deterministic compiler/binder from draft plans to bound plans;
- primitive/relation catalog with explicit types, units, cardinality, entity scope, missing-data semantics, limitations, and evidence fields;
- generic executor without query-ID, recipe-ID, or plan-ID branch conditionals;
- M1 ball-side block shift translated into approved plan data;
- runtime parity with frozen M1 legacy outputs;
- tri-state predicate traces and forced-window/non-match evaluation;
- dynamic `geometric_progressive_corridor` relation;
- experimental opposite-corridor-after-shift composition authored as plan data, not a Python detector;
- static developer inspector for plan selection, result inspection, replay frames, predicate traces, non-match inspection, and raw evidence.

## Verification Summary

Local controller verification passed:

- `make m1-1-gate-f-verify`: pass, 13 passing checks, 0 failures, 0 not-ready.
- `make m1-1-verify`: pass, 118 passing checks, 0 failures, 0 not-ready.
- `make test`: pass, 20 tests.
- `make m1-verify`: pass, original M1 Gates A-C still pass.
- `git diff --check`: pass, no whitespace errors.

M1.1 aggregate gate summary:

- Gate A: 49 pass, 0 fail, 0 not-ready.
- Gate B: 14 pass, 0 fail, 0 not-ready.
- Gate C: 10 pass, 0 fail, 0 not-ready.
- Gate D: 11 pass, 0 fail, 0 not-ready.
- Gate E: 21 pass, 0 fail, 0 not-ready.
- Gate F: 13 pass, 0 fail, 0 not-ready.

Gate F inspector summary:

- status: pass;
- plan count: 2;
- result count: 57;
- non-match evaluation count: 3;
- plans: approved M1 `ball_side_block_shift_ir_v1` and experimental `opposite_corridor_after_shift_experimental_v1`.

## Source And Evidence Map

Review these packet files:

- `source-files/delivery/m1.1/SPEC.md`
- `source-files/delivery/m1.1/status.yaml`
- `source-files/config/query-plans/ball_side_block_shift.ir.v1.json`
- `source-files/config/query-plans/opposite_corridor_after_shift.experimental.v1.json`
- `source-files/src/tqe/runtime/ir.py`
- `source-files/src/tqe/runtime/catalog.py`
- `source-files/src/tqe/runtime/binder.py`
- `source-files/src/tqe/runtime/executor.py`
- `source-files/src/tqe/runtime/relations.py`
- `source-files/src/tqe/inspector/m1_1.py`
- `source-files/src/tqe/verification/m1_1_gate_a.py`
- `source-files/src/tqe/verification/m1_1_gate_b.py`
- `source-files/src/tqe/verification/m1_1_gate_c.py`
- `source-files/src/tqe/verification/m1_1_gate_d.py`
- `source-files/src/tqe/verification/m1_1_gate_e.py`
- `source-files/src/tqe/verification/m1_1_gate_f.py`
- `source-files/tests/test_m1_1_binder.py`
- `source-files/tests/test_m1_1_runtime.py`
- `artifacts/m1.1/verification-report.json`
- `artifacts/m1.1/gate-f-verification-report.json`
- `artifacts/m1.1/binder-validation-report.json`
- `artifacts/m1.1/runtime-execution.json`
- `artifacts/m1.1/parity-report.json`
- `artifacts/m1.1/predicate-trace-report.json`
- `artifacts/m1.1/relation-validation-report.json`
- `artifacts/m1.1/experimental-query-results.json`
- `artifacts/m1.1/experimental-evidence-manifest.json`
- `artifacts/m1.1/inspector/manifest.json`
- `artifacts/m1.1/relation-visual-review/*.svg`

Large local artifacts omitted from the packet:

- `artifacts/m1.1/inspector/inspector-data.json` and `.js`, roughly 51 MB.
- `artifacts/m1.1/experimental-evidence/*/bundle.json` and `replay.json`, roughly 66 MB total.

## Specific Review Questions

Please answer these directly:

1. Does M1.1 honestly prove a composable tactical query runtime, or is it still mostly the M1 detector with a schema wrapped around it?
2. Is the "no query-specific backend code" claim defensible? Check especially `src/tqe/runtime/executor.py`, the AST-based gate checks, and whether helper naming or result shaping hides query-specific logic.
3. Are the binder checks strong enough to stop invalid or ambiguous plans from executing visibly, rather than silently returning no results?
4. Is the catalog sufficiently typed for M1.2 Hermes/natural-language drafting, or are important type/semantic constraints still informal?
5. Are tri-state predicate traces and non-match evaluations good enough for analyst trust and future feedback loops?
6. Is `geometric_progressive_corridor` a valuable and bounded relation primitive, or is it too bespoke/fragile for the roadmap?
7. Is the experimental opposite-corridor plan truly authored as plan data over reusable primitives/relations, or does it depend on hidden special cases?
8. Is Gate F's static inspector enough for developer verification before the polished M1.2 workshop begins?
9. Are the proof gates self-verifying enough for autonomous agents, with low ambiguity and low reward-hacking surface?
10. What, if anything, must be changed before M1.2 starts?

## Known Review Risks To Scrutinize

Do not take the local controller's approval as gospel. Please pressure test these concerns:

- The executor has primitive functions for the current known tactical concepts. That may be acceptable for M1.1, but it must not become an unbounded graph engine or a pile of per-query Python.
- The code includes legacy field names such as `query_id` for compatibility with M1 proof artifacts. Decide whether this is harmless compatibility or architectural debt.
- The AST gate checks reject branches on `query_id`, `recipe_id`, and `plan_id`, but they do not prove all forms of semantic coupling are absent.
- Gate E's no-code composition depends on a new generic `relation_destination_entry_classification` primitive. Decide whether that primitive is genuinely reusable.
- The static inspector is a developer artifact, not the final analyst UI. Decide whether this is the right stopping point for M1.1.
- The packet cannot prove the full local replay experience because the largest generated artifacts are omitted.

## Requested Output Format

Return:

```text
Decision: APPROVE | APPROVE_WITH_REQUIRED_CHANGES | REJECT

Blocking Findings:
- ...

Required Changes Before M1.2:
- ...

Non-Blocking Concerns:
- ...

Downstream Roadmap Risks:
- ...

Answer To The 10 Review Questions:
1. ...
```

Be strict. The purpose of this review is to decide whether M1.2 should begin or whether M1.1 needs one more corrective pass.
