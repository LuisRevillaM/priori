# Learning: Compatibility Must Be Host-Selected, Not Shape-Detected

S3R2 named the legacy adapters but still selected them from runtime-record shape. That was not enough: a generic plan could accidentally enter legacy behavior if its records looked similar.

The correction is to make compatibility a host-selected profile:

- generic profile: no legacy adapters and no legacy trace fallback;
- legacy M1 parity profile: adapters allowed for frozen oracle compatibility.

Temporal predicates also need a single implementation. Tests must call the same function runtime calls, and temporal output must preserve UNKNOWN intervals so later classification and target inspection do not collapse unknown into failure.

