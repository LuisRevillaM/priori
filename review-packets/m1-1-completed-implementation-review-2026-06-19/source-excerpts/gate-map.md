# M1.1 Gate Map

## Gate A - Type System And Binder

Purpose:

- Introduce Tactical Query IR v1.
- Prove plan binding against typed catalog/operator metadata.
- Reject invalid or ambiguous plans visibly.

Evidence:

- `source-files/src/tqe/runtime/ir.py`
- `source-files/src/tqe/runtime/catalog.py`
- `source-files/src/tqe/runtime/binder.py`
- `source-files/src/tqe/verification/m1_1_gate_a.py`
- `artifacts/m1.1/binder-validation-report.json`

## Gate B - M1 Runtime Parity

Purpose:

- Execute the approved M1 plan through the new runtime.
- Match frozen M1 outputs and proof result IDs.
- Preserve legacy detector source/config hashes as an oracle.

Evidence:

- `source-files/src/tqe/runtime/executor.py`
- `source-files/src/tqe/verification/m1_1_gate_b.py`
- `artifacts/m1.1/runtime-execution.json`
- `artifacts/m1.1/parity-report.json`

## Gate C - Predicate Traces And Non-Match Evaluation

Purpose:

- Emit predicate-level traces for matching results.
- Evaluate forced windows/non-matches.
- Preserve `UNKNOWN` separately from `FALSE`.

Evidence:

- `source-files/src/tqe/verification/m1_1_gate_c.py`
- `artifacts/m1.1/predicate-trace-report.json`
- `artifacts/m1.1/non-match-inspection-report.json`

## Gate D - Dynamic Relation Proof

Purpose:

- Add `geometric_progressive_corridor` as a typed relation primitive.
- Prove breadth across real moments.
- Produce positive, negative, flicker-boundary, unknown, and invalid evidence.

Evidence:

- `source-files/src/tqe/runtime/relations.py`
- `source-files/src/tqe/verification/m1_1_gate_d.py`
- `artifacts/m1.1/relation-validation-report.json`
- `artifacts/m1.1/relation-visual-review/*.svg`

## Gate E - No-Code Experimental Composition

Purpose:

- Add an experimental opposite-corridor-after-shift plan as plan data.
- Prove it binds and executes without adding a Python detector.
- Produce evidence bundles and predicate traces for experimental results.

Evidence:

- `source-files/config/query-plans/opposite_corridor_after_shift.experimental.v1.json`
- `source-files/src/tqe/verification/m1_1_gate_e.py`
- `artifacts/m1.1/experimental-query-results.json`
- `artifacts/m1.1/experimental-evidence-manifest.json`

## Gate F - Developer Inspector And Reports

Purpose:

- Build a static inspector that can inspect approved and experimental plans.
- Show validation, result lists, replay data, predicate traces, non-match evaluations, and raw evidence.
- Keep it a developer artifact, not the final analyst UX.

Evidence:

- `source-files/src/tqe/inspector/m1_1.py`
- `source-files/src/tqe/verification/m1_1_gate_f.py`
- `artifacts/m1.1/inspector/manifest.json`
- `artifacts/m1.1/gate-f-verification-report.json`
