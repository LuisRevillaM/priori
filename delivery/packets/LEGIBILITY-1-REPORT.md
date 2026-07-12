# LEGIBILITY-1 Report — implementation ready for director golden review

Status: FIXES DELIVERED — AWAITING DIRECTOR GOLDEN PROMOTION

Branch: `packet/legibility-1`

Frontier: `b14a2367435f450802e098282d747636905e43d9` (the director's
STATE-only session-close commit advanced the branch during execution; no
implementation path overlapped)

## Delivered surface

- The answered question carries ①②③ clause keys derived from the committed
  typed `meaning_clauses` and the `sequence_pattern` stage declaration. No
  question-specific display copy is stored in the response.
- The turf carries amber-on-ink mono key chips for the regain, carry threshold,
  and kept pass. Stage-aware offsets keep clustered witnesses legible.
- PASS moments read `① time regain → ② +distance m carry → ③ pass kept`; the
  distance comes from the stage-2 witness in the lazily opened hydration shard.
- A truncated stage-2 UNKNOWN reads, verbatim, `couldn't see whether ② happened
  — half ended`.
- The interval card restates population, completed chain, unknown partition,
  and honest bounds. Its metric name moved to provenance.
- Default cards no longer expose chain status fields, anchor/frame ids, node
  names, internal provider names, or truncation codes. Raw evidence remains
  available behind the existing JSON control.

The public answer now carries its typed meaning expression so the browser can
derive clause text for both the committed gallery and live compiled asks. The
addition is represented in the generated API schema and type artifacts.

## Required director gate

The three 1440×1100 captures below are **candidates, not goldens**. They are not
staged or committed. Per packet law, the director must review them before any
copy is committed as a golden.

| Candidate | SHA-256 |
| --- | --- |
| `artifacts/legibility-1/candidates/gallery-answer.png` | `d5cc1e3289b841f2995a2760ab1306008aa27a76fd81e51d1adbb0713a4caa86` |
| `artifacts/legibility-1/candidates/keyed-moment-replay.png` | `264abf25ec6daae541c026be756b7322279e734e555ecf61b34821ae9b016b71` |
| `artifacts/legibility-1/candidates/unknown-moment.png` | `c76a05e93bacac471111e236dded8ae0acbdaa4df6dde365743e7e58869e42da` |

The committed Playwright producer runs the N8 task verbatim: `read the
question, watch one replay, narrate which part is which`. It also scans the
visible surface for the packet's schema-token lint list.

Multimodal critic scoring, the genuinely fresh cold walkthrough, and the
director delight pass remain director-owned acceptance work. This executor
does not call the screen accepted.

## Ambiguity reported, not improvised

The packet's illustrative sentence says `Of 115 regains, 1 completed ... 90
couldn't be fully seen`, but the sealed/live certified interval source says
population `2,811`, completed `1`, unknown `2,810`, bounds `[0.04%, 100%]`.
The UI uses the authoritative certified population and partition, while the
moment list separately says `115 chain moments`. Substituting the visible
descriptor subset into the certified denominator would make the answer read
better while becoming false. A different copy choice requires a director
ruling or a changed evidence contract.

## Full-suite table

| Command | Result |
| --- | --- |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_deploy2_lazy_hydration tests.test_deploy1c_gallery_from_tables tests.test_deploy1_public_mode` | PASS — 17 tests |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_film_room_app tests.test_deploy2_lazy_hydration` | PASS — 10 tests |
| Frontend unit modules via `node --import tsx` | PASS — 8 modules, including fixture mutation and literal N8 copy assertions |
| `npm --prefix apps/workbench-alpha run build` | PASS — schema generation, TypeScript, Vite |
| `LEGIBILITY_CANDIDATE_DIR=artifacts/legibility-1/candidates npx playwright test tests/legibility1.spec.ts --project=chromium` | PASS — verbatim N8 walk, three candidate captures, visible-token scan |
| `MPLCONFIGDIR=/private/tmp/priori-matplotlib make test` | PASS — 594 tests in 555.960s; attestation VERIFIED |
| `git diff --check` | PASS |

The first full-suite run exposed one pre-N8 assertion that still required
`carry >= 3m` / `pass`. That assertion was updated to the dictated plain labels
`at least 3 m` / `pass kept`; the complete 594-test suite was then rerun from
the beginning and passed.

Deviation: `npm run test:unit` cannot start the `tsx` CLI's Unix IPC socket in
this executor sandbox (`listen EPERM .../tsx-501/*.pipe`). The same eight test
modules were run through Node's supported `--import tsx` loader and all passed.
Product code and test assertions were not altered to accommodate the sandbox.

No file under `docs/design/**`, no deploy oracle, dev set, blind pin, or sealed
evidence was modified.

## Round 2 — ACCEPT-WITH-FIXES response

Review basis: `delivery/packets/LEGIBILITY-1-REVIEW.md` at `46f58b7`.

The three exact fixes are delivered:

1. The pre-hydration PASS card now says `② watching the carry…`; after lazy
   hydration it still replaces that phrase with the observed witness value.
2. Missing, blank, and literal-sentinel `unknown` tree values render as
   `TREE —` with `title="Tree hash unavailable in this build"`. A real tree
   continues to render its first 12 characters and exposes its full value in
   the title.
3. The committed Playwright producer was rerun after both fixes and replaced
   all three candidate PNGs in `artifacts/legibility-1/candidates/`.

The recaptured candidates below supersede the Round 1 candidate bytes. They
remain uncommitted for director-only golden promotion.

