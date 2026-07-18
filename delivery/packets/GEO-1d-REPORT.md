# GEO-1d — all-line observation scope and flagship certification

Branch: `packet/geo-1d`

Frontier: `0e291003`

Executor clone: `/private/tmp/priori-geo1d-executor`

Status: **IMPLEMENTED — STOP AUDIT CLEAR — VERIFIED**

## Contract amendment

`multi_line_model` advances from `0.1.0` to `0.2.0`. Its default collection
scope becomes `all_opposing_lines`: every adequately observed opposing
outfielder may contribute to geometric line-band construction regardless of
ball position. `goal_side_buffer_m` remains meaningful only when the explicit
`line_collection_scope=goal_side_of_ball` compatibility scope is selected.
Rank is normalized longitudinal order, never a tactical role.

GEO-0c remains the truth gate: uncertified, insufficient, or ambiguous defender
observation forces UNKNOWN before absence can testify; adequately observed
absence of a requested band may FAIL. Each emitted band still requires the
declared minimum membership and exposes its identity and members.

## Consumer disposition inventory

| Consumer | Prior semantic dependency | Disposition |
|---|---|---|
| Q3 `second_line_at_release` | Declared goal-side rank 2 | Bind `goal_side_of_ball` explicitly and version `0.2.0`; certified value STOP applies |
| Q6 `first_line_at_release` | Declared goal-side rank 1 | Bind `goal_side_of_ball` explicitly and version `0.2.0`; certified value STOP applies |
| GEO-1 v1 recipe/artifacts | Historical ball-relative finding | Immutable evidence; never rerun or edit |
| GEO-1c v2 recipe/artifacts | Entity-relative selector over all observed bands, but inherited old default | Immutable evidence; GEO-1d regenerates a new artifact family from the unchanged meaning/recipe law with explicit `all_opposing_lines` and version `0.2.0` |
| `between_observed_lines` | Consumes supplied bands | No code/default change; its selector remains explicit |
| Compiler reachability/search targets | Catalog-discovered provider | Regenerate projections; no hand-authored goal-side claim added |
| Direct kernel/catalog tests | Observation primitive contract | Update to assert all-band default and explicit legacy scope |

No other executable query plan binds `multi_line_model`. Coverage-map prose,
counsel, reviews, and prior certified reports are historical/non-executable and
remain untouched.

## Named ratchets

- `binding.primitive.multi_line_model.0_1_0` → `.0_2_0`;
- `exposure.runtime.multi_line_model.0_1_0` → `.0_2_0`;
- `maturity.runtime.multi_line_model.0_1_0` → `.0_2_0`;
- Q3 plan/bound-plan/frozen expectation identity (value must not move);
- Q6 plan/bound-plan/frozen expectation identity (value must not move);
- capability catalog/context, tactical knowledge pack, runtime manifest,
  capability passport, AI/product/recipe/atlas/unsupported projections,
  semantic parity report, and registry lock;
- GEO-0b typed-field catalog census; and
- SCP2 vocabulary census, expected to remain 39 because this is a version
  replacement rather than a new primitive name.

Any existing certified tactical-value delta is a STOP. Identity/hash movement
caused solely by explicit version and scope bindings will be named, never
presented as a value delta.

## Implementation and compatibility result

`multi_line_model@0.2.0` now defaults to `all_opposing_lines`. It constructs
bands from every adequately observed opposing outfielder in attacking-direction
normalized coordinates; ball position is not a collection gate. The explicit
`goal_side_of_ball` scope preserves the removed analysis assumption for plans
that actually declared it. GEO-0c's coverage and minimum-membership gates remain
ahead of absence-to-FAIL, and every emitted band keeps its identity and member
ledger.

Q3 and Q6 are the complete executable legacy-scope consumer inventory. Both
now bind `goal_side_of_ball` and `multi_line_model@0.2.0` explicitly in their
source producers and tracked plan artifacts. No other executable plan binds the
primitive. Historical GEO-1, GEO-1b, and GEO-1c tables were not modified.

## Certified flagship result

The GEO-1c recipe law is unchanged: controlled receptions feed
`between_observed_lines` with `entity_relative_bracketing`, aggregate by
`receiver_id`, and expose unknown-bounded rates. Its new v3 plan changes only
the line provider binding to `multi_line_model@0.2.0` with
`line_collection_scope=all_opposing_lines`.

| Measure | Certified result |
|---|---:|
| Controlled-reception population | 4,189 |
| PASS between an observed adjacent pair | 121 |
| FAIL outside/minimum gap | 0 |
| UNKNOWN | 4,068 |
| Honest rate interval | 0.032588–1.000000 |
| Period/team rows | 28 |

Plan hash: `1ff9a08fdfbe8f9e1b3046ff3b004ada58634b39489dfcf23c7c6789ee2642c0`.
Certified-table hash: `b2b54bdcb1d517293002f2d2c73542be5bf00236f5c45df43088cace56e5c663`.
The committed generator reproduced both byte-for-byte. The wide upper bound is
the honest consequence of 4,068 UNKNOWN rows; it is not collapsed into a point
estimate.

## Certified-delta STOP audit

No certified tactical value changed for an existing consumer.

| Consumer | Before / after | Disposition |
|---|---|---|
| Q3 | 13 results; probe line statuses PASS 142 / FAIL 106, unchanged | CLEAR; result IDs/signature and plan hashes moved solely because the provider contract identity is now explicit |
| Q6 | 0 results; probe line-transition statuses PASS 1 / FAIL 13 / UNKNOWN 3, unchanged | CLEAR; plan hashes moved solely because the provider contract identity is now explicit |

The validation factories were renewed only through their committed freeze mode
after the plan artifacts were regenerated on a clean runtime-semantic tree.
Subsequent ordinary read-compare runs PASS for Q3 and Q6. This is the named
contract ratchet, not a silent re-certification.

## Ratchet acknowledgments

- `binding.primitive.multi_line_model.0_1_0` became
  `binding.primitive.multi_line_model.0_2_0`.
- `exposure.runtime.multi_line_model.0_1_0` became
  `exposure.runtime.multi_line_model.0_2_0`.
- `maturity.runtime.multi_line_model.0_1_0` became
  `maturity.runtime.multi_line_model.0_2_0`.
- Q3's bound-plan, document, result-ID, result-signature, and frozen-expectation
  identities moved by name; its 13 certified rows did not.
- Q6's bound-plan, document, and frozen-expectation identities moved by name;
  its certified honest zero did not.
- The GEO-0b typed-field census remains 118
  (`frame=43`, `entity=36`, `status=27`, `provenance=7`, `point=5`).
- The SCP2 vocabulary census remains 39.
- Catalog/context, knowledge-pack, runtime-manifest, semantic projections,
  parity report, passport, registry lock, and SCP-0 evidence were regenerated.

## Verification

| Check | Result |
|---|---|
| GEO-1d generator byte reproduction | PASS — 4,189/4,189; matching plan/table hashes |
| Q3 frozen read-compare | PASS — 13 results, no evidence failures |
| Q6 frozen read-compare | PASS — honest zero, no evidence failures |
| Focused GEO-0c/GEO-1 and ratchet tests | PASS (included in full discovery) |
| Full `unittest discover` | PENDING FINAL RUN |

No registry additions, tactical role names, or legal-offside claims were
introduced. No memory path changed, so the 2 GiB sealed law is not triggered.
