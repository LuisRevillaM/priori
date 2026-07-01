# M1.2 S0R2 Trust Boundary Review Packet

Date: 2026-06-21

Packet type: `inspection_packet_only`

Commit under review: `a003bc898560570445a00feaafc2507d4036d21c`

Branch: `codex/m1-1-s1-ir-binder`

## What This Is

This packet is for external review of the S0R2/S1R2 correction before M1.2 S2
Hermes drafting begins. It packages the committed source changes, generated
capability context, verifier reports, representative handles, replay artifacts,
and validation summaries.

## Review Scope

Review whether M1.2 now has a safe enough pre-Hermes boundary:

- explicit Hermes vs host/manual caller profiles;
- host-owned execution confirmation;
- opaque create-once handles;
- Hermes-only `EXPERIMENTAL` authoring;
- `agent_authorable` enforcement;
- trusted frozen M1 approved recipe selection;
- no filesystem paths in model-visible replay responses;
- canonical target-time replay lookup;
- model-visible dispatcher response-schema validation;
- S0/S1 verifiers proving the above without starting Hermes.

## What Is Real

- The implementation is committed in `a003bc8`.
- S0, S1, aggregate M1.2, M1.1 S7R, and unit checks were run locally and passed.
- The manual workshop artifacts were regenerated through the same dispatcher
  surface future Hermes calls, using host/manual authority where required.
- Replay artifacts are real coordinate windows generated from canonical data.

## Fixture, Local, Or Generated

- `artifacts/manual-workshop-data.json`, replay JSON files, handles, and reports
  are generated local evidence from the verifier run.
- This packet is not a standalone repo copy. It contains selected source files,
  diffs, reports, and artifacts for inspection.
- External reviewers cannot independently rerun the Make targets from only this
  packet.

## Validation Run

- `python -m py_compile src/tqe/workshop/m1_2.py src/tqe/verification/m1_2_gate_s0.py src/tqe/verification/m1_2_gate_s1.py`: pass.
- `make m1-2-verify`: pass, 2/2.
- `make m1-1-gate-s7r-verify`: pass, 13/13.
- `make test`: pass, 27 tests OK.

See `validation-output.md` and `commands/validation-summary.txt`.

## Not Proven

- Hermes natural-language drafting is not implemented or tested.
- S2 clarification behavior is not implemented.
- S3 revision diffs and immutable recipe loop are not completed.
- This does not prove broader tactical generality beyond the existing M1 recipe
  and experimental corridor composition.

## Review Map

- `scope.md`: review target and assumptions.
- `changed-files.md`: changed-file inventory.
- `diffs/head.patch`: full committed patch.
- `source-excerpts/src/tqe/workshop/m1_2.py`: workshop tool boundary.
- `source-excerpts/src/tqe/verification/m1_2_gate_s0.py`: S0 verifier.
- `source-excerpts/src/tqe/verification/m1_2_gate_s1.py`: S1 verifier.
- `source-excerpts/generated/capability-context.json`: Hermes-visible capability
  context.
- `reports/`: generated pass reports.
- `artifacts/`: representative handles, replay windows, recipe, and workshop
  data.
- `known-gaps.md`: explicit limitations and non-goals.

## Requested Reviewer Decision

Return one of:

```text
APPROVE_S2_UNBLOCKED
APPROVE_WITH_REQUIRED_CHANGES_BEFORE_S2
REJECT_KEEP_S2_BLOCKED
```

Focus on whether S2 can safely add Hermes as a client of this boundary without
another runtime architecture repair cycle.
