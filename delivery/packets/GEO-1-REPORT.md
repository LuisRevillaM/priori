# GEO-1 — `between_observed_lines` and certified reception recipe

Branch: `packet/geo-1`

Frontier: `079e3db686b63f0a507f1dee6e13708dda86607d`

Executor clone: `/private/tmp/priori-geo1-executor.Pug8zR` (outside the
repository tree)

Status: **IMPLEMENTED AND CERTIFIED — DIRECTOR REVIEW PENDING**

## Design brief (authored before implementation)

### Primitive boundary

`between_observed_lines` consumes an entity anchor collection and the
same-anchor `multi_line_model` collection. It evaluates one declared entity at
one declared frame against two observed geometric line boundaries. It does not
identify tactical line roles, formation, legal offside, intent, quality, or
optimality.

The catalog contract is version `0.1.0` with:

- inputs `line_evaluations` and `entity_anchors`, both anchor-scoped episode
  sets;
- typed field references `entity_id_field` (entity kind, default
  `receiver_id`) and `entity_frame_field` (frame kind, default
  `controlled_reception_frame_id`);
- declared numeric parameters `nearer_line_rank`, `farther_line_rank`,
  `line_boundary_buffer_m`, and `minimum_interline_gap_m`;
- `line_selector`, whose allowed values are `declared_ranks` and the ratified
  `deepest_observed_line` token; and
- anchor evaluations plus a tri-state `between_observed_lines_status` frame
  signal.

`minimum_interline_gap_m=0` means that no positive minimum has been declared.
Ranks are positive integers and must satisfy `nearer_line_rank <
farther_line_rank`. With `line_selector=declared_ranks`, those exact two ranks
are selected. With `line_selector=deepest_observed_line`, the nearer boundary
remains `nearer_line_rank` and the farther boundary becomes the identifiable
observed band with maximum normalized longitudinal coordinate. The declared
`farther_line_rank` remains echoed for compatibility and audit but is not the
selected farther boundary under that selector. The selected rank and selector
are both explicit evidence; the primitive never calls the deepest band a
defensive, back, last, or offside line.

### Geometry and selectors

At aligned frame `F`, the primitive uses the attacking-direction value emitted
by `multi_line_model`. For entity normalized longitudinal coordinate
`x'_entity` and selected line coordinate `x'_line`, signed distance is:

`s_line = x'_entity - x'_line`.

The selected nearer line must have a smaller normalized X than the selected
farther line. `interline_gap_m = x'_farther - x'_nearer`. With declared boundary
buffer `b`:

- `PASS` iff `s_nearer > b` and `s_farther < -b`;
- a signed distance in the closed buffer interval `[-b, b]` for either boundary
  is `UNKNOWN`; and
- every other adequately observed position is `FAIL`.

The output carries both line IDs, ranks, player memberships, physical and
normalized X coordinates, both signed distances, the inter-line gap, the
entity ID/frame/point, selector, complete parameter echo, the upstream
coverage/observation witnesses, and provenance row IDs.

If a positive `minimum_interline_gap_m` is declared and the observed gap is
smaller, the requested geometric interval is not established. This is
`FAIL/minimum_interline_gap_not_met` only when the pair is adequately observed;
it is never used to upgrade uncertain line evidence. A zero or negative
physical ordering is `UNKNOWN/selected_line_order_ambiguous`, because that
contradicts the rank/selector contract rather than testifying that the entity
is outside.

### Tri-state and GEO-0c inheritance

The primitive preserves one output row for every line-evaluation row with an
anchor frame, including missing joins. Its decision order is:

1. missing entity record or entity ID/frame/position → `UNKNOWN` with the exact
   typed reason;
2. entity frame unequal to `line_evaluation_frame_id` →
   `UNKNOWN/line_entity_frame_misaligned`;
3. invalid or conflicting attacking orientation → `UNKNOWN`;
4. `multi_line_status=UNKNOWN`, or defender observation other than `ADEQUATE`,
   or player-track coverage other than `CERTIFIED` → `UNKNOWN`, retaining the
   upstream reason and provenance rows;
5. adequately observed absence of either selected line → `FAIL` under GEO-0c;
6. boundary-zone membership → `UNKNOWN`;
7. adequately observed inside → `PASS`; adequately observed outside → `FAIL`.

