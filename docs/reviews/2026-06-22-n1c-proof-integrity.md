# N1C Proof Integrity Review

Decision: APPROVE_N1C_WORKBENCH_EXPOSURE_READY

N1C closes the proof-integrity gaps raised after the post-N1B live Hermes run. It does not rerun the live model or broaden the tactical runtime. It makes the existing backend novel-composition proof auditable enough to expose in Workbench with honest provenance and evidence.

## Evidence

- Verifier: `src/tqe/verification/n1c.py`
- Command: `make n1c-verify`
- Result: `8 pass / 0 fail`
- Manifest: `artifacts/n1c/n1c-canonical-freeze-manifest.json`
- Manifest SHA-256: `423b80651cf53c2850c0558ed12c1334b703eb44946572c5dad48cbda2ffcd12`
- Report: `artifacts/n1c/n1c-verification-report.json`
- Report SHA-256: `7599dea004f267e9762f575e997e0f50f41b640f9daedba0fcada9eeeb94fcaa`
- Knowledge-pack file SHA-256: `7cf720c8210b1d81f12574c5c8299a1dc309930eb1ce17f8eb934d8814119962`
- Knowledge-pack semantic SHA-256: `fd6d0843d32cc9632bc864b3dad11af4fea060fa2a5fd827196b3458af37b7a0`

## What Passed

- A canonical freeze/provenance manifest now records source, knowledge pack, Hermes configuration, MCP allowlist, frozen hero question, live draft/bound/execution/replay IDs, structural fingerprint, runtime hashes, and deployed/canonical data hashes.
- The current knowledge-pack file and semantic hashes are reconciled and labeled separately.
- Actual generic node execution drives `relation_destination_entry` through PASS, FAIL, and UNKNOWN.
- The bound `entry_status == PASS` predicate preserves UNKNOWN instead of treating it as false.
- Runtime values now enforce declared enum output domains, with scope limited to outputs that declare `allowed_values`.
- Executor `RuntimeParameters` access remains guarded by declared host defaults or checked-in recipe parameters.
- Destination-entry evidence now emits `entry_mode`: `PRESENT_AT_OPEN`, `ENTERED_AFTER_OPEN`, `NOT_ENTERED`, or `UNKNOWN`.

## Boundary

This accepts proof integrity for Workbench exposure of the existing N1 backend loop. It does not claim final UI polish, sealed frontier evaluation, or broad catalog-wide enum-domain completeness for outputs that do not declare allowed values.

Next: expose the N1 loop in Workbench with `HERMES_NOVEL_COMPOSITION` provenance, typed interpretation, host confirmation, cache status, result evidence, traces, replay, and honest `entry_mode` wording.
