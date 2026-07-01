# Known Gaps

## `requires_full_repo`: packet is not standalone

Validation requires the full repository, installed dependencies, local Python
environment, Node packages, and the local data/artifact setup.

Default boundary: treat this as an inspection packet, not a reproducible
standalone package.

Next action: rerun `make workbench-alpha-verify` in the repo if direct
reproduction is required.

## `not_in_scope`: visual polish

Final visual styling, choreography, and demo polish are intentionally excluded.

Default boundary: review information architecture and correctness, not final
presentation quality.

Next action: defer visual polish until the later M3/M5 slice.

## `not_in_scope`: model/Hermes/S3 feedback behavior

Workbench Alpha keeps manual mode functional and exposes model-unavailable
state. It does not implement model-backed interpretation, S3 feedback/revision
flows, or browser-to-MCP calls.

Default boundary: manual host-owned query-to-replay shell only.

Next action: wait for the S3/Hermes frontier path before adding feedback and
revision interaction.

## `unknown`: unrelated dirty worktree state

The repo has unrelated tracked and untracked changes outside this commit,
including S2I, knowledge-pack, audit, delivery, and older review-packet files.

Default boundary: reviewers should inspect only commit
`a38cd1d9d95cdf7e0eb2c07e357a3f233ec197d6` and this packet.

Next action: parallel owners should isolate or commit those other changes
separately.

## `not_in_scope`: npm advisory remediation

The packet records one low-severity transitive `esbuild` advisory. No broad
dependency upgrade was performed.

Default boundary: accepted as recorded for this slice unless it affects the
runtime path.

Next action: resolve with a narrow nonbreaking upgrade only if needed.
