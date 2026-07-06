# PRUNE-1 Legacy Retirement Report

Branch: `packet/prune-1`

Frontier base: `71ce656` (`codex/afl08-passport-loop`)

Packet: `delivery/packets/PRUNE-1-legacy-retirement.md`

Status vocabulary: this report uses `DELIVERED with evidence` only after
evidence exists. Review acceptance remains the director/reviewer's judgment.

## Inventory Commit

Status: `INVENTORY_ONLY`

No files were removed, moved, or rewritten before this inventory was committed.

Inventory evidence commands:

- `git status --short --branch`
- `git ls-files`
- `git grep -n "CURRENT_STATE.md|KNOWN_ISSUES.md|MILESTONES.md" -- .`
- `git grep -n "docs/TACTICAL_QUERY_ARCHITECTURE_AND_STANDARD_LIBRARY.md" -- .`
- `git grep -n "BETA_1A|BETA_1B" -- .`
- `git grep -n "WORKBENCH_PRODUCT_AUDIT_V1|WORKBENCH_OPUS_UI_SYSTEM_REVIEW|PRIMITIVE_LAYER_AUDIT_V1" -- .`
- `git grep -n "scripts/coverage_map" -- .`
- `git grep -n "scripts/packets" -- .`
- `git grep -n "r1_5_population_audit|population_audit" -- .`
- `git grep -n "render-start.sh|bootstrap-hermes.sh" -- .`

### Classified Inventory

