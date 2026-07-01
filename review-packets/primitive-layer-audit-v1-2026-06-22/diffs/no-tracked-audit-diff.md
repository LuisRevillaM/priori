# Diff Notes

The primitive-layer audit deliverables are new untracked artifacts in this workspace, not a tracked code patch.

Included artifacts:

- `artifacts/audits/PRIMITIVE_LAYER_AUDIT_V1.md`
- `artifacts/audits/primitive-inventory.json`
- `artifacts/audits/primitive-dependency-graph.json`
- `artifacts/audits/tactical-query-coverage-matrix.json`
- `artifacts/audits/next-primitive-recommendations.json`

The packet also includes `commands/git-diff-stat.txt`. At assembly time, tracked diffs existed in `pyproject.toml`, `src/tqe/workshop/knowledge_pack.py`, and `src/tqe/workshop/m1_2.py`. Those were pre-existing non-audit worktree changes. The packet includes `knowledge_pack.py` and `m1_2.py` as source excerpts because they are relevant to the audit context; no tracked code patch is presented as part of this audit packet.
