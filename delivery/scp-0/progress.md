# SCP-0 Progress Ledger

| Slice | Status | Evidence | Notes |
| --- | --- | --- | --- |
| SCP-0A | DONE | `src/tqe/semantic_registry/models.py`, `src/tqe/semantic_registry/runtime_manifest.py`, `src/tqe/semantic_registry/generate.py`, `semantic-registry/schemas/semantic-registry.schema.json`, `generated/semantic-registry/runtime-manifest.json`, `tests/test_scp0_semantic_registry.py` | Schemas, runtime introspection, registry lock generation, and fail-closed validation rails implemented. |
| SCP-0B | DONE | `semantic-registry/registry.yaml`, `semantic-registry/atlas/raw/five_year_capability_manifest.yaml`, `generated/semantic-registry/*.json`, `artifacts/scp-0/verification-report.json` | Current runtime capabilities, operators, recipes, validated AI composition, raw atlas import, projections, and two-pilot parity report implemented. |
| Verification | DONE | `make scp-0-verify`, `make test` | Parity report PASS; 10 adversarial SCP-0 tests pass; full repository unittest discovery passes 92 tests. Existing generated `generated/capability-catalog.json` was stale and was refreshed through `make m1-1-build` before the full run. |
| External review packet | DONE | `review-packets/scp-0-semantic-registry-foundation-2026-06-23.zip` | Inspection packet generated with internal `SHA256SUMS`; adjacent `.zip.sha256` file is the authoritative packet checksum. |
