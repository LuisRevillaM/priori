# F2-2 Report — Pass-Family Extraction

Branch: `packet/f2-2`
Protocol: local commit only; no push.

## Scope outcome

- Moved the pass-family implementations from `src/tqe/runtime/executor.py` to `src/tqe/runtime/capabilities/pass_family.py` as pure relocation.
- Relocated functions:
  - `primitive_action_event_anchor`
  - `primitive_controlled_pass_episode`
  - `primitive_one_touch_relay_episode`
  - `relation_opponents_bypassed_by_action`
- Relocated pass-only helpers:
  - `controlled_pass_anchor_record`
  - `controlled_pass_episode_record`
  - `one_touch_relay_anchor_record`
  - `pass_bypass_anchor_record`
- `primitive_action_event_anchor` moved because its current catalog-supported modes are pass-family coupled: `successful_pass` and `throw_in_successful_pass`. No non-pass action anchor mode is implemented in the function body.
- The dispatch registry in `src/tqe/runtime/capabilities/__init__.py` now resolves those four implementations lazily from `tqe.runtime.capabilities.pass_family`. `executor.py` does not import `pass_family`.
- No catalog contracts, generated artifacts, frozen expectations, N1D artifacts, or runtime semantics were changed.

## Line count

| File | Before | After | Delta |
|---|---:|---:|---:|
| `src/tqe/runtime/executor.py` | 10,999 | 10,589 | -410 |
| `src/tqe/runtime/capabilities/pass_family.py` | 0 | 451 | +451 |

## Shared helpers retained in `executor.py`

These are used by the relocated pass-family functions but remain in `executor.py` because they are shared runtime/kernel helpers or are used by other capability families too. They are director input for later shared-kernel extraction; F2-2 did not improve or relocate them.

| Helper / symbol | Why it stayed |
|---|---|
| `PeriodState` | Shared executor state type used by all capability implementations. |
| `anchor_record_id` | Generic deterministic anchor identity helper. |
| `catalog_input_value` | Generic bound-input resolver. |
| `catalog_output` | Generic catalog output metadata resolver. |
| `frame_match_time_ms` | Generic frame timestamp helper. |
| `node_parameter_event_type_filter` | Generic node-parameter helper for event filter parameters. |
| `node_parameter_number` | Generic node-parameter helper. |
| `node_parameter_text` | Generic node-parameter helper. |
| `optional_int` | Generic coercion helper used outside pass family. |
| `parquet_rows` | Generic runtime data-load helper. |
| `point_from_xy` | Generic point construction helper used by other families. |
| `align_event_to_frame` import in `executor.py` | Still used by `set_piece_structure`; not pass-family-only. |
| `EVENT_COLUMNS` import in `executor.py` | Still used by `set_piece_structure`; not pass-family-only. |
| `attack_x_sign_for` import in `executor.py` | Used by multiple non-pass families; not pass-family-only. |

## Improvement candidates not implemented

Pure relocation only. These were observed but deliberately deferred:

- Extract the generic executor helper/kernel symbols above into stable shared modules so capability modules no longer import shared helpers from `executor.py`.
- Move `primitive_pass_chain_episode` and `primitive_receiver_line_transition_during_pass_leg` in a later pass-family packet if the director wants the full pass family extracted, not just this packet's named slice.
- Split `action_event_anchor` into generic event anchoring plus pass-specific parsing if future non-pass action anchors land.
- Add a stricter no-executor-import target for capability modules after the shared-kernel extraction exists.

## Boundary guard updates

- Added a test that `executor.py` does not import or mention `pass_family`.
- Added a registry reachability assertion that `action_event_anchor`, `controlled_pass_episode`, `one_touch_relay_episode`, and `opponents_bypassed_by_action` resolve to `tqe.runtime.capabilities.pass_family` through the registry.
- Extended the node-parameter declaration guard so it scans both `executor.py` and `capabilities/pass_family.py` implementation bodies.

## Pinned-gate drift proof

To be filled after committed-tree verification.

## Full-suite table

To be filled after committed-tree verification.