| Path or scope | Class | Evidence | Planned action |
| --- | --- | --- | --- |
| `PROJECT_CHARTER.md` | KEEP | Packet fence protects the design charter/company boundary. `delivery/status.yaml` still names it as charter. | Untouched. |
| `README.md` | KEEP | Current entry point and source-of-truth map. It currently points at the legacy architecture brief. | Update references after quarantine so current sources point to semantic registry, ADRs, and current packet/design records. |
| `CURRENT_STATE.md` | QUARANTINE | Packet names it stale. Live refs are the document hierarchy itself and `delivery/status.yaml`; other refs are historical ledger/review evidence. | Move to `docs/archive/prune-1/top-level-state/CURRENT_STATE.md` with provenance header. |
| `KNOWN_ISSUES.md` | QUARANTINE | Packet names it stale. Live refs are `.github/workflows/ci.yml` and `docs/CI.md`; other refs are historical packet/review evidence. | Move to `docs/archive/prune-1/top-level-state/KNOWN_ISSUES.md` with provenance header; update live CI comments to describe the specific drift directly. |
| `MILESTONES.md` | QUARANTINE | Packet names it stale. `delivery/status.yaml`, old specs, ADRs, learnings, and review packets cite it as historical M1-M6 planning evidence. | Move to `docs/archive/prune-1/top-level-state/MILESTONES.md` with provenance header; update current status pointers to the AFL contract and ledger. |
| `docs/TACTICAL_QUERY_ARCHITECTURE_AND_STANDARD_LIBRARY.md` | QUARANTINE | Packet targets legacy operator-composition docs. The file presents `gt/gte/lte/persists_for` as current operator grammar and is referenced by README and M2A packet status/spec. | Move full legacy text to `docs/archive/prune-1/architecture/TACTICAL_QUERY_ARCHITECTURE_AND_STANDARD_LIBRARY.md` with provenance header; leave a short compatibility pointer at the original path that no longer presents operator grammar as current. |
| `config/query-plans/**` operator keys | KEEP | Packet says the legacy `operators` key is live machinery. Query plans contain `gt/gte/lte/persists_for` and are consumed by runtime/binder paths. | Untouched. |
| `generated/**` including `generated/audits/**` | FLAG | Packet fence says generated artifacts are regenerable and director handles at merge. Several generated files are hash/provenance records. | Untouched; director decision required for generated audit remnants. |
| `delivery/ledger.jsonl` | KEEP | Packet fence: ledger untouched. Many historical references to retired docs live here. | Untouched. |
| `delivery/packets/**` sealed evidence/reviews | KEEP | Packet fence protects sealed packet evidence/review files. Current packet reports also cite generators and evidence paths. | Untouched except this PRUNE-1 report append. |
| `review-packets/**` | KEEP | Tracked review bundles and hashes; packet fence protects sealed evidence/reviews. | Untouched. |
| `docs/design/**` | KEEP | Packet fence protects design charter. Film Room design files remain ratified. | Untouched. |
| `docs/adr/**` | KEEP | Packet fence protects ADRs except header notes. ADRs cite historical roadmap docs. | Untouched. |
| `semantic-registry/atlas/**` and `semantic-registry/atlas/PROVENANCE.md` | KEEP | Packet fence protects atlas and provenance. | Untouched. |
| `docs/BETA_1A_PRODUCT_FLOW_PRUNING_REPORT.md` | QUARANTINE | No current runtime/doc refs outside sealed review packets; packet targets M1-era workbench docs. | Move to `docs/archive/prune-1/workbench/` with provenance header. |
| `docs/BETA_1A_1_UX_STATE_HARDENING_REPORT.md` | QUARANTINE | No current runtime/doc refs outside sealed review packets; packet targets M1-era workbench docs. | Move to `docs/archive/prune-1/workbench/` with provenance header. |
| `docs/BETA_1B_COMPREHENSION_POLISH_REPORT.md` | QUARANTINE | No current runtime/doc refs outside sealed review packets; packet targets M1-era workbench docs. | Move to `docs/archive/prune-1/workbench/` with provenance header. |
| `docs/audits/WORKBENCH_PRODUCT_AUDIT_V1.md` | KEEP | `delivery/packets/RENAME-1-REPORT.md` explicitly says "Keep as historical audit"; review packets cite it. | Untouched. |
| `docs/audits/WORKBENCH_OPUS_UI_SYSTEM_REVIEW.md` | KEEP | Companion to `WORKBENCH_PRODUCT_AUDIT_V1.md`; review packets cite the pair as historical untracked-at-the-time audits. | Untouched. |
| `docs/audits/PRIMITIVE_LAYER_AUDIT_V1.md` | KEEP | Review packet `primitive-layer-audit-v1-2026-06-22` identifies it as the main human-readable audit; it also documents historical source-of-truth snapshots. | Untouched. |
| `docs/audits/FOUNDATION_AUDIT_2026-07-01.md` | KEEP | Current issue/history references in `CURRENT_STATE.md`, `KNOWN_ISSUES.md`, and packet work cite it as an audit record. | Untouched. |
| `docs/audits/ATLAS_STRATEGIC_REVIEW_2026-07-01.md` | KEEP | Current atlas/coverage context and review record. | Untouched. |
| `docs/CASE_STUDY.md` | KEEP | README and DOC/F1 packets identify it as current public narrative; F1-B explicitly forbids editing it in that packet context. | Untouched. |
| `docs/CAR_NORTH_STAR.md` | KEEP | Current R2 aggregation law and scouting-bank references cite it. | Untouched. |
| `docs/SCOUTING_QUESTION_BANK.md` | KEEP | ADR 0014 cites it as the aggregation-era question bank. | Untouched. |
| `docs/OWN_FOOTAGE_TRACK.md` | KEEP | Rights-cleared footage planning doc; no retirement instruction. | Untouched. |
| `docs/CI.md` | KEEP | Current CI documentation. It contains a live stale pointer to `KNOWN_ISSUES.md`. | Update the pointer after quarantine. |
| `.github/workflows/ci.yml` | KEEP | Current CI workflow. It contains a live stale pointer to `KNOWN_ISSUES.md`. | Update the comment after quarantine. |
| `delivery/status.yaml` | KEEP | Current delivery status file; it points to stale top-level roadmap/state docs. | Update only `source_of_truth` pointers to current sources/archive, leaving historical milestone states intact. |
| `scripts/audits/r1_5_population_audit.py` | KEEP | Imported by `tests/test_r1_c_checkpoint.py`; cited by R1-C packet and R2-2 provenance. | Untouched. |
| `scripts/baseline/build_m1_baseline.py` | KEEP | Makefile target `m1-baseline-freeze`; historical baseline generator. | Untouched. |
| `scripts/m1_1/build_gate_a_artifacts.py` | KEEP | Makefile target `m1-1-build`; review packets preserve it. | Untouched. |
| `scripts/data/source_lock_idsse.py` | KEEP | Makefile provisioning targets and ledger evidence cite it. | Untouched. |
| `scripts/data/build_data_manifest.py` | KEEP | R1-C packet and data-manifest boundary tests cite it. | Untouched. |
| `scripts/create-demo-data-bundle.py`, `scripts/provision-demo-data.py`, `scripts/render-start.sh`, `scripts/bootstrap-hermes.sh`, `scripts/cloud-smoke.py` | KEEP | Makefile/Dockerfile/deploy docs reference these as live deployment machinery. | Untouched. |
| `scripts/coverage_map/**` | KEEP | Makefile targets, autonomous progress, coverage-map reports, and R1/SCP packets cite these as active compiler/search machinery. | Untouched. |
| `scripts/packets/**` | KEEP | Packet reports and provenance files cite these as committed evidence generators. | Untouched. |
| `scripts/workbench_alpha/generate_contracts.py` | KEEP | `apps/workbench-alpha/package.json` uses it; generated TS API types cite it. | Untouched. |
| `scripts/workbench_alpha/generate_*_replay.py` and `generate_*_moment.py` | KEEP | Case-study/public replay JSON records and DOC-1 packet cite these as replay generators; helper imports chain through `generate_moment_zero.py`. | Untouched. |
| Untracked `delivery/packets/PERF-1-cold-ask-latency.md` | FLAG | Present before PRUNE-1 edits. Not part of PRUNE-1. | Leave untracked; director decides whether to add or discard. |
| Untracked `delivery/packets/r2-4-flagship/run-sidecar.local.json` | FLAG | Present before PRUNE-1 edits. Local sidecar artifact. | Leave untracked; recommend gitignore or local cleanup by owner if obsolete. |
| Untracked `docs/visual-explainers/tactical-compilation-concept.png` | FLAG | Present before PRUNE-1 edits. Not part of this packet. | Leave untracked; director decides if it belongs with visual explainers. |

