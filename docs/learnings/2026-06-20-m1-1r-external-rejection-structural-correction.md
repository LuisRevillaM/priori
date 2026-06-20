# M1.1R External Rejection And Structural Correction

Date: 2026-06-20

## Fact

External review rejected M1.1R Gate R5. The reviewer accepted that R5 improved binder, parameter, invocation, relation, parity, and proof discipline, but found that the typed plan still does not control execution.

## Decision

M1.2 remains blocked. The next corrective milestone is M1.1S, focused on the execution handoff itself: declared outputs, typed anchors, rule-driven result emission, alias-based evidence projection, trace propagation, and generic non-match evaluation.

## Learning

Node metadata and metamorphic tests are insufficient if the runtime still moves semantic state through M1-specific dictionaries. The proof must show that a second non-block-shift plan can emit real results without `state.candidates`, `state.accepted`, block-shift sorting fields, or terminal Python classification.

## Evidence

- External review source: `/Users/luisrevilla/.codex/attachments/0956833a-2d19-4a31-a2c4-cf9b1aba1e6d/pasted-text.txt`
- Review record: `docs/reviews/2026-06-20-m1-1r-gate-r5-external-review.md`
- Structural corrective spec: `delivery/m1.1/STRUCTURAL_CORRECTIVE_SPEC.md`

## Follow-Up

Implement M1.1S gates S0-S7. Do not begin M1.2 until M1.1S is externally approved or required changes are integrated and re-reviewed.
