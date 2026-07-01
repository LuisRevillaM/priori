# M1.1S Gate S3R2 External Review

Decision: `APPROVE_WITH_REQUIRED_CHANGES_BEFORE_S4`

The reviewer accepted the S3R2 direction but kept S4 blocked pending a focused S3R3 correction.

Resolved:

- explicit anchor source;
- canonical anchor identity;
- invalid anchor-ID rejection;
- strict frame alignment;
- declared-output trace foundation.

Blocking before S4:

- legacy compatibility was still selected implicitly from runtime-record shape;
- `persists_for` had two generic implementations, one used by runtime and one by tests;
- unknown intervals split persistence but were later erased into episode absence;
- the non-M1 trace proof injected final predicate outputs instead of executing predicate nodes;
- generic target tracing could still fall back to `_runtime_result` and `_predicate_status` sidecars.

Required correction:

Create S3R3 with explicit generic vs legacy compatibility profiles, one shared temporal implementation, UNKNOWN-preserving temporal output, actual-node non-M1 PASS/FAIL/UNKNOWN proof, and generic target trace independence from legacy side channels.

