# LEGIBILITY-1 Report — implementation ready for director golden review

Status: READY_FOR_DIRECTOR_GOLDEN_REVIEW

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
