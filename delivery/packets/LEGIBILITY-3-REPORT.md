# LEGIBILITY-3 — composition and scope report

Requested branch: `packet/legibility-3`
Frontier: `15eb05b0e6012e08335693503b87c2c4bd220f0f`
Implementation status: `READY_FOR_REVIEW` — director capture repair, pixel audit,
golden promotion, deploy, and perceptual panel round 3 remain external gates.

## Outcome

The round-3 changes are surgical and confined to the existing Film Room
composition. No capture producer, constitution file, oracle, dev set, sealed
evidence, deployment configuration, or backend response schema was changed.

1. The header certification chip is derived from the interval source and now
   says `metric interval: certified` for the flagship. It no longer certifies
   the whole evidence pipeline.
2. The honest interval span uses full-salience slate `#8B93A0`; the observed
   point remains a thin amber tick. Its label is positioned from the same
   observed percentage and connected by a leader. In `observed 1/1 (100%)`,
   only the first `1` is amber; the remainder is chalk-dim.
3. The partition strip is directly labeled and the detached legend row is
   deleted. Nonzero segments have a 3px minimum. The flagship states
   `segment enlarged to be visible — true share 0.04%`.
4. UNKNOWN explanation moved out of the SVG into an opaque slate strip between
   the replay header and pitch. UNKNOWN witness labels, keys, markers, and
   leader lines are slate and dashed. Label placement tries above/below witness
   candidates and rejects occupied boxes. Entity coordinates now map inside
   the drawn pitch inset, leaving room for markers at every edge.
5. On answer, the keyed question panel is the sole question record. The ask
   input is cleared and becomes the empty `Ask another…` affordance. The 115 /
   2,811 reconciliation sentence renders only at the moment list.
6. The certified bootstrap genuinely uses one artifact: both `plan_hash` and
   `synthesized_document_hash` are assigned the committed plan hash by
   `film_room_answer_from_certified_table`. Equal hashes render once as
   `PLAN = DOC …`; distinct hashes still render as separate truthful labels.
7. The answer card remains within its existing three-size budget.
8. Witness timing uses canonical per-stage frame IDs. A key and marker are
   absent before their witness frame, appear on the first replay sample at or
   after it, and persist thereafter. The carry trail also draws only through
   the current replay frame.
9. Replay status now says `frame N of M · 25 fps`; stride and duration remain
   on the secondary line without repeating the fps unit. A single nearby
   legend identifies blue as the home team and red as the away team.

## Item 8 STOP-condition disposition

The STOP condition did not trigger. The execution cache carries
`stage_1_frame_id`, `stage_2_frame_id`, and `stage_3_frame_id` in the canonical
replay frame domain. `film_room_evidence_overlay` preserves them in
`stage_labels[*].frame_id`, and the descriptor test now asserts the exact
fixture sequence `[80, 100, 120]`. Frontend tests assert the visibility sequence
`[]` before frame 100, `[①, ②]` at frame 110, and `[①, ②, ③]` after frame 120.
No time or sample was synthesized.

## Scope note

The replay payload exposes home/away roles and canonical team IDs, but not club
display names. The color legend therefore says `home team` and `away team`.
Substituting a guessed club name would exceed the available response truth.

## Verification table

| Command | Result |
| --- | --- |
| `TMPDIR=/private/tmp npm run test:unit` | PASS — eight frontend unit modules; certification scope, interval/segment tokens, leader presence, single reconciliation call, PLAN=DOC branching, and witness timing covered |
| `TMPDIR=/private/tmp npm run build` | PASS — contract generation, TypeScript, and Vite |
| `TMPDIR=/private/tmp PYTHONPATH=src .venv/bin/python -m unittest tests.test_deploy2_lazy_hydration tests.test_film_room_app` | PASS — 15 tests, including canonical stage-frame preservation |
| `TMPDIR=/private/tmp MPLCONFIGDIR=/private/tmp/priori-matplotlib-legibility3 make test` | PASS — 599 tests in 544.272s; attestation `VERIFIED`, blocking reasons `[]` |
| `git diff --check` | PASS |
| Director-owned repaired capture producer | NOT RUN by executor — explicitly fenced by the packet; director supplies distinct landing / ③ witness / UNKNOWN / warming / empty-error frames and rendered pixel samples |

## Environment and deviations

- `git pull --ff-only` failed before mutation because the repository contains
  an invalid `refs/heads/packet/f2-0.lock.probe` reference. The checked-out HEAD
  already exactly matched the requested frontier and its configured origin.
- Creating `packet/legibility-3` failed because this sandbox cannot create
  `.git/index.lock`. Work therefore remains clean-ordered on the frontier
  checkout for director scribe/stage.
- The round-2 landing and pass captures are byte-identical, exactly matching
  the director's gate-integrity finding. They were used only as failure
  evidence, never as an approved visual target.
- No push or deploy was attempted.
