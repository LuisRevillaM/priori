# SEAM-1 Report

Root cause: the certified Film Room path and runtime fallback answered one ask
with two interval populations. The committed R2-4 certified table used the full
declared per-regain partition (`denominator_status_field=stage_1_status`), while
the runtime fallback read rate evidence from returned chain-result rows. That
made runtime bounds depend on result ordering and `result_limit`; in the exam
exhibit the runtime fallback selected a 115-row chain-group denominator while
the certified path used the 2,811-row per-regain denominator.

Status: DELIVERED with evidence. DONE remains the review judgment.

## Changes

- Runtime executions now publish
  `execution.provenance.requested_evidence_sources`, a JSON-safe per-period
  summary of requested source outputs. Rate summaries omit nested
  `source_records` from the response and carry source-record counts/hashes.
- Film Room interval extraction uses certified table totals when the document
  hash matches a committed table; otherwise it uses the runtime source-output
  rate summaries. It no longer computes intervals from returned result order.
- Certified and runtime interval labels derive from the declared denominator.
  The counterattack flagship renders `CERTIFIED interval (per regain start)` or
  `RUNTIME EVIDENCE interval (per regain start)`.
- Numeric meaning clauses now refuse when they disagree with executable numeric
  operator parameters. I chose typed refusal rather than derivation because the
  incoming expression is an authored contract; silently rewriting the clause
  would hide the mismatch the exam found.
- Ranked execute responses no longer emit `requested_evidence: {}`. Rows with no
  projected requested evidence emit `evidence_contract` pointing to the
  inspection/stored-record/source-summary side channels.
- Payload shape and `moment_total_count` semantics are documented in
  `docs/EXECUTION_PAYLOAD_CONTRACT.md`. `moment_total_count` means distinct Film
  Room moments assembled for replay/overlay display; it is not the rate
  denominator.

## Evidence

Final R-AZ run:
`delivery/packets/seam-1-evidence/runs/2026-07-06T235726Z0000-1d70dc626a3f/`

| Item | Value |
| --- | --- |
| Producing script | `scripts/packets/seam1_evidence.py` |
| Script SHA-256 | `1d70dc626a3fc1d7e954c35f87baa496ff42d69a198e2197ff26706c1f30d875` |
| Evidence-stamped commit | `89813c130f35fd49ff6d406e11ba1203801ede23` |
| Evidence-stamped tree | `0558deb649a540e9de57b7b96deb4360418aca54` |
| Certified/runtime count equality | `true` |
| Certified counts | `A=1 B=0 C=2261 D1=0 D2=549 E=0 population=2811` |
| Runtime-source counts | `A=1 B=0 C=2261 D1=0 D2=549 E=0 population=2811` |
| Runtime partition count | `28` |
| Numeric mismatch probe | `MEANING_PARAMETER_MISMATCH`, refused |
| Focused evidence tests | PASS, 8 tests |

Cache provenance: the final evidence script does not consult the execution
cache. It compares the committed certified partitions to the same declared rate
partition shape consumed from runtime requested-evidence source summaries.
Workbench execution-cache identity was bumped to
`workbench_beta1c1_required_evidence_cache_v4` /
`required_evidence_complete_v2_with_source_summaries` so stale pre-SEAM execute
responses are not served for Film Room.

Earlier run
`delivery/packets/seam-1-evidence/runs/2026-07-06T235120Z0000-1d70dc626a3f/`
is retained as historical evidence from before the JSON-safety repair; the
final report relies on the run above.

## Verification

| Check | Tree/commit | Result |
| --- | --- | --- |
| Focused SEAM tests in final R-AZ evidence | `89813c1` | PASS, 8 tests in 0.017s |
| JSON-safe source-summary regression plus SEAM focused tests | working tree before `89813c1` | PASS, 9 tests in 0.018s |
| Full suite: `make PYTHON="uv run --no-sync python" test` | `d15b566`, tree `43c184fb4ef5657794330cd92f3e8f773b9432e4` | PASS, 572 tests in 478.072s; attestation `VERIFIED`, blocking reasons `[]` |

The full suite exceeded five minutes and was flagged during the run.

One prior full-suite run before `89813c1` failed in
279.921s because the new source-summary hash tried to hash a legacy runtime row
containing a pandas `Series`. `public_runtime_source_record` now normalizes
public values before hashing, and
`tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_public_runtime_source_record_is_json_safe_for_non_json_values`
covers that failure mode.

No alternate-index or clone route was used. Work was committed directly on
`packet/seam-1`; the branch-ref/worktree diff law for alternate routes was not
triggered. No provider/API billing was used in this packet beyond the existing
ChatGPT subscription surface; the SEAM-1 evidence run is local and deterministic.

Unrelated pre-existing untracked files were not touched:
`delivery/packets/r2-4-flagship/run-sidecar.local.json`, `docs/archive/`, and
`docs/visual-explainers/tactical-compilation-concept.png`.
