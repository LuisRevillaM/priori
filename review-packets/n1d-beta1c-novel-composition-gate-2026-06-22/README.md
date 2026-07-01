# Review Packet — N1D + Beta 1A/1A.1 → Beta 1C novel-composition gate

Date: 2026-06-22
Repo: priori · Branch: `codex/integrated-alpha`

## The one binary question

> Can Beta 1C proceed to expose `HERMES_NOVEL_COMPOSITION` in the Workbench,
> using **N1D** as the runtime-pinned proof and **Beta 1A / 1A.1** as the product shell?

This packet contains exactly the evidence needed to answer yes/no.

## Commits under review

| Slice | Commit | What it establishes |
|-------|--------|---------------------|
| N1D — runtime-pinned novel-composition refresh | `16fa57e` | The frozen N1 hero re-executed under current runtime; result evidence carries `entry_mode`; read-compare freeze gate. |
| Beta 1A — product-flow pruning | `59b6749` | Two-path shell, single Confirm-and-run, honest provenance, hidden internals, stale-state cleanup. |
| Beta 1A.1 — UX state hardening | `a9d056e` | Reducer-driven state machine, booting state, cold-run waiting, preview labeling, result measurements. |

Note: Beta 1A/1A.1 deliberately keep `HERMES_NOVEL_COMPOSITION` **non-runnable / "pending proof
refresh."** N1D is the proof that would let Beta 1C remove that block.

## Why this is the decision point

- The Workbench already supports the `HERMES_NOVEL_COMPOSITION` provenance enum but holds it back.
- N1D produces fresh, runtime-pinned artifacts whose result evidence honestly carries `entry_mode`,
  replacing the stale N1B live artifacts (which predate the runtime `entry_mode` contract).
- If N1D is accepted as sufficient runtime-pinned proof, Beta 1C can wire the novel path into the UI
  and drop the pending block. If not, the gate stays closed and N1D needs strengthening first.

## What the reviewer should check

1. **Proof integrity (N1D).** `delivery/n1d/N1D_REPORT.md` + `n1d-canonical-freeze-manifest.json` +
   `n1d-entry-mode-audit.json` + `n1d-hero-plan.json`, and the verifier `src/tqe/verification/n1d.py`.
   - Hero question unchanged; plan shape/capabilities/operators/prompts unchanged; the only addition
     is surfacing two catalog-declared, already-runtime-emitted evidence fields (`entry_mode`,
     `time_to_entry_seconds`) — required for proof consumption, not new vocabulary.
   - `entry_mode` audit (top 5): PRESENT_AT_OPEN ×3 (t2e=0.0), ENTERED_AFTER_OPEN ×2. Invariant
     `time_to_entry==0.0 ⇒ PRESENT_AT_OPEN` holds; no entry-before-open (structurally impossible;
     annotated in the audit).
   - The verifier is a **read-compare freeze gate**: it re-executes into a scratch dir and fails on
     drift; it never silently regenerates the pinned proof.
2. **Product shell (Beta 1A / 1A.1).** `docs/BETA_1A_*` reports; `apps/workbench-alpha/src/App.tsx`,
   `workbenchState.ts` (pure reducer FSM), `presentation.ts` (pure mappers, incl. honest `entry_mode`
   + provenance rendering); the test specs; and `screenshots/`.

## Verification results (as run at the packet commit)

- N1D gate `python -m tqe.verification.n1d`: **PASS 12/12**. Drift tamper test ⇒ **FAIL exit 1**;
  restore ⇒ **PASS exit 0**.
- `python -m tqe.verification.n1c`: **PASS 8/8** (N1C UNKNOWN + enum-domain contracts preserved).
- Backend `python -m unittest discover -s tests`: **40 tests OK**.
- Workbench `npm run test:acceptance`: **PASS** — contracts, fixtures, 4 unit suites (geometry,
  playback, presentation, workbenchState), **13 Playwright tests**. `tsc --noEmit` clean.

### Reproduce

```bash
# N1D proof gate (fails on drift; does not regenerate)
PYTHONPATH=src .venv/bin/python -m tqe.verification.n1d
# Preserved N1C contracts
PYTHONPATH=src .venv/bin/python -m tqe.verification.n1c
# Product shell
cd apps/workbench-alpha && npm run test:acceptance
```

## File index

- `delivery/n1d/N1D_REPORT.md` — N1D summary, artifact IDs/hashes, entry_mode audit, caveats.
- `delivery/n1d/n1d-canonical-freeze-manifest.json` — pinned runtime/data/artifact/result identity.
- `delivery/n1d/n1d-entry-mode-audit.json` — per-result entry_mode + time_to_entry audit.
- `delivery/n1d/n1d-hero-plan.json` — the frozen hero plan (candidate + 2 evidence fields).
- `src/tqe/verification/n1d.py` — freeze (`--freeze`) + read-compare gate.
- `docs/BETA_1A_PRODUCT_FLOW_PRUNING_REPORT.md`, `docs/BETA_1A_1_UX_STATE_HARDENING_REPORT.md`.
- `apps/workbench-alpha/src/{App.tsx,workbenchState.ts,presentation.ts}` — product shell.
- `apps/workbench-alpha/tests/{workbench-alpha.spec.ts,workbenchState.test.ts,presentation.test.ts,beta1a-proof.spec.ts}`.
- `tests/test_workbench_beta0_contract.py` — backend provenance contract.
- `screenshots/` — booting, initial split, recipe preview (not-interpreted), cold-run, confirmed
  result, model-unavailable.

`SHA256SUMS` lists a checksum for every file in this packet.

## Out of scope for this review

Beta 1C UI exposure is **not** implemented here. A "yes" authorizes building it (remove the pending
block, wire the N1D-pinned novel path into the UI, add end-to-end tests). Beta 1B comprehension polish
can proceed in parallel regardless of this decision.
