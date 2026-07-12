# LEGIBILITY-2 — truth in ink report

Branch: `packet/legibility-2`
Frontier: `f8445f2651131fe8ba455b24da8a879d0c4fcadc`

## Outcome

All thirteen dictated fixes are implemented without changing the constitution,
tokens, sealed evidence, dev sets, or delivery oracles. The committed Playwright
producer now exercises both answer-card layouts, samples rendered COMPLETE and
UNKNOWN badge colors, proves the replay scrubber focus state, and captures an
UNKNOWN replay with slate/dashed doubt markers.

The three gating semantics are now explicit:

- Finding-first is selected when observed-n is below 30 or UNKNOWN exceeds 50%.
  The flagship renders `1 of 2,811 seen through`; `observed 1/1 (100%)` is body
  evidence, followed by the dictated uncertainty sentence.
- The honest interval is dim slate and the observed value is a single amber
  tick. Every nonzero partition segment has a 2px minimum.
- COMPLETE uses amber. UNKNOWN badges, selection borders, pitch markers,
  banner accents, and legend swatches use slate `#8B93A0`; UNKNOWN pitch marks
  are dashed and say `not verified`.

## Why the gallery has 115 moments for a 2,811-regain answer

This was traced through the producer rather than inferred from the screen.
The certified interval aggregates 28 team/match-half partitions and contains
2,811 regain-start chain records. The execution cache returned one classified
result: the away-side `J03WOY` second-half partition containing the one completed
chain. `write_film_room_descriptor_fragment` creates replay descriptors only
from `requested_evidence.source_records` attached to returned classified
results, so that one partition contributes 115 descriptors and the other 2,696
records contribute only to the certified aggregate on this surface.

The backend now emits structured `film_room.replay_coverage.v1` metadata. Both
the answer banner and list header derive this sentence from it:

> Showing 115 of 2,811 — replay details exist only for the match-half containing the completed chain.

If the structured reason is absent, the UI says the reason is not recorded; it
does not guess.

## Other changes

- PASS display vocabulary is now COMPLETE, and COMPLETE sorts above UNKNOWN.
- The answer banner uses the dictated intrinsic panel2 treatment.
- Replay UI states source fps, frame stride, sample count, and window duration;
  the clock is anchored to the selected moment's match time. Descriptor rebuilds
  now derive per-chain match time from canonical frames rather than inheriting
  the classified result row's time.
- Provenance never ellipsizes its certification fields. TREE absence says
  `TREE not recorded`; Hermes, synthesis, and execution timings say
  `not measured` when no measurement exists.
- Moment overflow is measured after layout, with a below-fold count; pitch label
  placement rejects overlapping rectangles.
- The header now says `both teams` and `evidence pipeline: certified`; the
  answer card states `both teams across 7 matches`.

## Dictated-design ambiguity

Fix 11 says to name the team, but the flagship interval is an aggregate of both
home and away roles across seven matches and its response exposes no single
club whose regains own the denominator. Naming one club would be false. The
implementation therefore uses the literal scope `both teams across 7 matches`
and removes the `away+home perspective` jargon. A club-specific name requires
a team-specific evidence contract or a director-specified cohort label.

## Candidate screens

These are review candidates, not accepted targets or goldens. Director review
and promotion remain outstanding.

| Candidate | SHA-256 |
| --- | --- |
| `artifacts/legibility-2/candidates/gallery-answer.png` | `06c82cfced70332d35227a1a876eae3c21a362ce5b248570ede8afc0b5b05618` |
| `artifacts/legibility-2/candidates/keyed-moment-replay.png` | `1f190d3800fe2381a292fdaf0457cbdb7b9bc7b5717bf291f52364621dc77041` |
| `artifacts/legibility-2/candidates/unknown-moment.png` | `a84d57770dc7274d755544d7ff8d3907165d6fcc77ee4a880b861f17215795fa` |
| `artifacts/legibility-2/candidates/ratio-first-answer.png` | `4588af54e0de94f71ceadd3eabe213e6927c4165d3f24a326508fd8f63cc1ae1` |
| `artifacts/legibility-2/candidates/unknown-slate-replay.png` | `10a8a59c8863cd2e6067ade4b8c68c3e1e2379a4499679dacc836a298742f708` |

The first capture attempt exposed partially painted Chromium PNGs. The producer
was hardened to await font readiness and two animation frames, then settle for
250ms with animations disabled. All five final candidates were visually opened
and checked. The focused UNKNOWN candidate also records the keyboard focus ring.

## Full-suite table

| Command | Result |
| --- | --- |
| `TMPDIR=/private/tmp npm run test:unit` | PASS — 8 frontend unit modules; status-token lint, data-derived denominator text, threshold switch, replay clock/sampling covered |
| `TMPDIR=/private/tmp npm run build` | PASS — contract generation, TypeScript, and Vite |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_deploy2_lazy_hydration tests.test_film_room_app` | PASS — 15 tests |
| `LEGIBILITY_CANDIDATE_DIR=artifacts/legibility-2/candidates npx playwright test tests/legibility1.spec.ts` | PASS — N8 cold walkthrough, two layouts, token audit, UNKNOWN slate replay, five captures |
| `TMPDIR=/private/tmp MPLCONFIGDIR=/private/tmp/priori-matplotlib-legibility2 make test` | PASS — 599 tests in 596.914s; attestation `VERIFIED`, blocking reasons `[]` |
| `git diff --check` | PASS |
| `TMPDIR=/private/tmp npm run test:acceptance` | PARTIAL — contracts, fixture gate, unit tests, build, and LEGIBILITY-2 spec pass; 16 pre-existing root-route E2E cases fail because they open `/` expecting the retired Host Workbench while the frontier routes `/` to CoachSurface. Captured accessibility trees show the high-bypass browser. One concurrent backend E2E also encountered its shared-output JSON write race. No failing case exercises a changed LEGIBILITY-2 path. |

## Deviations and environment facts

- `git pull --ff-only` could not write `.git/FETCH_HEAD` (`Operation not
  permitted`). The checked-out frontier already exactly matched the packet's
  `f8445f2`, and the branch was created from that SHA.
- One frontend unit invocation hit the sandbox's `tsx` IPC denial under the
  macOS private temp path. The unchanged command passed with
  `TMPDIR=/private/tmp`.
- `pytest` and `ruff` are not installed in the project virtualenv. The canonical
  unittest and build gates were used; `git diff --check` is green.
- The Playwright app server logs its expected fixture-only descriptor-cache miss
  before route interception. The committed LEGIBILITY-2 test passes.
- No service was deployed or mutated. Auto-deploy remains off and the director
  owns deployment, golden promotion, and perceptual panel round 2.
