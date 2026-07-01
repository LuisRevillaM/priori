# M1.1S Gate S3R Controller Review - Explicit Anchor Contract And Generic Temporal Semantics

Date: 2026-06-20

Decision: ACCEPTED_CONTROLLER_ONLY

## Scope Reviewed

- `src/tqe/runtime/ir.py`
- `src/tqe/runtime/binder.py`
- `src/tqe/runtime/catalog.py`
- `src/tqe/runtime/executor.py`
- `src/tqe/runtime/values.py`
- `src/tqe/verification/m1_1_gate_s3r.py`
- approved and experimental query plans
- generated schema/catalog artifacts

## Acceptance Evidence

S3R addresses the external review findings before S4:

- plans now designate `anchor_source`;
- anchor source must bind to `episode_set<anchor_ref>` records;
- anchors are discovered only from the designated source;
- anchor IDs are semantic and stable under node rename;
- duplicate physical anchor records deduplicate;
- non-M1 anchors without block-shift fields can be targeted and traced;
- generic target/anchor code no longer carries `wide_entry`, `block_shift`, or `shift_gate` assumptions;
- runtime records live on `RuntimeValue.records`, not in provenance metadata;
- frame-signal length mismatch is a hard error;
- `persists_for` consumes tri-state Boolean truth series and emits generic predicate episodes;
- node execution returns an explicit `NodeExecutionResult`.

## Verification Run

- `make m1-1-gate-s3r-verify`: pass, 9/0/0
- `make m1-1-gate-s1-verify`: pass, 8/0/0
- `make m1-1-gate-s2-verify`: pass, 4/0/0
- `make m1-1-gate-s3-verify`: pass, 5/0/0
- `make m1-1-gate-b-verify`: pass, 14/0/0
- `make m1-1-gate-c-verify`: pass, 10/0/0
- `make m1-1-gate-r5-verify`: pass, 10/0/0
- `make test`: pass, 26 tests
- `git diff --check`: pass

## Controller Notes

This gate intentionally stops before S4. M1-specific primitive/result logic still exists, but generic anchor discovery, target inspection, and temporal persistence are no longer allowed to depend on M1 candidate/result side channels.

Proceeding to S4 is now reasonable from the controller perspective, pending any further external review requested by the owner.
