# Known Gaps

## not_in_scope: S4 is not implemented

This packet only addresses the corrective gate required before S4. It does not implement rule-driven result emission.

## not_in_scope: UI/demo work is not covered

No visual interface, animations, or demo UX are validated by this packet.

## requires_full_repo: validation commands are not independently runnable

The packet is inspection-only. The external reviewer can inspect source, diffs, configs, schemas, docs, and reports, but cannot rerun the `make` targets without the full repository and environment.

## not_in_scope: legacy M1 compatibility code remains

Some functions and fields with `wide_entry_*` and related M1 concepts still exist in `source-files/executor.py` for parity and compatibility. S3R does not claim all M1 code was removed. It claims generic anchor discovery, target inspection, and temporal predicate paths no longer depend on those assumptions.

## unknown: external approval

The controller accepted S3R locally, but this packet exists because external approval has not yet been received for the delta.