An upstream `multi_line_status=FAIL` licenses the missing-pair `FAIL` only when
its GEO-0c witnesses say defender observation is `ADEQUATE` and player-track
coverage is `CERTIFIED`. No downstream code converts an unlicensed absence to
negative evidence. For the deepest selector, the chosen band is the maximum
finite `normalized_line_x_m`; a missing, duplicated, or invalid maximum is
uncertain rather than guessed.

### Certified composition

The ratified recipe is named `reception_between_observed_lines.v1` and is
materialized under `delivery/packets/geo-1-reception-between-lines/`.
Its standard-envelope meaning expression synthesizes and binds the registered
composition across all seven canonical matches, both periods, and both team
perspectives:

`controlled_pass_episode.anchors`
`→ multi_line_model(anchor_frame_field=controlled_reception_frame_id)`
`→ between_observed_lines(entity_id_field=receiver_id,`
`entity_frame_field=controlled_reception_frame_id,`
`line_selector=declared_ranks)`.

The saved definition declares ranks 1 and 2, `line_boundary_buffer_m=0.5`,
`minimum_interline_gap_m=0`, and the existing `multi_line_model` defaults
(`goal_side_buffer_m=1`, `line_band_width_m=2`,
`minimum_line_defenders=3`, `target_line_rank=2`). These are versioned recipe
parameters, not universal football truths.

`aggregate_over` groups the same-source geometry records by `receiver_id` and
counts `between_observed_lines_status`. `rate` uses
`between_observed_lines_status` as numerator and the carried
`controlled_pass_status` as denominator. Therefore the denominator is exactly
the controlled-reception evidence population, not all provider pass rows, and
the rate's joint A/B/C/D1/D2/E partition supplies observed/lower/upper bounds.
The numerator subset declaration is explicit: geometry `PASS` can occur only
on a row whose controlled reception and frame are established. A violation is
an invariant error, not a repaired row.

The committed table will include the 14 team-match rows, period partitions,
receiver groups, complete rate partitions and intervals, status/reason totals,
and compact PASS/FAIL/UNKNOWN witnesses with line/entity/coverage evidence. A
committed generator must execute the plan and reproduce the meaning expression
derivatives, bound plan, provenance, JSON table, and Markdown table byte for
byte under `--check`.

### Compatibility, mutation standard, and STOP law

This packet adds one catalog primitive and its semantic projections. It does
not change existing primitive defaults, existing plan documents, observation
law, line-band construction, field-reference kinds, serving contracts, frozen
expectations, or certified tables.

Named direction tests will cover normalized geometry in both attacking
directions, declared-rank selection, deepest-line selection, inside/outside,
both boundary buffers, frame misalignment, missing entity/orientation/line,
GEO-0c adequate missing pair versus inadequate observation, minimum-gap
behavior, typed-field migration, dispatch, and recipe rate/grouping evidence.

Mutation evidence will alter the strict inside inequality/buffer behavior and
bypass the GEO-0c adequacy guard in turn. Each named oracle must fail under its
mutation, pass after restoration, and leave no mutation in the source tree.

Before certification, an untouched `079e3db6` control and the GEO-1 tree will
run every pre-existing certified surface that binds `multi_line_model`
(directly Q3 and Q6) plus the standing certified R2/GALLERY controls. If any
pre-existing certified tactical value, status population, classification, or
table byte changes, execution stops and reports the exact delta. Identity-only
hash movement caused by the additive catalog/evidence contract will be
disclosed, never presented as a value delta. No frozen expectation or existing
certified table is rewritten on this branch.

## Implementation record

The design was sealed before implementation in `58110e69`. The pure geometry
kernel, line-family runtime adapter, typed catalog contract, semantic registry
mapping, generated projections, and direction/honesty tests landed in
`bf243f86`. The certified composition and its producer landed in `7822f230`.
The compiler-vocabulary additive-count ratchet was corrected in `a8dd4cf4`.

`src/tqe/runtime/between_observed_lines.py` now implements the declared signed
geometry independently of serving or recipe code. It selects declared ranks or
the unique maximum-normalized-X `deepest_observed_line`, checks physical and
normalized orientation agreement, emits line identity and defender membership,
and applies the closed boundary buffer. The result cannot become `FAIL` unless
the inherited GEO-0c defender-observation status is `ADEQUATE` and player-track
coverage is `CERTIFIED`. Missing entity/frame/position, frame misalignment,
orientation uncertainty, invalid line geometry, inadequate observation, and
the boundary zone remain typed `UNKNOWN` outcomes.

