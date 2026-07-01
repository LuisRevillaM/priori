# Scope

## Included

Commit `a38cd1d9d95cdf7e0eb2c07e357a3f233ec197d6`:

- `src/tqe/workshop/app_service.py`
- `apps/workbench-alpha/**`
- Workbench-specific `Makefile` targets:
  - `workbench-alpha-install`
  - `workbench-alpha-build`
  - `workbench-alpha-serve`
  - `workbench-alpha-verify`
- Workbench-specific ignore rules in `.gitignore`

## Excluded

The worktree contains unrelated or parallel changes that are not part of this
packet or commit:

- `src/tqe/workshop/m1_2.py`
- `generated/tactical-knowledge-pack.*`
- `generated/capability-context.json`
- `artifacts/m1.2/gate-s2i-verification-report.json`
- delivery/current-state docs
- older review packets and primitive-layer audit artifacts
- unrelated `m1-2-gate-s2id-verify` Makefile changes left unstaged

Those files are listed in `commands/git-status-short.txt` only to make the
dirty-worktree boundary explicit.

## Boundary Claim

`app_service.py` is an HTTP/orchestration boundary. It serves static Workbench
assets, translates `/api` requests, reloads the approved recipe from host-owned
config before validation, calls existing workshop/runtime functions, and returns
DTOs.

It does not calculate tactical primitives, reconstruct predicate traces, parse
raw tracking data independently, or accept browser-minted authorization IDs.
