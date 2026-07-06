<!-- evidence_metadata: {"git_branch":"packet/perf-1","git_commit":"25812730cc95b79c1ad6d79ba6214a4f640caeb5","git_tree":"3f4211a8b78bd65f486b00d41bf23f892691bae8","produced_by":"scripts/packets/perf1_focused_test_evidence.py","producing_script_sha256":"ebc5bd558507d6b83891e9b88577b68c839be4f9582a1bc71adf0a288e76d402","run_dir":"delivery/packets/perf-1-evidence/fix-focused-tests/2026-07-06T195233Z0000-ebc5bd558507","run_started_at":"2026-07-06T19:52:33+00:00","schema_version":"perf1.focused_test_evidence_metadata.v1"} -->
# PERF-1 Fix Focused Test Evidence

- Status: `PASS`
- Duration: `85654.974 ms`
- Return code: `0`

| Test |
| --- |
| `tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_cache_key_mutates_for_every_director_component` |
| `tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_cache_key_canonicalizes_expanded_defaults` |
| `tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_persistent_cache_detects_corrupt_output_without_serving` |
| `tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_persistent_cache_detects_corrupt_preimage_without_serving` |
| `tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_persistent_cache_round_trips_frame_signal_outputs` |
| `tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_encode_cache_output_rejects_ambiguous_containers` |
| `tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_parallel_pool_falls_back_when_process_pool_is_unavailable` |
| `tests.test_m1_1_runtime.M11RuntimeTests.test_parallel_period_execution_matches_sequential_ordering` |

## Stdout

```

```

## Stderr

```
test_perf1_cache_key_mutates_for_every_director_component (tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_cache_key_mutates_for_every_director_component) ... ok
test_perf1_cache_key_canonicalizes_expanded_defaults (tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_cache_key_canonicalizes_expanded_defaults) ... ok
test_perf1_persistent_cache_detects_corrupt_output_without_serving (tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_persistent_cache_detects_corrupt_output_without_serving) ... ok
test_perf1_persistent_cache_detects_corrupt_preimage_without_serving (tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_persistent_cache_detects_corrupt_preimage_without_serving) ... ok
test_perf1_persistent_cache_round_trips_frame_signal_outputs (tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_persistent_cache_round_trips_frame_signal_outputs) ... ok
test_perf1_encode_cache_output_rejects_ambiguous_containers (tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_encode_cache_output_rejects_ambiguous_containers) ... ok
test_perf1_parallel_pool_falls_back_when_process_pool_is_unavailable (tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_perf1_parallel_pool_falls_back_when_process_pool_is_unavailable) ... ok
test_parallel_period_execution_matches_sequential_ordering (tests.test_m1_1_runtime.M11RuntimeTests.test_parallel_period_execution_matches_sequential_ordering) ... ok

----------------------------------------------------------------------
Ran 8 tests in 84.895s

OK
```
