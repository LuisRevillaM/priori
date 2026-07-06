# PERF-1 Report

Status: DELIVERED with evidence. Review judgment remains external.

## Scope

Implemented PERF-1 cold-ask latency work on `packet/perf-1`:

- Parallel per-period execution with deterministic merge order.
- Persistent node output cache keyed by the director-authored schema.
- Full equivalence harness over the declared plan set.
- Fresh R-AZ timing evidence with true numbers, including long runs.
- Full suite on the committed tree.

No alternate-index or clone route was used for this packet. Work was committed
directly on `packet/perf-1`; the branch-ref/worktree diff law for alternate
routes was therefore not triggered.

## Key Schema

The node cache now uses one derivation function:

- `derive_node_cache_key(...)` in `src/tqe/runtime/executor.py`.
- Merkle upstream lineage: each non-source node preimage includes input name,
  source node id, output name, and upstream cache key.
- Expanded-default canonicalization: runtime parameter defaults are included in
  sorted canonical form.
- Per-scope data manifest entries: match/period positions, frames, events,
  orientation, players, teams, matches, and raw tracking entries feed the key.
- Perspective bindings are part of the key.
- Runtime code epoch is part of the key.
- Persistent entries are self-describing with full preimage and output content
  hash. Preimage/output mismatch returns `detected_never_served`, never a served
  value.

The persistent cache serializes runtime `FrameSignal` outputs and decodes them
back to runtime objects on load. A process-pool construction fallback was added
for sandbox environments that deny semaphore sysconf; normal process-backed
parallelism remains the primary backend.

## Evidence

Fresh post-fallback R-AZ evidence:

- Run: `delivery/packets/perf-1-evidence/runs/2026-07-06T180008Z0000-9a9e54440adb/`
- Equivalence: `perf1-equivalence.json`
- Timing table: `perf1-timing-table.md`
- Prior live document record: `novel_live_scp2_3_cold_document.document-record.json`
- Producing script: `scripts/packets/perf1_equivalence_harness.py`
- Script SHA-256: `9a9e54440adb86acb33c3edd60d8bb568cb18d0d4ae476087ecb10181750a83b`
- Evidence commit: `a8860a4e745a1eb7dfb52f9661d27baeba6cb08b`
- Evidence tree: `b6b1b891db01be4fe3025839d8b5b5b69b3057aa`

Acceptance result:

| Metric | Result |
| --- | --- |
| Declared plan sets | 6 |
| Executable plan sets | 5 |
| Refusal fixtures | 1 |
| Execution rows | 27 |
| Optimized cold byte-identical to sequential | true |
| Optimized warm byte-identical to sequential | true |
| Detected-never-served cache rows | 0 |
| Evidence elapsed | 4,009,750.441 ms |
| Rows over 300s | 4 |

The novel live plan was sourced from the committed SCP2-3 R-AZ live Film Room
response, not a new provider call:
`delivery/packets/scp2-3-evidence/runs/2026-07-06T073846Z0000-06516dd4e3d5/film-room-cold-response.json`.
The evidence table carries that response's Hermes/synthesis attribution:
Hermes 75,069 ms, synthesis 12 ms.

## Timing Summary

| Plan/role | Sequential ms | Optimized cold ms | Optimized warm ms |
| --- | ---: | ---: | ---: |
| flagship_fragile_retention_rate/away | 435,189.762 | 117,148.414 | 43,418.404 |
| flagship_fragile_retention_rate/home | 434,956.016 | 113,628.240 | 42,817.775 |
| flagship_counterattack_initiation/away | 288,607.550 | 60,719.630 | 16,845.379 |
| flagship_counterattack_initiation/home | 290,015.716 | 59,552.616 | 16,613.364 |
| scp2_1_fragile_possession_state_known/away | 446,363.405 | 124,974.910 | 53,199.177 |
| scp2_1_fragile_possession_state_known/home | 444,016.954 | 125,368.303 | 52,270.106 |
| scp2_1_fragile_window_join_count_novel/single | 61,470.286 | 26,577.855 | 10,079.694 |
| novel_live_scp2_3_cold_document/away | 293,967.143 | 67,390.165 | 18,650.846 |
| novel_live_scp2_3_cold_document/home | 284,798.150 | 63,044.264 | 17,520.964 |

Long-run flags:

- Evidence run exceeded five minutes.
- Four uncached sequential rows exceeded 300 seconds: retention away, retention
  home, SCP2-1 fragile possession away, SCP2-1 fragile possession home.
- `make test` exceeded five minutes.

## Verification

| Check | Tree/commit | Result |
| --- | --- | --- |
| Focused cache/fallback/parallel tests | `a8860a4` | PASS, 3 tests in 97.810s |
| Full R-AZ equivalence harness | `a8860a4` | PASS, all executable roles byte-identical |
| Full suite: `make test` | `6d0aa3c` | PASS, 567 tests in 530.657s |

Full suite environment warnings were non-blocking:

- Matplotlib used a temporary cache directory because `/Users/luisrevilla/.matplotlib`
  is not writable in the sandbox.
- Arrow emitted sandbox sysctl warnings for CPU cache/neon discovery.

