# M1.1S Gate S3R3 External Review

Decision: `APPROVE_WITH_REQUIRED_CHANGES_BEFORE_S4`

The reviewer accepted the S3R3 architecture but kept S4 blocked for a small temporal-correctness patch.

Resolved:

- generic versus legacy compatibility profile selection is mostly resolved;
- one shared generic `persists_for` implementation is resolved;
- non-M1 proof now executes real generic predicate nodes;
- generic traces are independent of identified M1 side channels in code.

Blocking before S4:

- `TacticalQueryExecutor` defaulted to `legacy_m1_parity` instead of fail-closed `generic`;
- duration units were accepted but raw values were interpreted as seconds;
- persistence UNKNOWN was preserved only at missing frames, not across indeterminate windows;
- anchors outside evaluated temporal coverage could become FAIL;
- the side-channel proof did not actually perturb `state.predicate_traces`.

Required correction:

Create S3R4 so generic execution is the default, durations normalize to frame counts from typed units, persistence preserves PASS/FAIL/UNKNOWN semantics across windows and coverage, and the proof perturbs predicate-trace side channels.