| Round 2 candidate | SHA-256 | Dimensions |
| --- | --- | --- |
| `artifacts/legibility-1/candidates/gallery-answer.png` | `79554686c79498ad295ec337bc3281640d148ed4e96dd6bad5652a1dc4c4d908` | 1440×1100 |
| `artifacts/legibility-1/candidates/keyed-moment-replay.png` | `f5f01e36d6110605bc238a9c74b599948abd6ebebc99443cd706411e2c542ecc` | 1440×1100 |
| `artifacts/legibility-1/candidates/unknown-moment.png` | `c2e6b6a9b167c132dbb7803d7c9230989c443a6ea3c7f26385373b09bf1066ba` | 1440×1100 |

### Live-tree check

Current live bootstrap verification is **unverified from this executor**. The
public hostname could not be resolved by the shell (`curl: (6)`), the internet
reader could not open the unindexed endpoint, the in-app browser exposed no
browser backend, and the shell `agent-browser` runtime is not installed.
Historical committed live bootstrap evidence confirms that deployed responses
have carried real tree hashes, but it is not substituted for a current check.
The director must confirm the current live tree value during promotion/ship.

### Round 2 full-suite table

| Command | Result |
| --- | --- |
| Frontend unit modules via `node --import tsx` | PASS — 8 modules; exact loading copy and absent/sentinel/real tree cases covered |
| `npm --prefix apps/workbench-alpha run build` | PASS — TypeScript and Vite |
| `LEGIBILITY_CANDIDATE_DIR=artifacts/legibility-1/candidates npx playwright test tests/legibility1.spec.ts --project=chromium` | PASS — N8 walkthrough, `② watching the carry…`, titled `TREE —`, three recaptures |
| `MPLCONFIGDIR=/private/tmp/priori-matplotlib make test` | PASS — 594 tests in 745.270s; attestation VERIFIED |
| `git diff --check` | PASS |

## Live-regression hotfix — descriptor cache migration

Branch: `packet/legibility-1-hotfix` from `fafdb21`.

### Diagnosis and deviation

The rollback experiment correctly disproved ephemerality: the descriptor and
hydration files survive on the persistent cache disk. Inspection did **not**
find a new typed field on `FilmRoomMomentResponse`; the legibility delta changed
the meaning payload and descriptor overlay producer. The old fragment format
had no producer epoch, so it could not distinguish compatible bytes from stale
derived semantics. That cache-law gap is fixed as directed.

The first container run also found an independent, ship-blocking cause absent
from the stated diagnosis: `Dockerfile` did not copy LEGIBILITY-1's new
`counterattack_initiation_sequence_rate.v0.json` meaning expression. The
counterattack certified prewarm therefore failed before descriptor upgrade.
The amended image now contains that committed file; its in-image SHA-256 is
`e59bd793b8096bb5a266cff7774da9fc0bf3788936400f96d4241b2debc1e1f1`.
This deviation is necessary to make the shipped surface reach ready and is
covered by a named regression test.

### Delivered behavior

- Descriptor fragments and the merged index are now v2 and carry a code epoch
  bound to the descriptor schema and producing `app_service.py` bytes. A
  schema/code change is a cache miss.
- Missing or invalid fragments rebuild from the matching durable execution
  cache without executing a plan. The selector reads at most a 1 MiB metadata
  prefix per candidate.
- Chain-producing execution payloads have a hard 64 MiB load guard. The real
  counterattack payloads are 4,403,154 and 2,412,577 bytes. The 908–912 MiB
  fragile-retention envelopes are never decoded; their empty chain fragments
  rebuild metadata-only.
- Old absolute `/app/...` and current repository-relative spellings of the same
  plan are accepted as equivalent hydration provenance only when every other
  payload field matches.
- Rebuild start/completion events name flagship, role, reason, and disk-cache
  source. A failed rebuild leaves bootstrap `warming` with the exact failure in
  `descriptor_rebuild` and `last_error`; validation failure cannot become a
  silent zero.

### 2 GiB proof

The committed producer ran against a fresh runtime root and a hard-linked copy
of the real DEPLOY-2 cache bundle, beginning with four v1 fragments and 115
away chain descriptors. `WORKBENCH_PREWARM_FILM_ROOM=0` throughout.

| Run | Result | Peak | Headroom |
| --- | --- | ---: | ---: |
| Preserved attempt 1 | FAIL honestly — missing image asset plus absolute/relative hydration-path conflict | 90.59 MiB | 1,957.41 MiB |
| Exact current source in production image | PASS — ready, 115 moments, four cache-only rebuilds | 166.42 MiB | 1,881.58 MiB (91.87%) |
| Amended production image, no source/asset mounts | PASS — ready, 115 moments, prewarm off | 95.85 MiB | 1,952.15 MiB (95.32%) |

No run was OOM-killed. Raw stdout/stderr, cgroup counters, container states,
hashes, and the producer live under
`delivery/packets/legibility-1-hotfix-evidence/` and
`scripts/packets/legibility1_hotfix_evidence.py`.

### Hotfix full-suite table

| Command | Result |
| --- | --- |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_deploy2_lazy_hydration tests.test_deploy1c_gallery_from_tables tests.test_deploy1_public_mode tests.test_film_room_app` | PASS — 26 tests |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_deploy2_lazy_hydration` on the final tree | PASS — 8 tests |
| `MPLCONFIGDIR=/private/tmp/priori-matplotlib make test` | PASS — 596 tests in 1020.980s; attestation VERIFIED (run began before the final three guard tests were appended) |
| `MPLCONFIGDIR=/private/tmp/priori-matplotlib-final make test` | PASS — 599 tests in 828.585s; attestation VERIFIED; exact final tree |
| Production Docker image build | PASS — image `sha256:c79d8b28b825590a09e9d9aa1ce27dcf2a699987ef06baf2d686548b48964688`; meaning asset verified in-container |
| `git diff --check` | PASS |

No Render service was mutated. The director remains the ship authority.
