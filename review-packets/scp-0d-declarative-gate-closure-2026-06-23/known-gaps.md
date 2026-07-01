# Known Gaps

## Packet Is Inspection-Only

classification: `requires_full_repo`

What is missing:

- The packet does not include the full repository, virtual environment, data, or test harness dependencies needed to rerun validation standalone.

Why it matters:

- Reviewers can inspect evidence, diffs, generated artifacts, and logs, but cannot independently reproduce all commands from only the zip.

Default boundary:

- Treat this as an inspection packet, not a self-contained reproducible package.

Next action:

- Use the full repository at commit `6ae85300e80909dc8060c078e58441eccdf1c0bc` to rerun commands.

## SCP-1 Not Started

classification: `not_in_scope`

What is missing:

- No SCP-1 executable algebra work is claimed.

Why it matters:

- SCP-0D only determines whether SCP-1 may be unblocked.

Default boundary:

- Do not interpret this packet as SCP-1 implementation evidence.

Next action:

- If SCP-0D is externally accepted, proceed to SCP-1 with the registry/projection gates as source-of-truth constraints.

## Unrelated Workspace Dirtiness

classification: `unknown`

What is missing:

- The worktree contains unrelated modified and untracked files, listed in `commands/git-status-short.txt`.

Why it matters:

- They are not part of the SCP-0D commit or packet claims.

Default boundary:

- Ignore them for SCP-0D review unless they later intersect the SCP-1 workstream.

Next action:

- Clean or separately classify those files in their own maintenance pass.

## AI Projection Accepted Differences

classification: `requires_human_decision`

What is missing:

- SCP-0D explicitly accepts four AI recipe contract differences because the model-visible baseline is an authoring surface and the semantic projection includes full typed-plan dependencies.

Why it matters:

- This is no longer silent drift, but it is still a policy decision reviewers should inspect.

Default boundary:

- The accepted differences are valid only because they are explicitly listed in policy and reported in parity.

Next action:

- Reviewer should inspect `repo-files/semantic-registry/registry.yaml` and `repo-files/artifacts/scp-0/verification-report.json`.
