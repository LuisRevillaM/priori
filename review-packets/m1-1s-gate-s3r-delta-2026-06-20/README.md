# M1.1S Gate S3R Delta Review Packet

## What is this packet?

This is an external inspection packet for the M1.1S corrective gate named **S3R - Explicit Anchor Contract and Generic Temporal Semantics**.

It packages the committed implementation delta, controller review notes, verification reports, and the relevant source/config/schema files needed for a reviewer without repository access to evaluate whether the previous S1-S3 external review blockers were addressed before S4.

## Who is it for?

An external planning/review agent that does not have direct repository access.

## Packet type

`inspection_packet_only`

The packet includes representative source files, the full S3R commit patch, generated schemas, configs, docs, and verification artifacts. It does not include the full repository, Python environment, source dataset, or Makefile dependency graph needed to rerun every validation command independently.

## Review scope

Review commit:

`9febb97f681fd862b156a62316a90d6cfe75cb0c`

Branch:

`codex/m1-1-s1-ir-binder`

Scope is limited to whether S3R sufficiently addresses the external review decision recorded in `docs/2026-06-20-m1-1s-gate-s3-external-review.md` and unblocks S4 from an architecture/proof-gate standpoint.

## What changed?

- Plans now declare a single `anchor_source`.
- Binder requires the anchor source to resolve to an `episode_set` collection of `anchor_ref` records.
- `possession_segment` and `signed_lateral_shift` emit typed anchor records.
- Anchor IDs are generated from semantic identity: match, period, window/frame, and entities.
- Runtime anchor discovery reads only the plan-designated anchor source and deduplicates repeated representations.
- Runtime records live on `RuntimeValue.records` instead of hidden `provenance` payloads.
- Generic target/trace code supports non-M1 anchors without `wide_entry_*`, `block_shift_*`, or `shift_gate_*` fields.
- `persists_for` consumes generic tri-state Boolean truth series and does not bridge UNKNOWN frames.
- Frame/value length mismatches now fail instead of falling back to synthetic frame IDs.
- Node execution now returns `NodeExecutionResult` with resolved inputs, parameters, outputs, runtime values, warnings, and provenance.

## What is real?

- The S3R implementation is committed in `9febb97`.
- The included source files and patch are copied from that commit.
- The verification reports are generated artifacts from the local full repository.
- The S3R verifier reports 9 pass, 0 fail, 0 not-ready.
- Regression reports included in this packet show S1, S2, S3, Gate B, Gate C, R5, and parity checks passed after S3R.

## What is fixture/scenario/generated/local?

- `artifacts/*.json` are generated verification reports from local validation commands.
- `schemas/*` are generated schema/catalog artifacts refreshed after the implementation change.
- `configs/*` are real query-plan configs, copied into the packet for inspection.
- `source-files/*` are copied source files, not a runnable package.

## Validation run

See `validation-output.md` and `artifacts/`.

Important reported gates:

- `make m1-1-gate-s3r-verify`: pass, 9/0/0.
- `make test`: pass, 26 tests.
- `make m1-1-gate-b-verify`: pass, 14/0/0.
- `make m1-1-gate-c-verify`: pass, 10/0/0.
- `make m1-1-gate-r5-verify`: pass, 10/0/0.
- S1/S2/S3 regressions passed during the S3R run.

## What validation requires the full repo?

All `make` targets require the full repo, Python environment, dependencies, Makefile, and local artifacts/data. This packet is sufficient for inspection, not standalone execution.

## What is explicitly not proven?

- S4 rule-driven result emission is not implemented in this packet.
- Full UI/demo behavior is not in scope.
- This packet does not prove removal of all legacy M1 compatibility code. Some M1-specific functions and fields remain for frozen parity and legacy adapters. The S3R claim is narrower: the generic S4 path has an explicit anchor source, typed anchors, semantic identity, generic targeting/tracing, and generic temporal semantics.
- The external reviewer has not yet approved this S3R delta.

## Known gaps

See `known-gaps.md`.

## Review Map

Start here:

1. `docs/2026-06-20-m1-1s-gate-s3-external-review.md` - the blocking external decision S3R responds to.
2. `docs/gate-s3r-controller-review.md` - controller acceptance and residual risk.
3. `artifacts/gate-s3r-verification-report.json` - direct S3R proof checks.
4. `diffs/commit-9febb97-full.patch` - exact implementation delta.
5. `source-files/m1_1_gate_s3r.py` - verifier logic for the required proof tests.
6. `source-files/ir.py`, `binder.py`, `catalog.py`, `values.py`, `executor.py` - implementation surfaces.
7. `configs/*.json` and `schemas/*` - plan/schema/catalog contract changes.

