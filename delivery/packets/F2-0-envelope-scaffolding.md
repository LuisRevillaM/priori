# Work Packet F2-0 — Capability Envelope Scaffolding

Issued: 2026-07-02 by the project director. First packet of phase F2.
Governing design: `docs/adr/0012-f2-executor-extraction.md` (read fully
first — this packet implements its §1 scaffolding with ZERO behavior
change).

## Ground rules

- Branch `packet/f2-0` off `codex/afl08-passport-loop` (current tip or
  later). Acceptance review gates the merge.
- Read: the ADR, `docs/audits/FOUNDATION_AUDIT_2026-07-01.md` (core-runtime
  section), prior packet reviews (F1-B/C/D, DOC-1) for the acceptance
  standard.
- Standing bar: full-suite table on the committed tree in your report.
- Fences: no changes to `semantic-registry/`, `generated/`,
  `frozen-expectations/`, `delivery/n1d/`, `artifacts/`; no catalog
  parameter/output/evidence changes; NO behavior change anywhere.
- **The zero-drift bar (this packet's defining constraint):** every gate
  that passed before must pass after with byte-identical results —
  bound_plan_hashes, result_ids, signatures, evidence. Pure scaffolding.

## Scope

### 1. Envelope types — `src/tqe/runtime/envelope.py` (new)

Typed dataclasses/pydantic models per ADR §1: `CapabilityEnvelope` with
named output channels (episode set / frame signal / anchor evaluations /
scalar), an optional-for-now coverage channel slot, evidence records, and
witness references. Design them by SURVEYING what the 44 capabilities
actually emit into `state.signals` today (the `X` / `X_records` pairing,
`anchor_evaluations`, frame signals) so the envelope can represent all of it
without loss. Document each field.

### 2. Conformance checker — same module or sibling

A function that, given a catalog entry and an envelope, verifies: every
declared output has a channel of the declared temporal type; no undeclared
channels; evidence fields ⊆ declared; enum outputs within declared domains.
In this packet it is CALLED IN SHADOW MODE: wired into node execution behind
an env flag (`TQE_ENVELOPE_CONFORMANCE=warn|off`, default `off`), logging
findings without failing. Include a script or make target
(`envelope-conformance-report`) that runs one match through representative
plans with the flag on and writes a findings report to
`artifacts/check-runs/` — this report is the input to later packets, NOT a
gate yet.

### 3. Dispatch registry — formalize what exists

Today dispatch is a dict built in the executor. Extract it to
`src/tqe/runtime/capabilities/__init__.py` (new package): an explicit
registry mapping catalog identifier -> implementation callable, built at
import, with a test asserting every bound capability in the runtime manifest
has exactly one registered implementation and no registration lacks a
catalog entry (this test will EXPOSE the noop landmines —
`wide_channel_dwell`, `shift_persistence`, `robust_team_width`,
`analysis_rate` map to `primitive_noop` for names absent from the catalog.
Do NOT delete them in this packet (that is F2-X); register them in an
explicit `LEGACY_NOOP` allowlist the test acknowledges, so the debt is
visible and pinned.)

### 4. CI guard — capability names out of shared code

Add a test (house location: `tests/test_executor_boundaries.py`) that greps
the SHARED sections of `executor.py` (everything that is not a
`primitive_*`/`relation_*` implementation function) for capability
identifiers from the catalog, and fails on new introductions. Seed it with
an explicit, commented allowlist of the KNOWN existing leaks (audit items:
`destination_entry_relation_id_for_source`, the eq/neq frame-id fallbacks,
`experimental_predicate_traces_for_result`, `select_proof_results` labels)
— the test's job in this packet is to FREEZE the leak set so it can only
shrink. Later packets remove entries.

### 5. Nothing else

No implementation moves, no parameter changes, no deletion of shadow
defaults (F2-1), no behavior change. If the survey in §1 reveals something
the envelope cannot represent, document it in the report rather than
changing runtime behavior.

## Required tests

Envelope construction/validation unit tests (valid, undeclared channel,
missing declared, wrong temporal type, enum out of domain); registry
completeness test (§3); boundary-freeze test (§4); conformance shadow-run
smoke test on synthetic data.

## Deliverables

1. Branch `packet/f2-0`, focused commits.
2. Full-suite table on the committed tree (expectation: identical
   pass/fail set to the frontier — currently fully green).
3. Zero-drift proof: run `make scp-0-verify afl-passport-verify
   afl-09a-verify n1d1-verify` plus two representative afl gates before and
   after — byte-identical results, git status clean after each.
4. `delivery/packets/F2-0-REPORT.md`: the signals-survey summary (what the
   envelope had to represent, anything it can't), the conformance shadow
   report findings count by capability, the frozen leak allowlist, the
   noop debt list, full-suite table.
