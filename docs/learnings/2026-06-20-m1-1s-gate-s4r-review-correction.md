# Learning: Keep Uncertainty Visible Even When It Suppresses Results

The first S4 implementation correctly emitted generic rows, but the external review caught a subtle failure mode: when uncertainty prevented a result, the trace evidence could disappear too. That made `INVALIDATE_EXECUTION` impossible to enforce end to end.

Two implementation lessons matter for future agents:

- Result filtering must not erase anchor-level UNKNOWN evidence needed by execution-level policy.
- Legacy trace sidecars may remain authoritative only inside the explicit `legacy_m1_parity` path; generic execution must derive traces from declared runtime outputs and explicit predicate records.

Classification conflict semantics also need to be a real contract. The current rule behavior is now specificity first, plan order second. Lexical label order must never become tactical meaning.
