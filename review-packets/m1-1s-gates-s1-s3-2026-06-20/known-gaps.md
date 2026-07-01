# Known Gaps

## S4 Rule-Driven Result Emission

Classification rules still do not fully own result emission.

- class: `not_in_scope`
- why it matters: external rejection asked for plan-controlled execution, and S4 is the next major proof.
- boundary: do not claim final M1.1S architecture acceptance from S1-S3.
- next action: implement S4.

## S5 Alias-Based Evidence Projection

Evidence projection is not yet fully alias-based.

- class: `not_in_scope`
- why it matters: public result shape should not depend on node IDs or flat M1 dictionaries.
- boundary: do not claim stable public evidence API.
- next action: implement S5.

## M1 Compatibility Side Channel Remains

`signed_lateral_shift` still writes `state.candidates` as a compatibility side effect.

- class: `known_gap`
- why it matters: S3 moved generic target evaluation and traces off this side channel, but the side channel still exists for later parity support.
- boundary: acceptable only if S4-S7 continue removing generic dependence on it.
- next action: ensure final architecture proof prevents generic execution from depending on it.

## Packet Is Not Reproducible Alone

The packet does not include raw/canonical tracking data, virtualenv, or full source tree.

- class: `requires_full_repo`
- why it matters: reviewer cannot independently rerun validation commands.
- boundary: reviewer should inspect evidence and request more source if needed.
- next action: create a full reproducible package only if explicitly required.
