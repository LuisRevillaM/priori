# GEO-1c — entity-relative bracketing and amended reception recipe

Branch: `packet/geo-1c`

Frontier: `3403c51b`

Executor clone: `/private/tmp/priori-geo1c-executor`

Status: **IMPLEMENTED AND CERTIFIED — HONEST ALL-UNKNOWN FINDING**

## Sealed contract

`between_observed_lines` advances from `0.1.0` to `0.2.0`. The additive
`entity_relative_bracketing` selector sorts valid observed lines by normalized
longitudinal coordinate and selects exactly one adjacent pair satisfying
`ball_side_x <= entity_x <= goal_side_x`. No pair is typed UNKNOWN; more than
one pair is ambiguous and typed UNKNOWN. The existing GEO-0c adequacy gate runs
before selection, and the existing closed boundary buffer runs after selection.
Both selected line identities, ranks, memberships, signed distances, and gap
remain in the standard evidence record. Declared-rank and deepest-line behavior
is unchanged.

The amended recipe is a new `reception_between_observed_lines_v2` artifact
family under `delivery/packets/geo-1c-reception-between-lines/`; it binds
`line_selector=entity_relative_bracketing` explicitly. The GEO-1 v1 plan,
zero-PASS table, provenance, meaning expression, and generator are immutable.

## Ratchet inventory

The vocabulary name census remains 39: this is a version replacement, not a
new primitive name. The following versioned contracts move and must be
acknowledged by name wherever their pinned hashes fire:

- `binding.primitive.between_observed_lines.0_1_0` → `.0_2_0`;
- `exposure.runtime.between_observed_lines.0_1_0` → `.0_2_0`;
- `maturity.runtime.between_observed_lines.0_1_0` → `.0_2_0`;
- generated capability catalog, capability context, tactical knowledge pack,
  runtime manifest, capability passport, AI/product/atlas/unsupported/recipe
  projections, semantic parity report, and registry lock;
- the GEO-0b typed-field-reference catalog census; and
- any plan/bound-plan hash fixture that includes the complete catalog contract.

No drift baseline will be rewritten until its failing test identifies the
exact moved contract. Every update will name that ratchet in the final record.

## Implementation

The kernel and catalog now expose `entity_relative_bracketing` under
`between_observed_lines@0.2.0`. It selects a unique adjacent normalized-X pair
around the entity before applying the unchanged ordering, minimum-gap, signed-
distance, and closed-buffer laws. No pair yields
`UNKNOWN/entity_relative_bracketing_not_observed`; a shared-boundary double
match yields typed ambiguity. GEO-0c observation and coverage gates remain
upstream of selection. Existing `declared_ranks` and
`deepest_observed_line` tests remain green.

The v2 recipe binds the new selector explicitly in both perspective documents.
Its new meaning expression, plan, JSON/Markdown table, provenance, and producer
live only under `geo-1c-reception-between-lines`; the complete GEO-1 artifact
family is byte-untouched.

## Certified result and second substrate finding

| Measure | Value |
|---|---:|
| Evaluated receptions | 4,189 |
| PASS | 0 |
| FAIL | 0 |
| UNKNOWN | 4,189 |
| `entity_relative_bracketing_not_observed` | 2,909 |
| `entity_frame_missing` | 1,280 |
| Plan hash | `39c3ae0d9780995a52b2ffc3bca464d584cd634ce6983e1a0ce91ae491ab91e5` |
| Table hash | `ace4177fe3403efe1fbefd8313c36422635a0f4ffdf75ca5b91f53a94f5d3460` |

This is not the old structural zero: the selector contract is now correct and
the primitive refuses negative evidence. The upstream `multi_line_model`
collection still constructs only goal-side-of-ball bands. At reception the
receiver is at the ball, so it supplies no ball-side/goal-side adjacent pair
for all 2,909 controlled receptions with known entity frames. A1 therefore
reveals a second, upstream observation-scope limitation. The producer did not
invent a ball-side band, convert absence to FAIL, or claim a rate from an empty
observed denominator. The committed producer reproduced all artifacts byte for
byte on a second full seven-match execution.

## Ratchet acknowledgments

- Vocabulary census: `tests.test_scp2_1_meaning_to_target` remains **39** by
  explicit version-replacement law.
- Typed-field catalog census: `tests.test_geo0b_typed_field_references` retains
  its field-reference count; no reference was added or removed.
- Runtime binding subject moved by name to
  `binding.primitive.between_observed_lines.0_2_0`.
- Exposure subject moved by name to
  `exposure.runtime.between_observed_lines.0_2_0`.
- Maturity subject moved by name to
  `maturity.runtime.between_observed_lines.0_2_0`.
- SCP-0 regenerated the capability catalog, context, knowledge pack, runtime
  manifest, all six semantic projections, parity report, passport, and lock.
  `tests.test_scp0_semantic_registry` passed 58/58.

## Verification table

| Check | Result |
|---|---|
| GEO-1/GEO-1c geometry and honesty | PASS — 16/16 |
| SCP-0 registry generation | PASS |
| SCP-0 registry tests | PASS — 58/58 |
| V2 producer generation | PASS — 4,189 rows |
| V2 producer `--check` | PASS — byte-identical |
| GEO-1 v1 evidence overwrite audit | PASS — no changed path under `geo-1-reception-between-lines` |
| Full suite | PENDING |
