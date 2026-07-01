# N1I — Agent AST Authoring Contract Repair

Status: `pass`
Generated: `2026-06-23T06:20:15+00:00`
Faithful rerun deploy commit: `7b7bf8424f9f2d440315aa8a6cdbcf44b923f95d`

## N1H Failure Mapping

- `active_ball_possession_anchor` -> `possession_segment` (registered_catalog_ref)
- `progressive_corridor_availability` -> `geometric_progressive_corridor_from_anchor_set` (registered_catalog_ref)
- `ball_enters_corridor_destination_region` -> `relation_destination_entry.entry_status + eq PASS` (registered_measurement_plus_operator)
- `progressive_corridor.candidates` -> `progressive_corridor.episodes for relation_destination_entry and progressive_corridor.anchor_evaluations for exists` (registered_output_names)
- `undeclared invocation threshold parameters` -> `declare recipe.parameters and use ParameterRef, or use inline TypedValue in node.parameters` (schema_contract)
- `missing draft_plan.anchor_source` -> `{'source_node_id': 'possession', 'output_name': 'anchors'}` (schema_contract)

## Regenerated Knowledge Pack

- Path: `generated/tactical-knowledge-pack.json`
- File SHA-256: `05bc2b57b6bc399c5e9a1d10b5cad3213a1f70215b42941b21b7d8cee34b482f`
- Semantic SHA-256: `87d78d0f57bd829f4b8e391649e82b890d44a30d481f9bf702b71df10d9d3c39`

## Checks

- `pass` n1i.n1h_failure_extracted: N1H unknown catalog refs/operators were extracted from the origin bundle.
- `pass` n1i.describe_typed_query_plan_contract: describe_capability exposes the exact typed query plan node schemas.
- `pass` n1i.describe_destination_path_contract: describe_capability exposes exact valid refs/operators for destination entry composition.
- `pass` n1i.relation_destination_entry_contract_complete: relation_destination_entry describes its input/output contract and entry_status output.
- `pass` n1i.trusted_wrapper_absent_from_authorable_nodes: The trusted wrapper is not present in the generated authorable node set.
- `pass` n1i.failed_names_not_suggested: The generated authoring contracts do not suggest the failed N1H invented names.
- `pass` n1i.manual_ast_uses_visible_contract_only: The manually authored model-profile AST uses only visible refs/operators/output names.
- `pass` n1i.manual_ast_validates: A model-profile manually authored AST using the visible contract validates.
- `pass` n1i.inline_result_seed_executes_without_global_fallback: relation_destination_entry executes with inline result_id_seed and no result_id_seed_hash global.
- `pass` n1i.knowledge_pack_checks_pass: The regenerated tactical knowledge pack passes its safety and consistency checks.

## Faithful Rerun Status

Completed through the faithful Render runner with the unchanged scoped hero question. Beta 1C was not started.

### First N1I Render attempt

- Deploy commit: `437ee70c0c5a8fea936943a749a92f5157c861f5`
- Job id: `n1f_674eb16c053b47b4`
- Outcome: `failed`
- Stage: `failed`
- Blocker: `KeyError: 'result_id_seed_hash'`
- Diagnosis: `relation_destination_entry` supplied `result_id_seed` inline, but the executor eagerly evaluated the fallback `state.params.text("result_id_seed_hash")`.
- Resolution: `src/tqe/runtime/executor.py` now reads the inline resolved parameter before consulting the global fallback, and the N1I local gate includes `n1i.inline_result_seed_executes_without_global_fallback`.

### Second N1I Render attempt

- Deploy commit: `7b7bf8424f9f2d440315aa8a6cdbcf44b923f95d`
- Job id: `n1f_7a1f1b8013294534`
- Session id: `20260623_061107_59df89`
- Status: `succeeded`
- Stage: `bundle_exported`
- Draft plan id: `draft_cca93c8cac63ef66`
- Hermes draft hash: `cca93c8cac63ef66eb62a0479ca340cc4a926b2222d64fedbc5ef857d115663c`
- Bound plan id: `bound_68e7d1a7cd29d7bd`
- Bound plan hash: `68e7d1a7cd29d7bd0490765694d8f4700c882046510e78a2579b8845358f1bb0`
- Execution id: `exec_c4feb86ed01eaa93`
- Results: `14`
- Exported origin bundle path: `delivery/n1d/n1f-origin-bundle.json`
- Exported origin bundle file SHA-256: `6c570bcc82d9d617d0d1a7678a082e81adb579d28992eae01ac9e6e94feb7912`
- Origin bundle canonical SHA-256: `14c6104cec50703ca8f161925b1ef8fce047647d43dbebd5c42fa86e3ca55060`
- Raw Hermes decision SHA-256: `c2b0c61fbad6c0f34d2a04cd051d6a229122436ec64b075f93adbc400e0699f3`
- Ordered MCP tool-call trace SHA-256: `b6073d4a98ac5200549b34b8088f00dad05690cf6ee8150ccc6cebf89d995d3d`

Hermes authored the two required N1D evidence aliases directly:

- `destination_entry_mode`
- `destination_time_to_entry_seconds`

The host augmentation was therefore a no-op on requested evidence. N1D.1 now treats that as valid only when the plan is structurally identical after stripping evidence, no Hermes evidence is removed, any host-added aliases are a subset of the two allowed aliases, and the final plan contains both required aliases.

## N1D/N1D.1 Pinning

- N1D manifest path: `delivery/n1d/n1d-canonical-freeze-manifest.json`
- N1D manifest SHA-256: `39e2560c31b27917cad1ce75e7e2b707eed7dd7e448167d89065c868ce01bea6`
- N1D.1 attestation path: `delivery/n1d/n1d1-attestation.json`
- N1D.1 attestation SHA-256: `e2cb156609bdb92c205e83ea6392ee4f2e2c955b424dab428842540179985555`
- N1D.1 status: `VERIFIED`
- N1D.1 blocking reasons: `[]`
- Entry-mode distribution: `PRESENT_AT_OPEN=7`, `ENTERED_AFTER_OPEN=7`, `NOT_ENTERED=0`, `UNKNOWN=0`

## Final Verification

- `make n1d-verify`: pass, `12/12`
- `make n1d1-verify`: pass, `VERIFIED`
- `make n1c-verify`: pass, `8/8`
- `make n1i-verify`: pass, `10/10`
- `.venv/bin/python -m unittest tests.test_n1d1_attestation tests.test_workbench_beta0_contract tests.test_m1_1_binder tests.test_m1_1_runtime`: pass, `45` tests

## Runner Disable

The temporary Render runner was disabled after artifact export.

- Disable deploy id: `dep-d8t2bc67r5hc73eeeh30`
- Disable deploy commit: `7b7bf8424f9f2d440315aa8a6cdbcf44b923f95d`
- Health check after deploy: `/healthz` returned `200`
- Runner status after deploy: `/api/n1f/status` returned `403 N1E_RUNNER_UNAVAILABLE`

## Caveats

- The live faithful rerun was executed on deploy commit `7b7bf8424f9f2d440315aa8a6cdbcf44b923f95d`. The final local report and deterministic capability-context timestamp fix are committed afterward so local freeze verification remains stable.
- `HERMES_NOVEL_COMPOSITION` remains blocked from Workbench exposure until this N1I/N1D.1 result is reviewed and accepted. No Beta 1C UI work was started.
