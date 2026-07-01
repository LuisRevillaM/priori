# Known Gaps

## requires_full_repo: Runtime Reproduction

What is missing: full source tree, Python environment, canonical tracking data, raw IDSSE files, and ignored runtime artifacts.

Why it matters: without these, the reviewer cannot rerun the deterministic executor or milestone verification gates.

Default boundary: treat this packet as inspection evidence, not a reproducible runtime package.

Next action: use the full repo and local data to run the suggested verification commands in `validation-output.md`.

## not_in_scope: Raw Tracking And Replay Data

What is missing: raw XML tracking files, canonical Parquet files, and replay-window JSON artifacts.

Why it matters: coordinate-level recomputation and visual replay validation require those files.

Default boundary: this packet proves audit reasoning from source/contracts, not replay correctness.

Next action: request a separate evidence/replay packet if coordinate replay review is needed.

## unknown: Historical Generated Artifact Drift

What is missing: proof that every historical generated artifact in the full repo matches its generator at this exact source commit.

Why it matters: this packet includes current generated schema/context/knowledge-pack artifacts, but does not rerun all generation commands.

Default boundary: inspect included files as source evidence for the audit, not as a complete generated-artifact drift proof.

Next action: run the full repo generation/verification gates if drift proof is needed.

## not_in_scope: S2I And Workbench Alpha Completion

What is missing: Hermes installation, MCP adapter execution, final frontier-agent sealed acceptance, and React Workbench Alpha implementation evidence.

Why it matters: the audit explicitly concludes those tracks should not pause, but this packet does not prove those tracks are complete.

Default boundary: audit verdict is about primitive/IR/lowering architecture only.

Next action: review S2I and Workbench Alpha in separate packets.

## not_in_scope: Unrelated Dirty Worktree Files

What is missing: review of the unrelated `pyproject.toml` modification and pre-existing review-packet clutter.

Why it matters: they appear in `git status --short`, but were not part of this audit.

Default boundary: leave unrelated changes untouched.

Next action: inspect or clean those separately if needed.
