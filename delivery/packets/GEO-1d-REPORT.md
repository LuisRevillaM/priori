# GEO-1d — all-line observation scope and flagship certification

Branch: `packet/geo-1d`

Frontier: `0e291003`

Executor clone: `/private/tmp/priori-geo1d-executor`

Status: **DESIGN SEALED — IMPLEMENTATION IN PROGRESS**

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

