# F2-0 Acceptance Review — Round 1: REVISE (3 small items)

Reviewed 2026-07-02, branch `packet/f2-0` commits `4baafe3`+`17ed7f7`.
Verdict ACCEPT-WITH-FIXES. Verified: behavior neutrality (dispatch
relocation compared entry-by-entry; flag-gated hook mutates nothing; zero
cost when unset), zero drift (afl-09a, substrate-q4, n1d1 pass live with
pinned hashes; tree clean), findings census genuine (regenerated
byte-identical; spot-checked against emitted-vs-declared reality; single
class `undeclared_evidence_field`, lenient in the right direction), registry
and noop-debt ratchets exact, fences clean, suite 346 green under
independent invocation.

## Required for round 2 (same branch, append commits)

R1 — **Director design ruling (implement + document):** the envelope gains
an explicit `aux` payload slot preserving non-claim-bearing runtime metadata
WITH VALUES (`summary`, `source_results`, `anchor_source`, and anything else
the exclusion list currently reduces to key names). Contract, stated in the
module docstring: aux is non-evidentiary, never product-visible, never
consulted by trace/evidence projection; each F2 extraction packet must
either promote an aux item to a declared channel or leave it aux —
explicitly, per family. Correct the report's "without loss" claim
accordingly.

R2 — **Fix the env pollution:** the conformance smoke test runs
`main()` in-process and `scripts/runtime/envelope_conformance_report.py`
sets `TQE_ENVELOPE_CONFORMANCE=warn` (and mutates the logger) without
restore — every later test in the same process runs with shadow mode on.
Save/restore, or subprocess the smoke test. The "default off" invariant
must hold inside the suite process.

R3 — **Disclose the boundary-guard universe:** the guard detects catalog
identifiers only; three of the four audit-named leaks (eq/neq frame-id
fallbacks, the experimental-trace fabricator body, select_proof_results
labels) contain no catalog names and are invisible to it. Add the
disclosure to the report and the test's comments, plus a second freeze
list for those helper/label names so they ratchet too. Optional hardening
(take if cheap): freeze (name -> line,count) pairs instead of stripped
line text; derive the executor path from `executor.__file__`.

## Noted for later packets (no action now)

`CoverageChannel`'s field-name strings are the T6 shape reincarnated —
F2-Y replaces them with a typed status domain. Warn-mode paths that can
raise (`envelope.py:289,318`) should become crash-proof when F2-1 starts
leaning on shadow mode. Findings counts are per-record (~23 distinct
mismatch classes) — report tables should say so.

---

# F2-0 Acceptance Review — Round 2: ACCEPTED

Reviewed 2026-07-02, commit `4187f48`, merged as `54c1d1b`. R1: aux tier
preserves values (verified by hand on nested payloads) under an explicit
non-evidentiary contract; R2: env/logger restoration fixed with tests (the
default-off invariant holds inside the suite process); R3: detection-universe
disclosure plus a second exact-count freeze list for the non-catalog leak
surfaces. Suite 348 green under independent invocation. Phase F2 is open:
the envelope exists, the census (2544 findings) is the map, the ratchets
only tighten from here.