## Notes

An earlier full-suite run at `a8a5591` failed because this sandbox denied
`ProcessPoolExecutor` semaphore sysconf during the parallel-period test:
`PermissionError: [Errno 1] Operation not permitted`. The executor now falls
back to a thread pool only when process-pool construction is unavailable, and a
unit test covers that fallback path.

Earlier PERF-1 evidence run
`delivery/packets/perf-1-evidence/runs/2026-07-06T163909Z0000-9a9e54440adb/`
is retained in history, but the final report relies on the fresh post-fallback
run listed above.

---

# PERF-1 Fix Round Report

Status: DELIVERED with evidence. Review judgment remains external.

## Mechanical Fixes

- Deleted dead lineage-less wrappers: `catalog_node_cache_key`,
  `shared_catalog_node_cache_key`, and `synthetic_cache_state`.
- Removed the dependent shared-cache wrapper test.
- Expanded cache-key mutation coverage to sub-components: runtime parameter
  default value, `match_id`, `period`, resolved parameter value, upstream key,
  code epoch, schema version, node version, data manifest entry, and perspective.
- Added persistent-cache corrupted-preimage detection coverage.
- Changed `encode_cache_output` to reject tuple and ndarray values loudly.
- Persistent-cache store rejection now records `persistent_store_rejected` and a
  progress event instead of writing an ambiguous cache entry.
- Harness variant summaries now include `execution_parallelism`, including pool
  backend.

## Fix Evidence

Focused test evidence:

- Run: `delivery/packets/perf-1-evidence/fix-focused-tests/2026-07-06T195233Z0000-ebc5bd558507/`
- Script: `scripts/packets/perf1_focused_test_evidence.py`
- Script SHA-256: `ebc5bd558507d6b83891e9b88577b68c839be4f9582a1bc71adf0a288e76d402`
- Evidence commit: `25812730cc95b79c1ad6d79ba6214a4f640caeb5`
- Result: PASS, 8 named tests, 85,654.974 ms.

Named focused tests:

- `tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_cache_key_mutates_for_every_director_component`
- `tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_cache_key_canonicalizes_expanded_defaults`
- `tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_persistent_cache_detects_corrupt_output_without_serving`
- `tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_persistent_cache_detects_corrupt_preimage_without_serving`
- `tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_persistent_cache_round_trips_frame_signal_outputs`
- `tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_encode_cache_output_rejects_ambiguous_containers`
- `tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_parallel_pool_falls_back_when_process_pool_is_unavailable`
- `tests.test_m1_1_runtime.M11RuntimeTests.test_parallel_period_execution_matches_sequential_ordering`

Filtered harness evidence for backend recording:

- Run: `delivery/packets/perf-1-evidence/runs/2026-07-06T195405Z0000-72254d3bd996/`
- Plan set: `scp2_1_fragile_window_join_count_novel`
- Result: all executable roles byte-identical.
- Recorded optimized backend: `process`.
- Optimized-cold node cache: `persistent_store_rejected=2`,
  `detected_never_served=0`.
- Optimized-warm node cache: `persistent_hits=12`,
  `persistent_store_rejected=2`, `detected_never_served=0`.

## Full Suite

| Check | Commit | Result |
| --- | --- | --- |
| Full suite: `make test` | `d18dc9a` | PASS, 568 tests in 510.398s |

The full-suite run exceeded five minutes. Matplotlib temporary-cache and Arrow
sysctl warnings were non-blocking sandbox warnings.

## Disclosures

Cache-entry working files were removed from evidence run directories before
commit. Reason: persistent node-cache entries are generated working cache state,
not review evidence; committed evidence is the self-stamped JSON/Markdown
summary produced by committed scripts. The deletion was targeted to untracked
`node-cache/` working directories only.

Abandoned run directories:

- `delivery/packets/perf-1-evidence/runs/2026-07-06T162827Z0000-9a9e54440adb/`
  came from a pre-commit refusal-only smoke run. Its untracked summary files
  were deleted and no committed evidence depends on it.
- `delivery/packets/perf-1-evidence/runs/2026-07-06T162912Z0000-9a9e54440adb/`
  came from the failed FrameSignal serialization evidence run. It produced no
  committed evidence files.
- Fix-round failed filtered run
  `delivery/packets/perf-1-evidence/runs/2026-07-06T194957Z0000-72254d3bd996/`
  exposed tuple rejection during persistent store. It was removed as untracked
  failed-run working state after the executor was changed to record unsupported
  persistent stores without serving or writing ambiguous entries.

Production activation disclosure:

- `render.yaml` activates persistent node cache with
  `TQE_NODE_CACHE_ROOT=/var/data/cache/node-output`.
- `render.yaml` activates four execution workers with
  `TQE_EXECUTION_WORKERS="4"`.
- This is deliberate PERF-1 scope, not incidental config churn; the director
  ratifies production activation at merge.

Branch-tree-vs-worktree statement:

- No alternate-index or clone route was used.
- Work was committed through the normal `packet/perf-1` worktree.
- Final verification command: `git diff packet/perf-1 -- .`; expected result is
  empty after this report is committed, and the final handoff will state the
  observed result.
