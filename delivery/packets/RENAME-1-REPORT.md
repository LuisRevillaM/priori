# RENAME-1 Report: Entrelíneas Rename

Branch: `packet/rename-1`

Frontier base: `f90fce4` (`codex/afl08-passport-loop`)

## Protocol Status

| Item | Status | Evidence |
| --- | --- | --- |
| Packet read | DONE | `delivery/packets/RENAME-1-entrelineas.md` |
| Branch | DONE | `packet/rename-1` from `f90fce4` |
| Stage-0 inventory commit | DONE | `0fc5370`; committed before any rename edit landed. |
| Laws | SATISFIED | Historical records remain byte-exact; atlas/README attribution retained. |
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
| `src/tqe/runtime/artifacts.py` | Reclassified as generated-schema coupled; flag for sanctioned schema regeneration rather than edit in this packet. |
| `src/tqe/semantic_registry/generate.py`, `src/tqe/semantic_registry/runtime_manifest.py` | Reclassified as registry/knowledge-pack coupled; flag for sanctioned SCP regeneration rather than edit in this packet. |
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
make scp-0-write
make knowledge-pack-write
make coverage-map-write
make compiler-search-reachability
make m1-1-build
npm --prefix apps/workbench-alpha run build
make cloud-alpha-bundle
```

False-positive raw grep bucket: files containing only ordinary words such as
`priority`, `prioritization`, or `prioritized` are not old-name hits and are not
renamed.

## Implementation Log

| Commit | Contents |
| --- | --- |
| `0fc5370` | Classified inventory only; no rename edits. |
| `79b7ad2` | Renamed living README/product/package/config/data/source strings, preserved Hermes names, added atlas `PROVENANCE.md`. |
| `d1d54b2` | Updated the attestation provenance test allowlist so `source_file.mcp_server` remains an explicit fail-closed identity drift. |
| report commit | This final report update with verification table. |

## Implementation Summary

Renamed living surfaces to Entrelíneas/`entrelineas` where the change was not a
historical rewrite, pinned evidence mutation, Hermes toolset rename, repo/folder
rename, or generated refreeze. The `tqe` package name remains unchanged.

Attribution is preserved at the atlas via
`semantic-registry/atlas/PROVENANCE.md`, and the README now states that the
project was inspired by an exchange with Priori (the company), built
independently on public IDSSE/DFL data, and renamed Entrelíneas on 2026-07-05.

No `generated/`, prior `delivery/packets/*-REPORT.md`/`*-REVIEW.md`, prior
packet briefs, `delivery/ledger.jsonl`, ADR body text, committed evidence, or
`review-packets/` files were edited.

Expected old-name leftovers are the classified ones: Priori company attribution
and no-access history; current Render/GitHub/local-folder names; frozen Hermes
toolset identifiers; generated/registry/coverage outputs pending sanctioned
regeneration; protected AFL/imported-reference records; and historical evidence.

The first full-suite attempt on `79b7ad2` exposed the N1D attestation test
allowlist gap: the code correctly reported `source_file.mcp_server` as identity
drift after the MCP server prompt text changed, but the test did not list that
identity key. `d1d54b2` adds that key without weakening the fail-closed
attestation behavior. The pre-fix failure is the guard evidence for that one
line: without the key, the named test fails; with it, the named test passes and
still requires explicit identity-drift failures.

## Verification

| Command | Result | Tests | Duration | Notes |
| --- | --- | ---: | ---: | --- |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_executor_boundaries` | PASS | 17 | `0.179s` | Data-manifest schema source/test pair. |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_workbench_beta0_contract.WorkbenchBeta0ContractTests.test_match_library_is_limited_to_deployed_manifest_with_canonical_metadata` | PASS | 1 | `0.059s` | Deploy manifest still loads. |
| `npm --prefix apps/workbench-alpha run test:unit` | FAIL | 0 | pre-test | Sandbox denied `tsx` IPC pipe under `/var/folders/.../T`. |
| `TMPDIR=/private/tmp npm --prefix apps/workbench-alpha run test:unit` | PASS | 7 groups | not timed | `api`, `geometry`, `playback`, `presentation`, `workbenchState`, `overlay`, `momentZero`. |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python test` on `79b7ad2` | FAIL | 532 | `475.725s` | Long execution; one failure, `test_attested_novel_composition_requires_verified_plan_hash`, due missing `source_file.mcp_server` identity-key allowlist. |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_workbench_beta0_contract.WorkbenchBeta0ContractTests.test_attested_novel_composition_requires_verified_plan_hash` | PASS | 1 | `0.023s` | After `d1d54b2`. |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python test` on `d1d54b2` | PASS | 532 | `454.378s` | Long execution flagged; final committed-tree full suite. |

Final full-suite output summary:

```text
Ran 532 tests in 454.378s

OK
{"attestation_status": "VERIFIED", "blocking_reasons": []}
```

Untracked local files intentionally not staged:
`delivery/packets/r2-4-flagship/run-sidecar.local.json` and
`docs/visual-explainers/tactical-compilation-concept.png`.
