<!-- evidence_metadata: {"git_branch":"packet/perf-1","git_commit":"ccd511d8768857a0310a56f33702c703b55adc78","git_tree":"c626d7fd09ccdf6afd513b499e8356c7625f2857","key_schema":{"path":"delivery/packets/PERF-1-KEY-SCHEMA.md","sha256":"273517dc8be3f34e21bcfb86ccbe1678d81fddc94ba195a3420bc0e66c94dd5d"},"packet":{"path":"delivery/packets/PERF-1-cold-ask-latency.md","sha256":"da1ad086a2ff5d6fc15f7ff3bc5589d45239a7cdf10fe3dbe49ea8c410867b11"},"produced_by":"scripts/packets/perf1_equivalence_harness.py","producing_script_sha256":"9a9e54440adb86acb33c3edd60d8bb568cb18d0d4ae476087ecb10181750a83b","run_dir":"delivery/packets/perf-1-evidence/runs/2026-07-06T163909Z0000-9a9e54440adb","run_started_at":"2026-07-06T16:39:09+00:00","schema_version":"perf1.evidence_metadata.v1","script_args":{"long_run_threshold_seconds":300.0,"plan_set":[],"workers":4}} -->
# PERF-1 Timing Table

| plan_set_id | role | variant | hermes_ms | synthesis_ms | bind_ms | execute_external_ms | execute_total_ms | period_execution_ms | merge_apply_result_semantics_ms | period_count | result_count | persistent_hits | misses | detected_never_served | exceeded_long_run_threshold |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flagship_fragile_retention_rate | away | sequential |  |  | 5.419 | 461015.848 | 460982.999 | 460980.187 | 2.405 | 14 | 20 | 0 | 0 | 0 | True |
| flagship_fragile_retention_rate | away | optimized_cold |  |  | 5.419 | 144489.074 | 144480.400 | 144469.753 | 5.831 | 14 | 20 | 0 | 98 | 0 | False |
| flagship_fragile_retention_rate | away | optimized_warm |  |  | 5.419 | 52049.104 | 52033.414 | 52030.406 | 2.272 | 14 | 20 | 98 | 0 | 0 | False |
| flagship_fragile_retention_rate | home | sequential |  |  | 24.243 | 483502.975 | 483495.495 | 483491.834 | 3.290 | 14 | 20 | 0 | 0 | 0 | True |
| flagship_fragile_retention_rate | home | optimized_cold |  |  | 24.243 | 123909.895 | 123902.366 | 123893.548 | 3.761 | 14 | 20 | 0 | 98 | 0 | False |
| flagship_fragile_retention_rate | home | optimized_warm |  |  | 24.243 | 67343.032 | 67327.367 | 67324.569 | 2.075 | 14 | 20 | 98 | 0 | 0 | False |
| flagship_counterattack_initiation | away | sequential |  |  | 37.045 | 296479.636 | 296472.786 | 296460.335 | 0.507 | 14 | 1 | 0 | 0 | 0 | False |
| flagship_counterattack_initiation | away | optimized_cold |  |  | 37.045 | 62305.981 | 62297.866 | 62283.630 | 0.437 | 14 | 1 | 0 | 70 | 0 | False |
| flagship_counterattack_initiation | away | optimized_warm |  |  | 37.045 | 18994.634 | 18986.410 | 18971.824 | 0.447 | 14 | 1 | 70 | 0 | 0 | False |
| flagship_counterattack_initiation | home | sequential |  |  | 6.278 | 291598.363 | 291589.601 | 291577.164 | 0.508 | 14 | 0 | 0 | 0 | 0 | False |
| flagship_counterattack_initiation | home | optimized_cold |  |  | 6.278 | 62218.038 | 62209.591 | 62196.762 | 0.380 | 14 | 0 | 0 | 70 | 0 | False |
| flagship_counterattack_initiation | home | optimized_warm |  |  | 6.278 | 17025.290 | 17018.711 | 17005.631 | 0.367 | 14 | 0 | 70 | 0 | 0 | False |
| scp2_1_fragile_possession_state_known | away | sequential |  |  | 4.939 | 441952.784 | 441944.601 | 441941.376 | 2.865 | 14 | 20 | 0 | 0 | 0 | True |
| scp2_1_fragile_possession_state_known | away | optimized_cold |  |  | 4.939 | 112351.189 | 112342.900 | 112340.011 | 2.449 | 14 | 20 | 0 | 98 | 0 | False |
| scp2_1_fragile_possession_state_known | away | optimized_warm |  |  | 4.939 | 42510.422 | 42499.703 | 42497.294 | 1.786 | 14 | 20 | 98 | 0 | 0 | False |
| scp2_1_fragile_possession_state_known | home | sequential |  |  | 6.148 | 434549.599 | 434543.354 | 434540.184 | 2.792 | 14 | 20 | 0 | 0 | 0 | True |
| scp2_1_fragile_possession_state_known | home | optimized_cold |  |  | 6.148 | 115548.449 | 115540.082 | 115527.645 | 5.925 | 14 | 20 | 0 | 98 | 0 | False |
| scp2_1_fragile_possession_state_known | home | optimized_warm |  |  | 6.148 | 47551.209 | 47528.319 | 47525.974 | 1.665 | 14 | 20 | 98 | 0 | 0 | False |
| scp2_1_fragile_window_join_count_novel | single | sequential |  |  | 29.639 | 58633.579 | 58627.167 | 58623.712 | 0.593 | 2 | 13 | 0 | 0 | 0 | False |
| scp2_1_fragile_window_join_count_novel | single | optimized_cold |  |  | 29.639 | 25265.438 | 25257.829 | 25254.611 | 0.143 | 2 | 13 | 0 | 14 | 0 | False |
| scp2_1_fragile_window_join_count_novel | single | optimized_warm |  |  | 29.639 | 9476.002 | 9468.884 | 9465.836 | 0.115 | 2 | 13 | 14 | 0 | 0 | False |
| novel_live_scp2_3_cold_document | away | sequential | 75069 | 12 | 3.594 | 276025.838 | 276020.099 | 276007.966 | 0.491 | 14 | 1 | 0 | 0 | 0 | False |
| novel_live_scp2_3_cold_document | away | optimized_cold | 75069 | 12 | 3.594 | 55969.265 | 55960.761 | 55948.415 | 0.397 | 14 | 1 | 0 | 70 | 0 | False |
| novel_live_scp2_3_cold_document | away | optimized_warm | 75069 | 12 | 3.594 | 16070.494 | 16064.055 | 16051.244 | 0.364 | 14 | 1 | 70 | 0 | 0 | False |
| novel_live_scp2_3_cold_document | home | sequential | 75069 | 12 | 4.099 | 280823.674 | 280817.738 | 280804.528 | 0.575 | 14 | 0 | 0 | 0 | 0 | False |
| novel_live_scp2_3_cold_document | home | optimized_cold | 75069 | 12 | 4.099 | 57080.997 | 57070.338 | 57057.519 | 0.354 | 14 | 0 | 0 | 70 | 0 | False |
| novel_live_scp2_3_cold_document | home | optimized_warm | 75069 | 12 | 4.099 | 16253.098 | 16245.980 | 16233.002 | 0.375 | 14 | 0 | 70 | 0 | 0 | False |
