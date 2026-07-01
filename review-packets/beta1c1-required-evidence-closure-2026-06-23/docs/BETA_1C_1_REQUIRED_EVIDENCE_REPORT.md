# Beta 1C.1 - Required Evidence Contract Closure

## Decision

Implemented and locally verified.

## Defect Closed

The deployed Beta 1C hero could reuse a stale cached execution whose underlying record was incomplete:

```text
execution.status = incomplete
requested_evidence_failure_count = 14
possession_start_frame_id = null on every result
```

Current deterministic execution resolves the required possession-start evidence for the complete hero result set.

## Changes

- Public `execute_query_plan` responses now expose `execution_status`, `execution_complete`, `requested_evidence_failure_count`, and `requested_evidence_failures`.
- Execution records carry the same completeness fields.
- Execution cache identity was bumped to `workbench_beta1c1_required_evidence_cache_v3`, preventing reuse of stale incomplete hero cache entries.
- N1D now audits and pins the required-evidence contract:
  - `execution_status == pass`
  - `requested_evidence_failure_count == 0`
  - every required evidence alias is non-null for every returned result
- N1D.1 now fails closed unless the N1D manifest and committed Hermes-origin bundle both prove complete required evidence.
- The committed Hermes-origin bundle host pipeline was refreshed under the corrected runtime.
- Workbench renders incomplete executions visibly if they ever occur.
- Product copy now says: `Verified Hermes-authored composition` and explains it is loaded from a previously attested Hermes session.

## Current Proof

N1D pinned required-evidence audit:

```text
execution_status: pass
requested_evidence_failure_count: 0
result_count: 14
all_required_aliases_resolved: true
required aliases:
  corridor_duration_seconds
  corridor_open_frame_id
  destination_entry_status
  destination_region
  destination_time_to_entry_seconds
  possession_start_frame_id
  relation_id
```

## Verification

```text
make m1-2-gate-s2i-verify
make n1d-freeze
make n1d-verify
make n1d1-verify
make n1c-verify
make n1i-verify
.venv/bin/python -m unittest tests.test_workbench_beta0_contract
.venv/bin/python -m unittest discover tests
npm --prefix apps/workbench-alpha run test:acceptance
```

Results:

```text
S2I-A: 25 passed, 0 failed
N1D: 15 passed, 0 failed
N1D.1: VERIFIED
N1C: 8 passed, 0 failed
N1I: 10 passed, 0 failed
Workbench backend contract: 14 tests OK
Python discovery: 53 tests OK
Workbench acceptance: 16 Playwright tests passed
```