The runtime adapter preserves one same-anchor record and passes through the
controlled-pass population fields needed by registered aggregation and rate
operators. Catalog parameters use GEO-0b field references for `receiver_id` and
`controlled_reception_frame_id`. The primitive is registered through the full
concept → operationalization → implementation → runtime binding → claim →
evidence → exposure → maturity chain, and the committed producers regenerate
the catalog, capability context, tactical knowledge pack, SCP-0 projections,
passport, parity report, and registry lock.

The standard-envelope compiler needed one exact construction rule: one shared
`controlled_pass_episode` stream feeds both `multi_line_model` and
`between_observed_lines`; it never synthesizes two independently evaluated pass
populations. The recipe adds an optional `team_scope` parameter to
`controlled_pass_episode`. Its default is `all`, preserving every existing
plan. GEO-1 alone binds `perspective_team`, preventing opponent pass rows from
being interpreted against the declared team orientation. The bound recipe then
adds registered `aggregate_over(group_by=receiver_id)` and `rate` terminals over
the same geometry records.

## Certified composition and the zero-PASS finding

The committed standard-envelope artifacts live under
`delivery/packets/geo-1-reception-between-lines/`. The generator executes all
seven canonical matches, both team perspectives, and both periods. It asserts
the one-shared-chain wiring, binds the complete composition, rejects any
opposite-team row, reconciles every receiver group against both operators, and
commits compact geometry/coverage witnesses.

| Certified measure | Value |
| --- | ---: |
| Evaluated anchor rows | 4,189 |
| `between_observed_lines=PASS` | 0 |
| `between_observed_lines=FAIL` | 2,909 |
| `between_observed_lines=UNKNOWN` | 1,280 |
| Controlled-pass denominator PASS | 2,909 |
| Controlled-pass denominator UNKNOWN | 804 |
| Controlled-pass denominator FAIL | 476 |
| Observed rate | 0 |
| Joint-unknown lower bound | 0 |
| Joint-unknown upper bound | 0.21653649340156209 |

Reason totals are `selected_line_not_observed=2450`,
`entity_frame_missing=1280`, and `entity_outside_observed_lines=459`. Plan hash
is `b58f5a84796666eb6d42bd835bd9598f92be49c6e7953d26ecfcdde0e0e58e77`;
table hash is
`d302e36cff59deff1f393d11c66edb6d1d33bdad478f32e68342b91c01854e50`.
The committed `--check` run re-executed all 4,189 rows and reproduced the plan,
JSON table, Markdown table, and provenance byte for byte.

The zero PASS count is a definition-level finding, not a failed data search and
not something this packet silently repairs. The ratified round-1 definition
says the normal pair is line ranks 1 and 2 goal-side of the ball. The certified
recipe evaluates the receiver and `multi_line_model` at the same controlled-
reception frame. At that frame the receiver is at the ball, while every line
candidate is constructed strictly goal-side of the ball. Consequently every
adequately observed pair places the receiver behind the nearer line; none can
satisfy `s_nearer > b`. Changing the line model to include bands behind the
ball, or evaluating reception geometry against release-frame lines, would be a
new charter/recipe ruling. This executor did neither. The primitive remains a
valid general geometry primitive for entity/frame compositions whose entity can
lie between the declared observed bands, but this exact flagship composition is
structurally incapable of a positive row under the current definitions.

## Mutation evidence

Two source mutations were applied separately and completely restored:

1. The closed buffer test was changed from `<= b` to `< b`. The named oracle
   `test_closed_boundary_buffer_is_unknown_at_both_lines` failed: an entity at
   exactly 0.5 m changed from expected `UNKNOWN` to `FAIL` (exit 1). After
   restoration the same oracle passed.
2. The GEO-0c adequacy branch was bypassed for upstream `FAIL` line evidence.
   `test_fail_status_without_adequate_coverage_is_forced_unknown` failed because
   the licensed insufficient-observation reason was replaced by
   `selected_line_not_observed` (exit 1). After restoration it passed.

A source diff against `7822f230` proved neither mutation remained. The focused
suite also exercises signed geometry in both attacking directions.

