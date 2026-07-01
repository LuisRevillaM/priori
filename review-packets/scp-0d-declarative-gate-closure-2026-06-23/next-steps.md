# Next Steps

## Reviewer Decision Requested

Decide whether SCP-0D closes the previous required-change findings enough to unblock SCP-1.

Recommended review sequence:

1. Confirm the external review request in `external-review/source-review-request.md`.
2. Inspect the implementation diff in `diffs/scp0d-commit.patch`.
3. Inspect the report in `repo-files/artifacts/scp-0/verification-report.json`.
4. Verify policy and accepted differences in `repo-files/semantic-registry/registry.yaml`.
5. Inspect the focused tests in `repo-files/tests/test_scp0_semantic_registry.py`.
6. Confirm baselines and typed plans are present.

## If Approved

- Mark SCP-0D accepted.
- Update SCP-0 status from `BLOCKED_PENDING_EXTERNAL_SCP_0D_REVIEW` to SCP-1-ready.
- Begin SCP-1 design/implementation using the registry lock, projection policies, baseline pins, and signature constraints as hard gates.

## If Changes Are Required

- Keep SCP-1 blocked.
- Open a narrow SCP-0E only for concrete failing findings from this packet.
- Do not reopen broad architecture unless the reviewer finds a structural contradiction in the registry/projection model.
