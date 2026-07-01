# Next Steps

## For External Reviewer

1. Read `artifacts/audits/PRIMITIVE_LAYER_AUDIT_V1.md`.
2. Cross-check capability counts and layer assignments in `artifacts/audits/primitive-inventory.json`.
3. Inspect opaque/layering flags in `artifacts/audits/primitive-dependency-graph.json`.
4. Review tactical coverage classifications in `artifacts/audits/tactical-query-coverage-matrix.json`.
5. Evaluate the five recommended capabilities in `artifacts/audits/next-primitive-recommendations.json`.
6. Use `source-excerpts/` and `config/query-plans/` to verify whether the audit claims are supported by actual code and plan evidence.

## For Repo Maintainers

1. Keep S2I and Workbench Alpha moving.
2. Before a second approved tactical family, decide whether to:
   - declare hidden runtime parameter dependencies on catalog entries, or
   - explicitly document them as recipe-level lowering dependencies.
3. Keep `outcome_classification` trusted-recipe-only.
4. Treat `signed_lateral_shift` as a high-level detector stage or split its lowerings only when real second-family duplication justifies it.
5. Add next capabilities incrementally with typed outputs, PASS/FAIL/UNKNOWN behavior, evidence fields, and visual inspection support.
