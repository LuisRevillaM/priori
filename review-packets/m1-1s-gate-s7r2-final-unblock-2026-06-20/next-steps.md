# Next Steps

## Review Decision

Return one of:

- `APPROVE_M1_2_UNBLOCKED`
- `REJECT_KEEP_M1_2_BLOCKED`

If rejected, include only concrete S7R2 blockers. Do not reopen broader architecture unless the committed patch violates a required S7R2 proof.

## Recommended M1.2 Shape After Approval

M1.2 should include both machine and human inspection:

```text
Natural-language request
→ Hermes drafts typed plan
→ user inspects interpretation
→ deterministic execution
→ ranked real moments
→ structural predicate trace
→ coordinate replay
→ human labels result
→ Hermes proposes explicit revision
→ result delta
→ immutable recipe version
```

Recommended slices:

- S0: tool and capability boundary.
- S1: manual reference workshop with typed plan edit, bind, execute, results, traces, replay, feedback.
- S2: Hermes query compiler using the same tools.
- S3: visual feedback and explicit revision with immutable recipe versions.

No polished UI is required for M1.2, but a plain coordinate replay panel is required for human tactical inspection.
