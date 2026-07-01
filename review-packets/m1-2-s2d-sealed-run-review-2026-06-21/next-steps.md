# Next Steps

Recommended reviewer focus:

1. Decide whether the `second runner arrived properly` failure requires a model
   semantic-validation correction or a different ambiguity expectation.
2. Decide whether `change the primitive definitions` should count as the
   expected `mutation` gap in the scorer, or whether the compiler must emit the
   exact mutation term.
3. Decide whether a corrected S2E needs a fresh sealed set, or whether the
   current sealed set can be retired as diagnostic evidence.

Suggested conservative path:

```text
REJECT_KEEP_S3_BLOCKED
Open S2E focused correction:
  - second-runner support clarification robustness
  - mutation synonym scoring or exact gap requirement
  - rerun visible/held-out corpus
  - request a fresh sealed mini-set only after correction
```