## Certified-result STOP audit

Control clone: `/private/tmp/priori-geo1-control.BDh1Ab`, detached at
`079e3db686b63f0a507f1dee6e13708dda86607d`. The control and GEO-1 trees used
the same canonical/raw corpus, one worker, and separate cold node-cache roots.

| Certified surface | Untouched frontier control | GEO-1 | Value verdict |
| --- | --- | --- | --- |
| Q3 execution | PASS; 13 results; 0 evidence failures | exact same | no delta |
| Q3 multi-line probe | PASS 142; FAIL 106; UNKNOWN 0; population 248 | exact same | no delta |
| Q3 downstream probes | support FAIL 184 / UNKNOWN 64; action chain PASS 146 / FAIL 64 | exact same | no delta |
| Q6 execution | PASS; honest zero; 0 results; 0 evidence failures | exact same | no delta |
| Q6 line transition | PASS 1; FAIL 13; UNKNOWN 3; population 17 | exact same | no delta |
| Q6 pressure / velocity | pressure PASS 5 / FAIL 7; velocity PASS 17 | exact same | no delta |

The additive controlled-pass parameter changes bound-plan identity, as required
by the cache-key law: Q3 moves from `88970ddc...` to `04bdaf58...`; Q6 moves
from `f1a264b2...` to `ee2a97b6...`. Q3's 13 identity-bearing `result_id` values
therefore move. Removing only `result_id`, the freshly executed control and
GEO-1 result rows are byte-identical with SHA-256
`c918f1e9ea07f95f0c703a69a4fa3bb1b96b4befd0ca4edb5425e3392911c1b9`.
Q6 retains the canonical empty-row hash
`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
No status, population, classification, evidence value, or tactical result
changed. No pre-existing plan, certified table, oracle, dev set, or frozen
expectation was rewritten. Therefore **the certified-value STOP condition does
not fire**.

## Verification table

| Gate | Result |
| --- | --- |
| GEO-1 primitive/recipe suite | PASS — 14 tests |
| GEO substrate + line kernels + executor boundaries | PASS — 95 tests in 0.913 s |
| Closed-buffer mutation | EXPECTED FAIL; restored oracle PASS; mutation absent |
| GEO-0c guard mutation | EXPECTED FAIL; restored oracle PASS; mutation absent |
| Standard-envelope generation | PASS — 4,189 rows across 28 scopes |
| Byte-reproducing generator `--check` | PASS — plan/table/Markdown/provenance reproduced |
| Q3/Q6 frontier-vs-GEO STOP comparison | PASS — exact values; identity-only movement disclosed |
| SCP-0 generation and read-only verification | PASS — zero findings and 45 registry tests |
| `compileall`, `git diff --check`, source restoration | PASS |
| Initial full-suite attempt | INVALID ENVIRONMENT — 616 tests, 2 failures + 5 errors in 496.205 s; missing ignored canonical files plus one real additive-count ratchet |
| Named-failure rerun after corpus copy and ratchet fix | PASS — 36 tests in 389.341 s |
| Final canonical `make test` | PASS — 635 tests in 603.300 s; attestation `VERIFIED`; zero blockers |
| Leg zero | PASS — charter, GEO-0a/0b/0c laws, existing certified artifacts, and frozen expectations unchanged |

## Deviations and repository state

- All work is confined to external executor clone
  `/private/tmp/priori-geo1-executor.Pug8zR`; no clone was created inside the
  repository tree.
- The first full-suite attempt exposed that Git does not carry the ignored
  canonical Parquet corpus into a clone. Environment variables covered executor
  defaults, but six older tests intentionally use relative paths. A regular-file
  copy of the same 182 MB canonical corpus was placed under the clone's ignored
  `data/canonical/v1`; it creates no tracked diff. The complete red attempt is
  reported above rather than erased.
- The same first attempt caught the one legitimate missed ratchet: compiler
  vocabulary increased from 37 to 38 primitives. Only that expected count was
  changed; no fixture, oracle, frozen expectation, or certified value was
  altered.
- No serving, deployment, registry vocabulary beyond the ratified primitive,
  memory path, or external service was touched. No 2 GiB proof applies.
- No push was attempted. Pre-report packet commits are `58110e69`, `bf243f86`,
  `7822f230`, and `a8dd4cf4`.
