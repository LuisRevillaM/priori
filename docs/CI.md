# CI

Established by F0-3 (foundation audit 2026-07-01, finding V2): the test suite
and the parity/drift gates run on every push and PR, so stale-green is
structurally impossible. Before this, the system's honesty depended on
somebody remembering to re-run the gates; now it depends on nothing.

Workflows:

- `.github/workflows/ci.yml` — runs on every push and PR.
- `.github/workflows/afl-protected-gate.yml` — the AFL PROTECTED_CI promotion
  boundary (manual dispatch). Scaffolding only until the protected identity is
  created; see the checklist below.

## What `ci.yml` covers

**Job 1 — Python suite + drift gates** (Python 3.12, `pip install -e .`):

1. `make test` — the full unittest suite, minus the data-dependent subset
   (see next section). This includes, in full: the SCP-0 stale-green guard
   tests (`test_scp0_semantic_registry`, 58 tests), the F0-2 write-mode
   policy tests (`test_verifier_write_mode`), binder/IR/catalog conformance
   (`test_m1_1_binder`), and all synthetic-geometry kernel tests
   (`test_m2a_bypass`, `test_defensive_line_model`, `test_lane_occupancy`,
   `test_controlled_line_break`, `test_relative_position_to_line`,
   `test_support_arrival`, `test_local_number_relation`,
   `test_one_touch_pass_chain`, ...).
2. A loud report of the skipped data-dependent test count (GitHub notice +
   job summary). A skip is an honest declaration, never a silent pass.
3. Drift gates, all verified to pass data-free in read-only check mode:
   `scp-0-verify`, `afl-passport-verify`, `afl-g0-verify`, `scp-1-verify`,
   `afl-g0-gate` (result BLOCKED without the protected identity — the honest
   fail-closed state; the runner still exits 0).
4. **The F0-2 invariant, enforced forever:** after all gates, the job fails
   if `git status --porcelain` is non-empty. Verifiers are read-only checks;
   a gate that mutates tracked evidence as a side effect of running is a bug.

**Job 2 — Workbench alpha unit tests:** `npm ci && npm run test:unit` in
`apps/workbench-alpha` (pure tsx unit tests; no corpus, no build, no
Playwright).

## What CI skips (data-dependent tests)

The 2.6 GB canonical corpus (`data/canonical/v1`, gitignored) is not
available in CI. Tests that execute against real match data declare the
dependency with `@requires_canonical_data` from
`tests/support/canonical_data.py` (a `unittest.skipUnless` on the presence of
`<TQE_DATA_ROOT>/matches.parquet`, default root `data/canonical/v1`).

Current split (2026-07-01): **284 tests total; 248 run in CI; 36 are
data-dependent and skip without the corpus**:

| Where | Skipped |
|---|---|
| `test_m1_1_runtime.M11RuntimeTests` (full class) | 12 |
| `test_m2a_controlled_pass.M2AControlledPassRuntimeTest` (full class) | 3 |
| `test_m2a_pass_bypass.M2APassBypassRuntimeTest` (full class) | 10 |
| `test_m2a_high_bypass_pass.M2AHighBypassPassRuntimeTest` (full class) | 9 |
| `test_workbench_beta0_contract` (2 methods: match library metadata, attested hero execution) | 2 |

These 36 are covered only by local full-suite runs with the corpus
provisioned (`make provision-corpus`, then `make test` — must end
`OK` with no skips).

Reproduce the CI (no-data) environment locally — `data/` is gitignored, so a
fresh worktree has no corpus, exactly like CI:

```bash
git worktree add /tmp/priori-nodata HEAD
cd /tmp/priori-nodata
PYTHONPATH=$PWD/src <repo>/.venv/bin/python -m unittest discover -s tests
# expect: Ran 284 tests ... OK (skipped=36)
git worktree remove /tmp/priori-nodata
```

(`TQE_DATA_ROOT=/nonexistent make test` also triggers the skips, but the
worktree is the faithful simulation.)

## Gates deliberately excluded from CI

- `afl-time-to-arrival-verify` — fails on frozen-expectation drift
  (`KNOWN_ISSUES.md`); wire it in after a deliberate re-freeze decision.
- `n1d-verify` — fails 2/15 checks by design since the AFL expansion moved
  past the N1D freeze pins; needs a fresh live rerun to re-pin.
- All corpus-dependent capability verifiers (`m2a-s1a/b/c-verify`,
  `afl-defensive-line-verify`, `afl-lane-occupancy-verify`,
  `afl-substrate-q*-verify`, ...) — require `data/canonical/v1`.
- `workbench-alpha-verify` (test:acceptance) — needs the built app plus a
  corpus-backed service (Playwright e2e); only `test:unit` runs in CI.

When a new test or gate is corpus-dependent, mark it with
`@requires_canonical_data` (tests) or leave it out of `ci.yml` with a comment
(gates) — never let it fail silently or pass vacuously.

## AFL protected identity — user-side setup checklist

`afl-protected-gate.yml` is committed with no keys and no secrets. Until the
identity below exists, every dispatch reports "identity not configured" and
skips the gate steps; `make afl-g0-gate` is itself fail-closed and reports
`BLOCKED` without all four env vars (see
`delivery/autonomous/PROTECTED_GATE_SETUP.md`). To finish the boundary:

1. **Create the environment.** GitHub → repo `LuisRevillaM/priori` →
   Settings → Environments → New environment → name it exactly
   `afl-protected-gate`. Add protection rules: required reviewers (someone
   who is not the candidate builder) and restrict deployment branches to
   `main`.
2. **Generate the signing key — outside the repo, never committed.** E.g.
   `openssl rand -hex 32` (or an ed25519 private key if/when the gate moves
   to asymmetric signatures). Store it only in the environment secret.
3. **Add the secret.** In the `afl-protected-gate` environment, add secret
   `AFL_GATE_SIGNING_KEY` with the generated key.
4. **Pin the hidden suite.** Assemble the hidden holdout/mutation suite and
   protected denominator definitions outside builder control; compute a
   stable hash over them (e.g. `shasum -a 256` over a sorted file list).
   Add environment **variables** `AFL_PROTECTED_SUITE_ID` (stable id, e.g.
   `afl-hidden-suite-v1`) and `AFL_PROTECTED_SUITE_HASH` (the pinned hash).
5. **Protect the workflow itself.** Enable branch protection on `main`
   (require PR review) so a candidate builder cannot edit
   `afl-protected-gate.yml`, the gate runner, or the promotion policy on the
   promotion branch.
6. **Verify fail-closed, then promote.** Dispatch the workflow once *before*
   step 3 and confirm it reports "identity not configured" and skips; after
   steps 1–5, dispatch again and confirm the gate produces a signed
   `PROTECTED_CI` result and archives the gate-result/certificate/canary
   artifacts. Only `result = PROMOTED` + `protection_level = PROTECTED_CI` +
   a present `promotion_signature` constitutes promotion
   (`PROTECTED_GATE_SETUP.md`); a local `BLOCKED` run never does.
