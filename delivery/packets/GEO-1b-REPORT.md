# GEO-1b — receiver-relative reception between observed lines

Branch: `packet/geo-1b`

Frontier: `7dcd528d231e5ca6f9a543db5f9287883a605352`

Executor clone: `/private/tmp/priori-geo1b-executor` (outside the repository
tree)

Status: **STOPPED BEFORE IMPLEMENTATION — RECIPE CONTRACT CANNOT EXPRESS A1**

## Amendment and preserved evidence

ADR 0018 Amendment A1 requires the reception recipe to select the adjacent
observed opposing-line pair bracketing the receiver at the controlled-reception
frame. The original GEO-1 definition and its 0/2,909 PASS certified table are
unchanged and remain the proof that ball-relative ranks 1/2 are structurally
wrong for this composition.

No old plan, table, generator, primitive, catalog entry, registry entry, or
generated artifact was modified in this attempt.

## Pre-implementation expressibility audit

The merged `between_observed_lines@0.1.0` runtime contract cannot currently
express A1:

1. `line_selector` permits only `declared_ranks` and
   `deepest_observed_line`.
2. `nearer_line_rank` and `farther_line_rank` are scalar numeric plan
   parameters. They cannot be selected from each receiver record.
3. `_select_lines` chooses the declared nearer rank before examining entity
   position; neither selector computes the adjacent pair around the entity.
4. The runtime adapter passes one fixed `BetweenObservedLinesConfig` to every
   anchor record in the invocation.
5. The registered composition operators have no tri-state union/coalesce/OR
   operation. Multiple fixed-rank invocations therefore cannot be collapsed
   into one same-reception PASS/FAIL/UNKNOWN population for `aggregate_over`
   and `rate`.

`deepest_observed_line` does not repair this: it retains the fixed declared
nearer rank and changes only the farther boundary. A producer-side scan that
chooses a bracketing pair after execution would be an unregistered parallel
implementation and would make the certified table claim semantics absent from
the committed plan. This executor refuses that misreport.

## Required ruling

The smallest coherent correction is to amend the primitive's selector surface
with a registered `receiver_relative_bracketing` (preferably the more general
`entity_relative_bracketing`) selector. The kernel already receives normalized
entity X and the complete observed-line collection, so it can select the
unique adjacent pair with one line ball-side and one goal-side, preserve GEO-0c
tri-state coverage, apply the existing boundary buffer, and emit both selected
line identities. The recipe would then bind that selector explicitly; a
ball-anchored recipe would bind an explicit ball-relative selector as A1
requires.

That is a primitive contract amendment, which the packet explicitly forbids.
The alternative is a new registered per-anchor bracketing/tri-state-coalesce
composition operator, also outside recipe-only scope and materially larger.

Until one of those surfaces is authorized, there is no honest new plan or
certified table to generate. The census ratchet remains 116 on the frontier;
this attempt adds no vocabulary item.

## Verification table

| Check | Result |
|---|---|
| A1 text and GEO-1 finding reviewed | PASS |
| Existing zero-PASS artifacts byte-untouched | PASS |
| Primitive selector inventory | FAIL for A1 expressibility — two static selectors only |
| Registered operator inventory | FAIL for recipe-only workaround — no tri-state union/coalesce |
| New plan/table/generator | NOT RUN — producing them would misreport the committed plan |
| Full suite | NOT RUN — no implementation was authorized past the expressibility STOP |

