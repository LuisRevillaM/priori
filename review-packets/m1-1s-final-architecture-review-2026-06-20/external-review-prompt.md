# External Review Prompt

You are reviewing an inspection-only packet for M1.1S of the Priori tactical query runtime. You do not have full repo access and cannot rerun the commands unless you separately obtain the repo, environment, and canonical data.

Please review whether M1.1S should be approved to unblock M1.2.

Focus on:

1. Whether S4 generic result emission is truly plan-driven.
2. Whether S5 evidence aliases, required/optional semantics, node rename behavior, and missing evidence failure are sufficient.
3. Whether S6 proves a genuinely second, non-block-shift tactical shape.
4. Whether S7 honestly separates generic runtime behavior from legacy M1 compatibility.
5. Whether M1 parity is preserved only through explicit legacy compatibility.
6. Whether any remaining coupling, overfitting, reward hacking, or unproven claim should block M1.2.

Please return one of:

- `APPROVE`
- `APPROVE_WITH_REQUIRED_CHANGES_BEFORE_M1_2`
- `REJECT`

If not approving, list blocking issues and required proof tests. Assume the local verifier outputs are internally generated evidence unless you can verify them from included source and artifacts.
