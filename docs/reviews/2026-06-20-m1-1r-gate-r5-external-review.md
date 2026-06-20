# M1.1R Gate R5 External Review

Date: 2026-06-20

Decision: `REJECT`

Source attachment: `/Users/luisrevilla/.codex/attachments/0956833a-2d19-4a31-a2c4-cf9b1aba1e6d/pasted-text.txt`

## Controller Interpretation

The rejection is accepted as substantively correct.

R5 preserved and improved useful scaffolding, but it still does not prove the M1.1 product outcome: a composable tactical-query runtime whose orchestration is controlled by the typed plan. The current runtime remains an M1-specific detector pipeline with typed plan metadata layered over it.

M1.2 remains blocked.

## Blocking Themes

- The declared graph is not the actual execution graph because `state.candidates`, `state.accepted`, `state.near_misses`, and M1 result dictionaries still drive execution and result handoff.
- Declared node outputs exist, but downstream nodes still read undeclared raw side channels from `state.signals` and global period context.
- Classification rules filter already-labeled results; they do not emit classifications from predicate satisfaction.
- Requested evidence is projected from flat M1-specific result dictionaries and still leaks node IDs through requested-evidence keys.
- Runtime type conformance can launder M1-shaped dictionaries into declared frame signals rather than failing mismatches.
- `persists_for` still contains block-shift candidate logic and does not preserve UNKNOWN as a first-class temporal value through generic intervalization.
- Relations are still anchored to M1-style terminal result objects rather than a stable generic anchor model.
- Predicate traces and non-match inspection remain tied to candidate dictionaries and specialized M1 paths.
- R5 tests prove weaker properties than their names imply, especially for second-plan results, classification rules, requested evidence, node-ID opacity, and unknown propagation.

## Required Controller Action

Create and execute M1.1S, a structural corrective sub-milestone under M1.1.

Source of truth:

- `delivery/m1.1/STRUCTURAL_CORRECTIVE_SPEC.md`

## Non-Blocking Positives To Preserve

- Canonical data and feature pipeline.
- M1 detector and parity oracle.
- Current IR and binder concepts.
- Parameter schemas.
- Corridor geometry.
- Invocation handling.
- Query hashing/versioning.
- Replay inspector and proof artifacts.

## Boundary

Do not proceed to M1.2 until M1.1S proves that a plan using existing primitives and predicates can produce materially different real results without a Python terminal that understands that query's candidate shape.
