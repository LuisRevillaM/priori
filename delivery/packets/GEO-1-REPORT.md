# GEO-1 — `between_observed_lines` and certified reception recipe

Branch: `packet/geo-1`

Frontier: `079e3db686b63f0a507f1dee6e13708dda86607d`

Executor clone: `/private/tmp/priori-geo1-executor.Pug8zR` (outside the
repository tree)

Status: **DESIGN SEALED — IMPLEMENTATION PENDING**

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
