# Evidence Retention Policy

Status: adopted 2026-07-01. This codifies the de facto practice the repo grew
into, resolving the inconsistencies between `.gitignore` rules and tracked
files. It governs what evidence lives in git, in which form, and what stays
local.

## Principles

1. Evidence that backs an accepted or reviewed claim is part of the audit
   trail and belongs in git (per README: these directories are "noisy on
   purpose").
2. Every piece of evidence is stored in exactly one canonical form — no
   duplicate representations of the same bytes.
3. Regenerable outputs are tracked only when a contract, gate, review, or
   committed document references them.

## Rules by directory

### `review-packets/`

Review packets are point-in-time evidence bundles prepared for (external)
review.

- **Tracked:** the extracted packet tree (`review-packets/<packet-name>/`)
  and the integrity attestation (`review-packets/<packet-name>.zip.sha256`).
- **Not tracked:** the `.zip` itself (ignored via `.gitignore`). The tree is
  the diffable content of record; the `.sha256` pins the exact bytes of the
  zip that was delivered for review. Keep delivered zips in local/external
  archive storage if byte-exact reproduction is required.
- Historical exception: four pre-policy zips remain tracked from the earliest
  packet families. They stay (removing them would rewrite history), but no new
  zips are added.

### `artifacts/`

`artifacts/` is gitignored by default: gate runs regenerate their reports
locally. A curated subset is deliberately force-added (`git add -f`) when a
report or manifest is pinned by hash in an accepted gate, attestation, or
delivery document (e.g. `artifacts/n1c/`, `artifacts/n1d/`,
`artifacts/autonomous/`). The rule: **if a committed document pins the file's
hash or path as evidence, the file is committed; otherwise it stays local.**

### `generated/`

Generated contracts, packs, and audit outputs are tracked when they are inputs
to committed documents, contracts, or the deployed product (knowledge packs,
schemas, coverage maps, audit JSONs referenced by `docs/audits/`). Purely
exploratory generator output stays local.

### `data/`

Raw/canonical/feature match data is never tracked (size, license hygiene).
Source locks and hashes under version control pin its identity.

### Scratch

Root-level planning scratch (`/task_plan.md`, `/progress.md`, `/findings.md`)
and test-runner state (`test-results/`) are gitignored; they are
session-local, not project state.

## Change control

Weakening this policy (e.g. deleting tracked evidence, re-pinning hashes
without a fresh verified run) is a governance change, not a cleanup, and needs
explicit owner sign-off.
