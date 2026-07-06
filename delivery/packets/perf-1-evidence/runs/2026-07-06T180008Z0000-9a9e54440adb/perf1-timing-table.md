<!-- evidence_metadata: {"git_branch":"packet/perf-1","git_commit":"a8860a4e745a1eb7dfb52f9661d27baeba6cb08b","git_tree":"b6b1b891db01be4fe3025839d8b5b5b69b3057aa","key_schema":{"path":"delivery/packets/PERF-1-KEY-SCHEMA.md","sha256":"273517dc8be3f34e21bcfb86ccbe1678d81fddc94ba195a3420bc0e66c94dd5d"},"packet":{"path":"delivery/packets/PERF-1-cold-ask-latency.md","sha256":"da1ad086a2ff5d6fc15f7ff3bc5589d45239a7cdf10fe3dbe49ea8c410867b11"},"produced_by":"scripts/packets/perf1_equivalence_harness.py","producing_script_sha256":"9a9e54440adb86acb33c3edd60d8bb568cb18d0d4ae476087ecb10181750a83b","run_dir":"delivery/packets/perf-1-evidence/runs/2026-07-06T180008Z0000-9a9e54440adb","run_started_at":"2026-07-06T18:00:08+00:00","schema_version":"perf1.evidence_metadata.v1","script_args":{"long_run_threshold_seconds":300.0,"plan_set":[],"workers":4}} -->
# PERF-1 Timing Table

| plan_set_id | role | variant | hermes_ms | synthesis_ms | bind_ms | execute_external_ms | execute_total_ms | period_execution_ms | merge_apply_result_semantics_ms | period_count | result_count | persistent_hits | misses | detected_never_served | exceeded_long_run_threshold |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flagship_fragile_retention_rate | away | sequential |  |  | 5.040 | 435189.762 | 435164.070 | 435161.204 | 2.433 | 14 | 20 | 0 | 0 | 0 | True |
| flagship_fragile_retention_rate | away | optimized_cold |  |  | 5.040 | 117148.414 | 117140.396 | 117137.887 | 1.875 | 14 | 20 | 0 | 98 | 0 | False |
| flagship_fragile_retention_rate | away | optimized_warm |  |  | 5.040 | 43418.404 | 43411.250 | 43408.743 | 1.895 | 14 | 20 | 98 | 0 | 0 | False |
| flagship_fragile_retention_rate | home | sequential |  |  | 7.717 | 434956.016 | 434948.414 | 434944.364 | 3.643 | 14 | 20 | 0 | 0 | 0 | True |
| flagship_fragile_retention_rate | home | optimized_cold |  |  | 7.717 | 113628.240 | 113620.406 | 113618.274 | 1.589 | 14 | 20 | 0 | 98 | 0 | False |
| flagship_fragile_retention_rate | home | optimized_warm |  |  | 7.717 | 42817.775 | 42810.728 | 42808.371 | 1.736 | 14 | 20 | 98 | 0 | 0 | False |
| flagship_counterattack_initiation | away | sequential |  |  | 4.758 | 288607.550 | 288601.672 | 288584.215 | 0.859 | 14 | 1 | 0 | 0 | 0 | False |
| flagship_counterattack_initiation | away | optimized_cold |  |  | 4.758 | 60719.630 | 60711.009 | 60696.942 | 0.540 | 14 | 1 | 0 | 70 | 0 | False |
| flagship_counterattack_initiation | away | optimized_warm |  |  | 4.758 | 16845.379 | 16838.305 | 16824.533 | 0.385 | 14 | 1 | 70 | 0 | 0 | False |
| flagship_counterattack_initiation | home | sequential |  |  | 4.665 | 290015.716 | 290009.662 | 289997.314 | 0.470 | 14 | 0 | 0 | 0 | 0 | False |
| flagship_counterattack_initiation | home | optimized_cold |  |  | 4.665 | 59552.616 | 59544.029 | 59531.321 | 0.363 | 14 | 0 | 0 | 70 | 0 | False |
| flagship_counterattack_initiation | home | optimized_warm |  |  | 4.665 | 16613.364 | 16606.865 | 16594.157 | 0.364 | 14 | 0 | 70 | 0 | 0 | False |
| scp2_1_fragile_possession_state_known | away | sequential |  |  | 4.913 | 446363.405 | 446355.590 | 446351.016 | 4.164 | 14 | 20 | 0 | 0 | 0 | True |
| scp2_1_fragile_possession_state_known | away | optimized_cold |  |  | 4.913 | 124974.910 | 124966.906 | 124961.424 | 3.097 | 14 | 20 | 0 | 98 | 0 | False |
| scp2_1_fragile_possession_state_known | away | optimized_warm |  |  | 4.913 | 53199.177 | 53188.121 | 53184.764 | 2.587 | 14 | 20 | 98 | 0 | 0 | False |
| scp2_1_fragile_possession_state_known | home | sequential |  |  | 15.848 | 444016.954 | 444008.081 | 444003.736 | 3.923 | 14 | 20 | 0 | 0 | 0 | True |
| scp2_1_fragile_possession_state_known | home | optimized_cold |  |  | 15.848 | 125368.303 | 125357.290 | 125340.868 | 5.980 | 14 | 20 | 0 | 98 | 0 | False |
| scp2_1_fragile_possession_state_known | home | optimized_warm |  |  | 15.848 | 52270.106 | 52242.810 | 52239.795 | 2.326 | 14 | 20 | 98 | 0 | 0 | False |
| scp2_1_fragile_window_join_count_novel | single | sequential |  |  | 22.883 | 61470.286 | 61463.480 | 61460.349 | 0.176 | 2 | 13 | 0 | 0 | 0 | False |
| scp2_1_fragile_window_join_count_novel | single | optimized_cold |  |  | 22.883 | 26577.855 | 26569.723 | 26566.413 | 0.170 | 2 | 13 | 0 | 14 | 0 | False |
| scp2_1_fragile_window_join_count_novel | single | optimized_warm |  |  | 22.883 | 10079.694 | 10072.999 | 10069.676 | 0.173 | 2 | 13 | 14 | 0 | 0 | False |
| novel_live_scp2_3_cold_document | away | sequential | 75069 | 12 | 4.020 | 293967.143 | 293960.819 | 293946.809 | 1.488 | 14 | 1 | 0 | 0 | 0 | False |
| novel_live_scp2_3_cold_document | away | optimized_cold | 75069 | 12 | 4.020 | 67390.165 | 67381.800 | 67336.751 | 0.656 | 14 | 1 | 0 | 70 | 0 | False |
| novel_live_scp2_3_cold_document | away | optimized_warm | 75069 | 12 | 4.020 | 18650.846 | 18644.032 | 18629.861 | 0.441 | 14 | 1 | 70 | 0 | 0 | False |
| novel_live_scp2_3_cold_document | home | sequential | 75069 | 12 | 4.674 | 284798.150 | 284791.355 | 284777.735 | 0.714 | 14 | 0 | 0 | 0 | 0 | False |
| novel_live_scp2_3_cold_document | home | optimized_cold | 75069 | 12 | 4.674 | 63044.264 | 63035.747 | 63022.784 | 0.370 | 14 | 0 | 0 | 70 | 0 | False |
| novel_live_scp2_3_cold_document | home | optimized_warm | 75069 | 12 | 4.674 | 17520.964 | 17514.066 | 17500.443 | 0.382 | 14 | 0 | 70 | 0 | 0 | False |
