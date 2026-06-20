# Git / Worktree Status

## `git branch --show-current`

```text
main
```

## `git rev-parse HEAD`

```text
fatal: ambiguous argument 'HEAD': unknown revision or path not in the working tree.
HEAD
```

Interpretation: no valid `HEAD` commit is available in this worktree.

## `git status --short`

```text
?? .gitignore
?? KNOWN_ISSUES.md
?? MILESTONES.md
?? Makefile
?? PROJECT_CHARTER.md
?? apps/
?? config/
?? delivery/
?? docs/
?? pyproject.toml
?? scripts/
?? src/
?? tests/
```

Interpretation: the current project state is uncommitted/untracked. This packet is local inspection material, not a commit-based review.
