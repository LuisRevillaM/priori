# R1-0 Report - Operator Scaffolding

Branch: `packet/r1-0`
Frontier base: `48175df`
Packet: `delivery/packets/R1-0-operator-scaffolding.md`
ADR: `docs/adr/0013-r1-operator-era.md`
Push: no push, per direct-channel protocol.

## Scope

Pure scaffolding for the R1 operator era:

- additive operator node kind in IR;
- empty operator signature registry with ratchets armed;
- binder validation and fail-closed `operator_not_implemented` behavior;
- executor dispatch shell only, unreachable while registry is empty;
- boundary ratchets extended by absence checks for named R1 operators;
- hash-invariance proof for existing plans;
- composition-space census for R1-1 through R1-5.

Required constraints: zero behavior change and zero hash drift for existing
plans. Fenced directories stayed untouched: `semantic-registry/`,
`generated/`, `frozen-expectations/`, `delivery/n1d/`, and `artifacts/`.

## Implementation Ledger

| Step | Status | Evidence |
| --- | --- | --- |
| L1 report first commit | PASS | First packet commit: `c4e1db5 Start R1-0 operator scaffolding report`. |
| IR/operator model | PASS | Added `NodeKind.OPERATOR`, draft/bound operator node models, operator input/output declarations, and `CompositionOperatorSignature`. |
| Empty registry and ratchets | PASS | Added `src/tqe/runtime/operators/__init__.py`; `OPERATOR_SIGNATURES` and `OPERATOR_IMPLEMENTATION_NAMES` are empty tuples. |
| Binder scaffolding | PASS | Operator nodes validate against injected signatures, then fail closed with `operator_not_implemented` when the registry has no implementation. |
| Executor scaffolding | PASS | Executor builds an empty operator registry and contains only a defensive dispatch shell for `BoundOperatorNode`. |
| Envelope model | PASS | Added additive `OperatorEnvelope`; unused by existing runtime paths. |
| Boundary ratchets | PASS | `tests/test_r1_0_operator_scaffolding.py` asserts distinctive R1 operator names are absent from shared binder/executor code. |
| Composition-space census | PASS | Catalog census below: 44 capabilities, 108 output channels. |
| Hash invariance | PASS | Existing `ball_side_block_shift` plan hash and bound-plan hash unchanged under focused test. |

Scaffolding commit: `92625d6 Scaffold empty composition operator registry`.

## Composition-Space Census

The census is a channel-shape map only. It does not approve operator semantics
or authorize composition behavior; each later R1 packet still needs explicit
contracts, implementation, and verification.

Runtime catalog at this commit:

| Count | Value |
| --- | ---: |
| Capabilities | 44 |
| Primitives | 37 |
| Relations | 7 |
| Output channels | 108 |
| Outputs with coverage declaration | 36 |

Output-channel shape:

| Dimension | Counts |
| --- | --- |
| Temporal | `episode_set=43`, `frame_signal=63`, `relation_episode_set=2` |
| Payload | `anchor_ref=38`, `boolean=5`, `enum=44`, `number=18`, `point=1`, `relation_ref=2` |
| Cardinality | `collection=45`, `per_team=1`, `single=62` |

R1 operator space:

| Packet | Operator | Eligible current channels | Coverage-declared subset | Notes |
| --- | --- | ---: | ---: | --- |
| R1-1 | `typed_join` | 45 | 36 | Collection episode/relation channels with identity-like evidence fields. Candidate space only; join keys and coverage must be declared later. |
| R1-2 | `extremum_over_set` | 46 | 36 | Collection/per-entity outputs. Coverage-qualified extrema are the safer initial surface. |
| R1-3 | `window` | 108 | 36 | All current outputs are time-indexed as frame signals or episode/relation sets. Later packet must define window closure and UNKNOWN behavior. |
| R1-4 | `project_onto_axis` | 16 | 9 | Point-like payload/evidence channels; only one direct `point` payload exists today. |
| R1-5 | `delta_across_anchor` | 63 | 0 | Frame-signal outputs only. No current frame-signal channel carries coverage declaration, so coverage must be supplied by the operator contract or input evidence. |

Example channels observed in the census include `possession_segment.episodes`,
`controlled_pass_episode.episodes`, `carry_episode.episodes`,
`space_region_generation.representative_open_space_point`,
`transition_anchor.transition_status`, and
`outcome_window.outcome_window_status`.

