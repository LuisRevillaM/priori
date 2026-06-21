# M1.1S Gate S7R2 External Review

## Decision

`APPROVE_M1_2_UNBLOCKED`

The external reviewer approved S7R2 as sufficient to begin M1.2 and explicitly recommended against opening another M1.1S runtime-correction gate.

## Required M1.2 S0 Guard

The Hermes-facing capability boundary must expose only proven-safe operator/source combinations.

Until broader collection semantics are intentionally designed and tested:

- Hermes may use `exists` and `count_at_least` for declared `anchor_evaluations`;
- Hermes must hide or reject other collection-source combinations, including raw relation episode inputs and generic Boolean episode-set counting;
- unsupported combinations must surface as capability gaps.

## Opening Tests For M1.2

- Two distinct anchors at the same frame must not share witnesses or evidence accidentally. Prefer exact `anchor_id` correlation over frame-only fallback.
- Relation-limit enforcement can remain post-computation for the current corpus, but execution cost must be recorded and Hermes must be prevented from requesting broad unnecessary scopes.

## M1.2 Direction

Proceed with:

```text
S0  Freeze Hermes-visible tools and safe capability subset
S1  Manual reference workshop with typed plan, bind, execute, traces, coordinate replay, feedback
S2  Hermes drafting, clarification, and capability-gap behavior
S3  Explicit revisions, semantic diffs, result deltas, feedback labels, immutable recipe versions
```

M1.2 needs a plain coordinate replay for human tactical inspection. It does not need polished UI.
