# F2-4 Report — Lines Family Extraction

Branch: `packet/f2-4`
Protocol: local commit only; no push. The executor run was externally interrupted
after the code commit and before this report was written.

## Scope outcome

- Moved the observed-line implementations from `src/tqe/runtime/executor.py` to
  `src/tqe/runtime/capabilities/lines_family.py` as pure relocation.
- Relocated node implementations:
  - `primitive_defensive_line_model`
  - `primitive_multi_line_model`
  - `primitive_relative_position_to_line`
  - `primitive_receiver_line_transition_during_pass_leg`
  - `primitive_controlled_line_break_episode`
- Registry mapping preserved:
  - `defensive_line_model` resolves to `primitive_defensive_line_model`.
  - `multi_line_model` resolves to `primitive_multi_line_model`.
  - `relative_position_to_line` resolves to `primitive_relative_position_to_line`.
  - `receiver_line_transition_during_pass_leg` resolves to
    `primitive_receiver_line_transition_during_pass_leg`.
  - `controlled_line_break_episode` resolves to
    `primitive_controlled_line_break_episode`.
- Relocated line-only helpers:
  - `multi_line_anchor_record`
  - `multi_line_payload_from_anchor`
  - `defensive_line_anchor_record`
  - `relative_position_to_line_anchor_record`
  - `receiver_line_transition_anchor_record`
  - `controlled_line_break_anchor_record`
  - `record_by_anchor_id`
- Shared cached-position helpers stayed in `executor.py`; they are used by
  non-line families and belong to a later shared-kernel extraction, not F2-4.
- No catalog contracts, generated artifacts, frozen expectations, N1D artifacts,
  or runtime semantics were changed.

## Line count

| File | Before | After | Delta |
|---|---:|---:|---:|
| `src/tqe/runtime/executor.py` | 9,884 | 9,183 | -701 |
| `src/tqe/runtime/capabilities/lines_family.py` | 0 | 708 | +708 |

## Verification note

The executor run was interrupted before it could write this report. The project
director ran acceptance verification independently and merged F2-4 at
`a9b4dcd` (`Merge packet/f2-4: lines family extraction (F2-4 accepted)`).
This backfill records the accepted scope and line counts; F2-5 reruns the full
pinned-gate and suite table on top of the accepted frontier.
