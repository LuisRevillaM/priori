# M1.1S Gate S3R External Review

Decision: `REJECT_KEEP_S4_BLOCKED`

The external reviewer accepted the direction of S3R but rejected it as insufficient before S4.

Blocking findings:

- anchor identity was still producer-controlled because runtime discovery trusted supplied `anchor_id` values;
- `NodeExecutionResult` was still a post-execution report rather than an execution boundary;
- `persists_for` still had hidden record-backed semantics under the generic operator name;
- non-M1 target/trace proof only demonstrated graceful `UNKNOWN`, not real PASS/FAIL traces;
- list-backed frame signals without frame IDs could still invent synthetic temporal identity.

Required corrective proof set:

- semantic duplicate anchors with conflicting supplied IDs canonicalize/deduplicate;
- invalid producer anchor IDs fail at the typed output boundary;
- generic predicate execution receives resolved inputs and parameters directly;
- generic `persists_for` has one Boolean frame-signal path and does not inspect records;
- non-M1 target inspection can produce engine-derived PASS and FAIL traces from declared runtime outputs;
- unknown frames split persistence intervals;
- side-channel perturbation does not change generic anchor discovery or target evaluation;
- full M1 parity remains behind explicitly named legacy adapters.

Controller action: accepted as blocking, strengthened S3R instead of starting S4.

