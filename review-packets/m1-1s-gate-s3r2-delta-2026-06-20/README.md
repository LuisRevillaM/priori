# M1.1S Gate S3R2 External Review Packet

## What is this packet?

This is an external inspection packet for the corrective revision after the prior S3R packet was rejected with `REJECT_KEEP_S4_BLOCKED`.

It asks the reviewer to decide whether **S3R2** now satisfies the unblock condition for S4:

> A semantically identified non-M1 anchor is evaluated through declared node inputs and a single generic temporal model, producing real PASS/FAIL/UNKNOWN traces without legacy record side channels.

## Who is it for?

An external reviewer or planning agent without repository access.

## Packet type

`inspection_packet_only`

The packet contains the exact S3R2 patch, representative source files, generated reports, configs, schemas, controller docs, and review notes. It does not contain the full repo, data, Python environment, or dependency graph needed to rerun all validations independently.

## Review scope

Commit under review:

`0ae27e1d014685a7b5516832b7eff1f4046e8b95`

Prior S3R commit:

`9febb97f681fd862b156a62316a90d6cfe75cb0c`

Scope is the delta from `9febb97..0ae27e1`, plus whether the strengthened S3R proof set addresses the external rejection recorded in `docs/2026-06-20-m1-1s-gate-s3r-external-review.md`.

## What changed?

- Runtime anchors are canonicalized from semantic identity: match, period, anchor frame, start/end frame, and entity references.
- Typed `anchor_ref` records reject non-canonical producer-supplied `anchor_id` values.
- Runtime anchor dedupe uses the canonical semantic key, not arbitrary supplied IDs.
- Multi-valued frame signals require explicit frame IDs.
- Predicate nodes execute through resolved input and parameter mappings.
- Generic `persists_for` has one Boolean frame-signal path and does not inspect record sidecars.
- Legacy M1 persistence behavior is isolated behind explicitly named compatibility adapters.
- Target inspection derives traces from declared predicate runtime outputs first.
- Non-M1 target proof now requires engine-derived PASS and FAIL traces, not only UNKNOWN traces.

## What is real?

- The S3R2 correction is committed in `0ae27e1`.
- The included diff is generated from `9febb97..HEAD`.
- The included reports were generated from the full local repository after S3R2.
- `gate-s3r-verification-report.json` reports 11 pass, 0 fail, 0 not-ready.
- Regression reports show Gate S1, Gate B/parity, Gate C, and Gate R5 passing after S3R2.

## What is fixture/scenario/generated/local?

- `artifacts/*.json` are generated validation reports.
- `source-files/*` are copied source files from the local repository at packet creation time.
- `schemas/*` and `configs/*` are copied for inspection context.
- This packet is not runnable by itself.

## Validation run

See `validation-output.md` and `artifacts/`.

Reported local validation:

- `make m1-1-gate-s3r-verify`: pass, 11/0/0.
- `make m1-1-gate-s1-verify`: pass, 8/0/0.
- `make m1-1-gate-b-verify`: pass, 14/0/0.
- `make m1-1-gate-c-verify`: pass, 10/0/0.
- `make m1-1-gate-r5-verify`: pass, 10/0/0.
- `make test`: pass, 26 tests.
- `git diff --check`: pass.

## What validation requires the full repo?

All `make` targets require the full repo, local Python environment, data/artifact context, and dependencies. Treat the JSON reports as internal execution evidence unless you can independently rerun the repository.

## What is explicitly not proven?

- S4 rule-driven result emission is not implemented.
- S5 alias evidence projection is not implemented.
- UI/demo behavior is not in scope.
- Legacy M1 compatibility code still exists. The claim is not that M1 was deleted; the claim is that the generic `persists_for`, anchor identity, predicate execution boundary, and non-M1 target tracing are now separated enough to build S4 without relying on hidden M1 side channels.

## Known gaps

See `known-gaps.md`.

## Review Map

Start here:

1. `docs/2026-06-20-m1-1s-gate-s3r-external-review.md` - rejection S3R2 responds to.
2. `docs/gate-s3r2-controller-review.md` - local controller review.
3. `artifacts/gate-s3r-verification-report.json` - strengthened proof checks.
4. `source-files/m1_1_gate_s3r.py` - verifier logic.
5. `diffs/s3r2-delta-9febb97-to-0ae27e1.patch` - exact corrective delta.
6. `source-files/executor.py` and `source-files/values.py` - primary implementation.