## Hash Invariance

Focused proof:

```text
PYTHONPATH=src .venv/bin/python -m unittest tests.test_r1_0_operator_scaffolding
```

Result: PASS, 6 tests.

The existing `config/query-plans/ball_side_block_shift.ir.v1.json` hashes
remained:

| Hash | Value |
| --- | --- |
| `plan_hash` | `6ffa2ed7df43e999183f1b9135f0d64382dd01b00f044394a67ebccdd6c647c9` |
| `bound_plan_hash` | `4a5a1dabc168ffcc511923700ddb28af67393fb13c7caccd7b92689289d8b4ce` |

No existing query plan was edited.

## Verification

Targeted checks:

| Command | Status | Notes |
| --- | --- | --- |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_r1_0_operator_scaffolding` | PASS | 6 tests; empty registry, fail-closed binder behavior, injected-signature validation, operator-name absence, hash invariance. |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_executor_boundaries` | PASS | 14 tests. |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_m1_1_binder` | FAIL | 1 expected disclosure: `test_generated_artifacts_are_current`; additive IR schema is not regenerated because `generated/` is fenced. |

Full suite on committed tree:

| Command | Status | Notes |
| --- | --- | --- |
| `make PYTHON=.venv/bin/python test` | FAIL | 377 tests run; 1 failure: `test_generated_artifacts_are_current`. Diff is generated schema/types drift from the additive operator IR. Runtime tests passed. |

Pinned gates on committed tree:

| Gate | Status | Packet attribution |
| --- | --- | --- |
| `n1d1-verify` | PASS | `attestation_status=VERIFIED`, no blocking reasons. |
| `scp-0-verify` | PASS | Report status PASS; registry tests OK. |
| `afl-passport-verify` | PASS | Report status PASS; passport hash matched stored hash; registry tests OK. |
| `afl-lane-occupancy-verify` | PASS | Report status PASS; 20 results; requested evidence failures 0. |
| `afl-line-break-support-response-verify` | FAIL | Pre-existing frontier red. Base `48175df` reproduces same `execution_id=1aec451674d55bf1`, result count 1, result signature `c330d685d65bff2221a8ed920f10d8987d51dfd1f069778298fdd27d584e1ea9`, and `runtime_semantics_dirty_at_freeze`. |
| `afl-09a-verify` | FAIL | Pre-existing frontier red. Base `48175df` reproduces the same two bootstrap factory failures: line-break support response and relative-position-to-line. |
| `afl-substrate-q4-verify` | FAIL | Pre-existing frontier red. Base `48175df` reproduces same `execution_id=53d5687e708d4100`, result count 2, result IDs `3084e9dca2398892`, `e68c82e446eba217`, signature `0a6599a5560eb239d5e8805b7b42e845d6b3403bdc6711f7f02d3c7c70992dbb`, and `runtime_semantics_dirty_at_freeze`. |
| `afl-substrate-q6-verify` | FAIL | Pre-existing frontier red. Base `48175df` reproduces same `execution_id=4d661d30392ba526`, honest-zero count 0, signature `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`, and `runtime_semantics_dirty_at_freeze`. |

Base-state check used a detached worktree at
`/private/tmp/priori-r1-base-20260703` with the same local canonical data
symlinked into that worktree. The red pinned gates therefore are inherited
frontier state, not introduced by this packet.

## File Footprint

Tracked files changed:

- `delivery/packets/R1-0-REPORT.md`
- `src/tqe/runtime/binder.py`
- `src/tqe/runtime/envelope.py`
- `src/tqe/runtime/executor.py`
- `src/tqe/runtime/ir.py`
- `src/tqe/runtime/operators/__init__.py`
- `tests/test_r1_0_operator_scaffolding.py`

Fenced/generated artifacts were not edited or regenerated. The only untracked
file in the shared worktree during this packet was the pre-existing unrelated
`docs/visual-explainers/tactical-compilation-concept.png`; it was not staged.

## Summary

R1-0 scaffolding is additive and fail-closed. The operator registry is empty,
no operator implementation can execute, existing plan hashes are unchanged, and
the composition-space census is recorded for R1-1 through R1-5. The only new
suite failure is generated-artifact currency from the additive IR schema, which
is intentionally not regenerated under the packet fences. Four pinned gates are
red on the packet branch but reproduce on the frontier base with the same
payloads and are disclosed as inherited state.