### Inventory Rulings

- No `RETIRE` rows are executed before the inventory commit.
- Files classified `QUARANTINE` are historically valuable but must stop acting
  as current guidance.
- Files classified `KEEP` are live machinery, protected history, or current
  source-of-truth references.
- Files classified `FLAG` require director/merge-time decision or are local
  untracked artifacts outside this packet.

## Execution

Status: `DELIVERED with evidence`

Execution evidence:

- Inventory-first commit exists: `7a07dde`.
- Quarantine paths were created under `docs/archive/prune-1/`.
- Quarantined files carry PRUNE-1 provenance headers naming their original
  path, inventory commit, reason, and current source to use instead.
- Current pointers were updated in `README.md`, `delivery/status.yaml`,
  `docs/CI.md`, and `.github/workflows/ci.yml`.
- Protected/fenced areas were left untouched: `delivery/ledger.jsonl`,
  `review-packets/**`, `docs/design/**`, `docs/adr/**`,
  `semantic-registry/atlas/**`, and `generated/**`.

Quarantined files:

| Original path | New path |
| --- | --- |
| `CURRENT_STATE.md` | `docs/archive/prune-1/top-level-state/CURRENT_STATE.md` |
| `KNOWN_ISSUES.md` | `docs/archive/prune-1/top-level-state/KNOWN_ISSUES.md` |
| `MILESTONES.md` | `docs/archive/prune-1/top-level-state/MILESTONES.md` |
| `docs/TACTICAL_QUERY_ARCHITECTURE_AND_STANDARD_LIBRARY.md` | `docs/archive/prune-1/architecture/TACTICAL_QUERY_ARCHITECTURE_AND_STANDARD_LIBRARY.md` |
| `docs/BETA_1A_PRODUCT_FLOW_PRUNING_REPORT.md` | `docs/archive/prune-1/workbench/BETA_1A_PRODUCT_FLOW_PRUNING_REPORT.md` |
| `docs/BETA_1A_1_UX_STATE_HARDENING_REPORT.md` | `docs/archive/prune-1/workbench/BETA_1A_1_UX_STATE_HARDENING_REPORT.md` |
| `docs/BETA_1B_COMPREHENSION_POLISH_REPORT.md` | `docs/archive/prune-1/workbench/BETA_1B_COMPREHENSION_POLISH_REPORT.md` |

Compatibility pointer:

- `docs/TACTICAL_QUERY_ARCHITECTURE_AND_STANDARD_LIBRARY.md` now remains as a
  short pointer to current architecture sources and the archived original. It
  explicitly says the legacy `operators` key is still live machinery while the
  old prose is not current composition grammar.

## Verification

Pending execution commit and full-suite run on the committed tree.
