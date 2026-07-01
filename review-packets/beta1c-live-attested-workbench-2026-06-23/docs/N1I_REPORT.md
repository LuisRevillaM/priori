# N1I — Agent AST Authoring Contract Repair

Status: `pass`
Generated: `2026-06-23T10:32:35+00:00`
Git head: `fd09735ff79c59a0db4c0117ce14d6ff4c68c33a`

## N1H Failure Mapping

- `active_ball_possession_anchor` -> `possession_segment` (registered_catalog_ref)
- `progressive_corridor_availability` -> `geometric_progressive_corridor_from_anchor_set` (registered_catalog_ref)
- `ball_enters_corridor_destination_region` -> `relation_destination_entry.entry_status + eq PASS` (registered_measurement_plus_operator)
- `progressive_corridor.candidates` -> `progressive_corridor.episodes for relation_destination_entry and progressive_corridor.anchor_evaluations for exists` (registered_output_names)
- `undeclared invocation threshold parameters` -> `declare recipe.parameters and use ParameterRef, or use inline TypedValue in node.parameters` (schema_contract)
- `missing draft_plan.anchor_source` -> `{'source_node_id': 'possession', 'output_name': 'anchors'}` (schema_contract)

## Regenerated Knowledge Pack

- Path: `generated/tactical-knowledge-pack.json`
- File SHA-256: `859159a41aac6b3c7eb77a032247758dbb8888edbbbc77ecfc81cec1079952d6`
- Semantic SHA-256: `0ede7a0a508a16dc18bb24ad08f6e1a74c5a419326e300b392e3aaece9a9eeb7`

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

Not run by this local gate. The next step is a single faithful deploy-side Hermes rerun using the unchanged scoped hero question. Beta 1C remains blocked unless `n1d1-verify` reaches VERIFIED.
