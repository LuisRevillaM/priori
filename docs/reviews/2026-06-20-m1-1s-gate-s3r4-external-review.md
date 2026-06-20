# M1.1S Gate S3R4 External Review

Decision: `APPROVE_S4_UNBLOCKED`

The external reviewer approved S3R4 and explicitly recommended proceeding to S4 without opening S3R5 unless S4 exposes a concrete regression in the corrected semantics.

Key approval claims:

- `TacticalQueryExecutor()` defaults to generic execution.
- Legacy persistence adapters are only entered under `legacy_m1_parity`.
- Duration units normalize through one conversion function with positive ceil semantics.
- `execute_persists_for()` partitions evaluated frames into PASS, FAIL, and UNKNOWN.
- `TRUE, TRUE, UNKNOWN` is indeterminate; `TRUE, TRUE, FALSE` is definitive failure.
- Anchors outside evaluated temporal coverage trace as UNKNOWN.
- Non-M1 proof executes actual generic predicate nodes.
- Generic traces are independent of contaminated candidates, accepted results, predicate traces, `_runtime_result`, and `_predicate_status`.
- Frozen M1 parity remains 180 results and 900 traces.

Opening S4 cleanup required by review:

- Split `execute_plan_from_path()` so it is generic by default.
- Add an explicitly named `execute_legacy_m1_plan_from_path()` helper for parity-only flows.
- Do not let S4 or Hermes use a legacy-forcing generic helper accidentally.

S4 discipline:

- Implement plan-driven classification and evidence projection using PASS/FAIL/UNKNOWN traces.
- Preserve M1 parity, but do not let legacy behavior influence generic execution.
- Do not add Hermes, UI polish, or new primitives during S4.
- After S4 passes, test the architecture with a second dissimilar tactical pattern.
