# Work Packet F1-D — Lane-Model Unification and Occupancy Honesty

Issued: 2026-07-02 by the project director. Self-contained brief for an
external executor. Final packet of remediation phase F1.

## Ground rules (unchanged regime; two-round precedents apply)

- Dedicated branch `packet/f1-d` off `codex/afl08-passport-loop` (tip
  `d006780` or later). Acceptance review gates the merge.
- Read first: `docs/audits/FOUNDATION_AUDIT_2026-07-01.md` (findings G4, G2,
  and the spatial-audit lane items), `delivery/packets/F1-B-REVIEW.md` and
  `F1-C-REVIEW.md` (what acceptance rejects; the standing full-suite bar).
- Tri-state doctrine as always. All gates read-only; never `TQE_WRITE=1`;
  fences: `semantic-registry/`, `generated/`, `frozen-expectations/`,
  `delivery/n1d/`, `artifacts/`, case-study files.
- **Standing bar (from F1-C):** your report MUST include the full-suite
  table (`PYTHONPATH=src .venv/bin/python -m unittest discover -s tests`)
  with every failure enumerated and attributed. No table, no review.
- Env: `.venv/bin/python`, `PYTHONPATH=src`; needs `data/canonical/v1`.
  `tests/test_afl_validation_factory` fails on uncommitted runtime edits by
  design.

## Scope

### 1. G4 — one lane geometry for the whole catalog

Two incompatible lane models coexist:
- `src/tqe/runtime/lane_occupancy.py`: five equal 13.6 m lanes with a
  globally lower-inclusive/upper-exclusive boundary policy that is
  mirror-asymmetric (y=-20.4 → LEFT_HALF_SPACE but y=+20.4 → RIGHT_WIDE —
  a committed test asserts this asymmetry deliberately);
- `src/tqe/runtime/relations.py` `destination_lane`: 0.33/0.66 fractional
  half-width bands (central < 11.22 m, half-space 11.22–22.44, wide
  ≥ 22.44).
Reproduced consequence: y=8.0 is "central" to the corridor model but
RIGHT_HALF_SPACE to lane occupancy; any composed query mixing them
disagrees with itself.

Fix: extract ONE shared lane module (suggest
`src/tqe/runtime/lane_geometry.py`) providing the partition, used by both
consumers. Director rulings to implement:
- **The five-equal-lanes model wins** (13.6 m bands — it matches
  coaching-standard five-lane language; the fractional model was ad hoc).
- **Boundary policy: symmetric about y=0** — band edges at |y| with the
  edge belonging to the inner band (ties toward center), and an explicit
  `tie_epsilon_m`. The committed test asserting the asymmetry gets updated
  with justification (it pinned a bug as behavior).
- `destination_lane` classifications in `relations.py` re-express in the
  shared model; `destination_side("central")` being a measure-zero category
  at exactly y==0.0 (spatial item 17) gets a declared central band, not a
  point.
- Declare the lane partition in the catalog entries that expose lane
  outputs (names, band edges, boundary policy, epsilon) — declared
  semantics, not code trivia.

### 2. G2 — occupancy requirements count players, not player-frames

`lane_occupancy.py:257,494-511`: requirements aggregate player-frame
assignments, so one player in CENTRAL across 2 frames satisfies
"2 players in CENTRAL" (reproduced false PASS). Fix: requirements evaluate
per frame over distinct players, with the aggregation across the window an
explicit declared semantic (`all_frames` / `any_frame` / `min_frame_ratio`
— pick a declared default, document it). PASS only when the requirement
holds under the declared aggregation; insufficient frame coverage routes
through the same UNKNOWN discipline as everywhere else.

### 3. Ride-along backlog (required this time — small, enumerated)

- `relations.py:55-66` (current line refs may have shifted): the
  orientation-unavailable path fabricates a synthetic
  `Counter({"UNKNOWN": 1})` state — an unevaluated window must report
  zero states (the empty counter already yields UNKNOWN) and must not
  pollute global state counts.
- Promote the corridor executor-path test from single-node
  `_execute_node` to full `execute()` end-to-end (F1-C review item).
- Move the 11 corridor tests out of `tests/test_m2a_bypass.py` into
  `tests/test_corridor_episode_honesty.py` (pure relocation; the bypass
  file returns to bypass-only).
- Declare (docstring + catalog limitation line) the F1-C round-2 semantic
  choice: whole-missing-frame UNKNOWN emission is scoped to window-present
  targets, so a roster player never tracked in-window emits no states.
- `event_type_allowed` empty-tuple widen (F1-B review F3): make the empty
  filter tuple fail closed (UNKNOWN/rejected), unreachable today but a
  latent fail-open.

## Required tests

House style `tests/test_m2a_bypass.py` (style model, NOT the destination
file). Minimum: shared-model equivalence (both consumers classify a grid of
y-values identically, including all band edges, both signs); mirror
symmetry (classify(y) mirrors classify(-y) exactly); tie handling at every
edge with the declared epsilon; per-frame requirement semantics (the G2
false-PASS reproduction must now FAIL or UNKNOWN per declared aggregation;
one-player-two-frames vs two-players-one-frame distinguished); UNKNOWN
coverage routing; executor-path test through full execute() for a
lane-consuming plan.

## Expected legitimate ripples (report, don't fix)

Lane reclassification changes evidence and possibly results wherever lanes
appear: survey and report every gate/test consuming lane outputs
(`afl-lane-occupancy-verify`, any lane-occupancy frozen expectations,
corridor destination_lane evidence in M1.1/N1 paths — N1 stays fenced,
report only). Quantify the classification delta on the corpus: how many
player-frame lane assignments change bands, and how many corridor
destination_lane classifications change, per match. Contract regeneration
and re-freezes happen at director acceptance.

## Deliverables

1. Branch `packet/f1-d`, focused commits (suggest: shared module + G4,
   then G2, then ride-alongs).
2. New tests green; full suite table (standing bar) with every failure
   attributed.
3. `delivery/packets/F1-D-REPORT.md`: per-fix summary with file:line; the
   lane-reclassification delta tables; gate-status table; every changed
   pin justified; anything this packet missed.
