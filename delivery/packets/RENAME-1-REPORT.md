# RENAME-1 Report: Entrelíneas Rename

Branch: `packet/rename-1`

Frontier base: `f90fce4` (`codex/afl08-passport-loop`)

## Protocol Status

| Item | Status | Evidence |
| --- | --- | --- |
| Packet read | DONE | `delivery/packets/RENAME-1-entrelineas.md` |
| Branch | DONE | `packet/rename-1` from `f90fce4` |
| Stage-0 inventory commit | IN_PROGRESS | This report section is committed before any rename edit lands. |
| Laws | ACTIVE | Historical records remain byte-exact; atlas/README attribution retained. |
| Push | NOT_DONE | Local commits only. |

## Classified Inventory

This section was authored before any rename edits. Existing untracked files were
left untouched: `delivery/packets/r2-4-flagship/run-sidecar.local.json` and
`docs/visual-explainers/tactical-compilation-concept.png`.

Inventory commands:

```text
git ls-files -co --exclude-standard -z | xargs -0 grep -Il -i 'priori' | sort
git ls-files -co --exclude-standard -z | xargs -0 grep -In -i 'priori'
find . -path ./.git -prune -o -path ./.venv -prune -o -path ./node_modules -prune -o -type f -iname '*priori*' -print | sort
```

Raw results: 442 repo files, 2,844 matching lines, and 8 pathnames. Narrowed
actual old-name results after separating `priority`/`prioritization` substring
false positives: 370 files and 1,683 matching lines.

### A. Living Surface To Rename

These are live project/product/source surfaces, excluding Hermes toolset names,
`tqe` package identity, current infra names, and historical/provenance records.

| Surface | Planned handling |
| --- | --- |
| `README.md` | Rename title/intro to Entrelíneas; add required history paragraph; keep current Render URL as current infra until owner renames it. |
| `PROJECT_CHARTER.md` | Rename project title only; keep Priori company access/no-integration language as historical truth. |
| `pyproject.toml` | Rename distribution from `priori-tactical-evidence` to `entrelineas-tactical-evidence`; `tqe` package remains. |
| `apps/replay-proof/package.json`, `apps/replay-proof/package-lock.json` | Rename machine package id to `entrelineas-replay-proof`. |
| `apps/workbench-alpha/package.json`, `apps/workbench-alpha/package-lock.json` | Rename machine package id to `entrelineas-workbench-alpha`. |
| `apps/workbench-alpha/index.html` | Rename browser title. |
| `apps/workbench-alpha/src/CaseStudy.tsx` | Rename product eyebrow. |
| `apps/workbench-alpha/src/CoachSurface.tsx` | Rename visible brand and aria label. |
| `docs/CASE_STUDY.md` | Rename living case-study label; keep current URL until infra rename. |
| `docs/CI.md` | Rename temporary worktree example; keep GitHub repo URL as out-of-scope. |
| `config/deploy/demo-data-manifest.json` | Rename bundle id/description. |
| `data/manifest.json`, `scripts/data/build_data_manifest.py`, `src/tqe/runtime/executor.py`, `tests/test_executor_boundaries.py` | Rename data-manifest schema version together. |
| `scripts/create-demo-data-bundle.py`, `scripts/provision-demo-data.py`, `scripts/render-start.sh` | Rename human descriptions, default bundle/temp names, and temp prewarm filename. |
| `src/tqe/idsse/source_lock.py` | Rename HTTP user agent. |
| `src/tqe/runtime/artifacts.py` | Rename tactical-query schema `$id`. |
| `src/tqe/semantic_registry/generate.py`, `src/tqe/semantic_registry/runtime_manifest.py` | Rename generator ids; generated outputs are not edited by hand. |
| `src/tqe/workshop/app_service.py`, `src/tqe/workshop/hermes_invocation.py`, `src/tqe/workshop/mcp_server.py` | Rename human-facing prompt/instruction text only; preserve frozen Hermes identifiers. |

### B. Historical Record To Keep

Law 1 keeps these byte-exact except this new report. Counts below are narrowed
actual old-name file counts:

| Historical group | Count | Handling |
| --- | ---: | --- |
| `delivery/packets/*` prior reports/reviews/briefs, including the RENAME-1 brief | 20 | Keep. |
| `delivery/ledger.jsonl` | 1 | Keep. |
| `review-packets/**` | 219 | Keep. |
| `docs/adr/*.md` body text | 4 | Keep; no header note needed for this packet. |
| `docs/learnings/2026-*` | 6 | Keep dated learning records. |
| `docs/reviews/2026-*` | 5 | Keep dated review records. |
| `delivery/n1d/**`, `delivery/m1.1/**`, `delivery/m1.2/**`, `delivery/scp-*`, `delivery/status.yaml` | 16 | Keep prior delivery/evidence records. |
| `delivery/autonomous/**` imported charter, protected contract, status/progress | 13 | Keep as prior imported references and protected promotion records. |
| `docs/audits/WORKBENCH_PRODUCT_AUDIT_V1.md` | 1 | Keep as historical audit. |

### C. Attribution To Keep

| Surface | Handling |
| --- | --- |
| `semantic-registry/atlas/raw/five_year_capability_manifest.yaml` | Keep Priori company origin; add `semantic-registry/atlas/PROVENANCE.md`. |
| `scripts/coverage_map/aggregate.py` denominator note | Keep attribution to Priori company's authored 741-concept atlas; reword only for clarity if touched. |
| `docs/audits/ATLAS_STRATEGIC_REVIEW_2026-07-01.md` | Keep attribution statement as historical audit. |
| `README.md` | Add required history paragraph: inspired by an exchange with Priori (the company), built independently on public data, renamed Entrelíneas. |
| `PROJECT_CHARTER.md`, `MILESTONES.md`, `KNOWN_ISSUES.md` | Keep Priori company no-access/no-integration/no-private-data boundaries where the company is the subject. |

### D. Pinned, Hash-Anchored, Generated, Or Explicitly Exempt

These are flagged for the director and not hand-edited in this packet.

| Surface | Reason |
| --- | --- |
| `generated/**` | Regenerable outputs; packet forbids hand-editing generated files. |
| `apps/workbench-alpha/src/generated/**` | Regenerable frontend API/data outputs if old-name strings appear later. |
| `artifacts/**` | Committed evidence and proof outputs. |
| `artifacts/cloud-alpha/priori-cloud-workbench-alpha-fortuna-v1.{tar.gz,manifest.json}` | Ignored cloud bundle artifacts with old name in path; flag only. |
| `semantic-registry/registry.yaml` | Generated/registry contract surface with old registry id; flag for sanctioned SCP regeneration. |
| `delivery/autonomous/afl_milestone_contract.yaml`, `delivery/autonomous/priori_autonomous_*`, `src/tqe/verification/afl_gate.py` | Protected AFL program id/imported reference surfaces; do not rename/refreeze without director ratification. |
| `src/tqe/verification/afl_substrate_q4.py` claim-boundary text | Coupled to frozen expectation evidence; flag rather than refreeze in this packet. |
| `priori_tactical`, `mcp-priori_tactical`, `mcp_priori_tactical_*` across Docker/Render/scripts/src/tests/docs | Hermes toolset identifiers; explicitly stay. |
| `priori-integrated-alpha` Render service/disk/URLs in `README.md`, `CURRENT_STATE.md`, `.codex/render-target.json`, `render.yaml` | Current infra names/URLs; flag for owner/director infra rename rather than local text substitution. |
| `https://github.com/LuisRevillaM/priori`, local folder/clone paths | GitHub repo and local folder rename are out of scope. |

Regeneration commands to run after merge-time ratification, not in this packet:

```text
TQE_WRITE=1 make scp-0-verify
TQE_WRITE=1 make knowledge-pack-write
TQE_WRITE=1 make coverage-map
TQE_WRITE=1 make compiler-search-reachability
npm --prefix apps/workbench-alpha run build
make cloud-alpha-bundle
```

False-positive raw grep bucket: files containing only ordinary words such as
`priority`, `prioritization`, or `prioritized` are not old-name hits and are not
renamed.

## Implementation Log

| Commit | Contents |
| --- | --- |
| inventory commit | Classified inventory only; no rename edits. |

## Verification

Pending implementation.
