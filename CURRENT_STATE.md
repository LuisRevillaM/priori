# Current State Snapshot

Date: 2026-07-01

## Repository State

- Canonical branch: `codex/afl08-passport-loop` (this is the deployed and
  active line; see "Branch topology" below).
- Deployed alpha: single Render Docker service.
  - Coach preview: `https://priori-integrated-alpha.onrender.com/`
  - Case study: `https://priori-integrated-alpha.onrender.com/case-study`
  - Research workbench: `https://priori-integrated-alpha.onrender.com/workbench`

## Document Hierarchy (which document answers what)

| Question | Source of truth |
| --- | --- |
| What is this project, what is real today | `README.md` |
| The public narrative and product lesson | `docs/CASE_STUDY.md` (live at `/case-study`) |
| How the system is layered | `docs/TACTICAL_QUERY_ARCHITECTURE_AND_STANDARD_LIBRARY.md` |
| What each capability may claim | semantic registry (`semantic-registry/`, `src/tqe/semantic_registry/`) — generated passports are projections, never hand-authored |
| Ongoing roadmap and promotion rules | `delivery/autonomous/afl_milestone_contract.yaml` (protected) + `delivery/autonomous/priori_autonomous_delivery_charter.md` |
| Historical product milestones (M1–M6) | `MILESTONES.md` + `delivery/*/status.yaml` + `delivery/ledger.jsonl` (historical record; do not extend) |
| North-star metric direction | `docs/CAR_NORTH_STAR.md` |
| What lives in git as evidence | `docs/EVIDENCE_RETENTION_POLICY.md` |
| Known issues | `KNOWN_ISSUES.md` |

The two milestone namespaces are distinct on purpose: `M1/M1.1/M1.2/...` is the
completed early product roadmap; `AFL-*` is the current protected autonomous
roadmap. Do not mint new milestone IDs outside the AFL contract (the afl-g0
gate enforces this).

## Verified State (re-verified locally 2026-07-01 on this branch)

- `make test`: 188 tests pass; N1D.1 attestation check prints
  `VERIFIED, blocking_reasons: []`.
- `make n1d1-verify`: `VERIFIED`.
- `make n1i-verify`: `10/10 pass`.
- `make n1d-verify`: `13 pass / 2 fail` — the two failures are **expected
  source-hash drift**: the N1D freeze manifest pins executor/binder/catalog
  hashes from N1D acceptance time (2026-06-23), and the AFL standard-library
  expansion has legitimately moved those files since. The historical N1D/N1D.1
  acceptance (live Render rerun, job `n1f_7a1f1b8013294534`, deploy
  `7b7bf842`, 14 results) remains valid as recorded in
  `delivery/n1d/N1I_REPORT.md`. Re-pinning requires a fresh live rerun, not a
  hash update.
- Primitive/capability gates: see `make`-targets in `Makefile`
  (`afl-*-verify`, `scl0-verify`, `scl1-verify`, `scl-nl0-verify`).

Warning for operators: several verifiers (e.g. `n1d`, `n1i`) regenerate their
report files and knowledge packs **in place** when run locally. Running a gate
without a live evidence source can overwrite a pinned historical report with a
weaker local one — this exact mechanism produced a misleading "not run" edit of
`N1I_REPORT.md` on a superseded branch. Until the gates are fixed to write
fresh runs to `artifacts/` only, check `git status` after running gates and do
not commit regenerated evidence files without a decision.

## Standing Blockers (external authority required)

1. **S2I-F** — final independent sealed evaluation of the frontier
   Hermes/GPT-5.5 path (harness ready; fails closed without an
   externally-authored sealed set).
2. **SCP-0E.1** — semantic registry external review.
3. **AFL protected promotion** — no protected CI identity, hidden-suite hash,
   or signing key exists yet; `afl-g0-gate` correctly emits BLOCKED rather
   than PROMOTED (builder may not judge).

## Branch Topology (2026-07-01 reconciliation)

- `codex/afl08-passport-loop` — canonical frontier, deployed.
- `origin/main` — behind; contains a rebased duplicate of the SCP/AFL-G0
  commits plus README/branding. Should be fast-forwarded or reset to the
  frontier line at the next release point.
- `codex/coverage-map-v0`, `codex/integrated-alpha`, `codex/m1-1-s1-ir-binder`
  — superseded. The only unique content of `coverage-map-v0` (workbench audit
  docs, visual explainer) was carried onto the frontier; its draft runtime
  kernels were superseded by the reviewed AFL versions.
- The former primary clone (`~/Documents/priori`) was deleted; its worktree
  was verified byte-identical to the pushed frontier tip before cleanup.

## Where Work Continues

Ongoing work is governed by the AFL milestone contract
(`delivery/autonomous/afl_milestone_contract.yaml`) — currently the AFL-08
standard-library / atlas-closure and AFL-09 validation-factory territory —
steered by the atlas coverage map (`delivery/autonomous/COVERAGE_MAP_V0.md`)
and, going forward, CAR-unlock scoring (`docs/CAR_NORTH_STAR.md`). A
foundation audit of the runtime core and primitive kernels is in progress as
of this snapshot; its findings will land in `docs/audits/`.
