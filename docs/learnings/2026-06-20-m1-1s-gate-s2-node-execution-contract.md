# M1.1S Gate S2 Learning - Declared Inputs Must Preserve Semantic Cadence

Date: 2026-06-20

Fact: Moving an implementation from local `PeriodState` fields to declared `RuntimeValue` inputs can change semantics if the runtime value was normalized at a different cadence than the original source.

Decision: `defensive_outfield_centroid` now emits an explicit full-frame `FrameSignal` so `signed_lateral_shift` consumes the declared input without losing the full-frame defender centroid series needed by the frozen detector.

Learning: A node-execution contract is not proven by replacing `state.signals.get(...)` calls mechanically. It needs a substitution test showing that a compatible declared input actually changes downstream output, plus parity to catch cadence and ordering mistakes.

Evidence:

- `make m1-1-gate-s2-verify` passes and writes `artifacts/m1.1/gate-s2-verification-report.json`.
- The verifier scales the declared defensive-centroid input and confirms all 39 signed-shift values in the probe period change.
- The approved plan still returns 180 frozen results and 900 traces.

Follow-up: Gate S3 should remove the remaining M1 candidate anchor inspection from the generic target-evaluation path. The temporary target-inspection UNKNOWN fill preserves current Gate C behavior, but it is not the final generic anchor core.
