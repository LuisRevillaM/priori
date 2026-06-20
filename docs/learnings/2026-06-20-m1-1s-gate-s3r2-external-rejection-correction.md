# Learning: S3R Needed Runtime-Enforced Semantics, Not Only Better Shapes

The rejected S3R packet exposed a useful pattern: describing a generic runtime contract is not enough if execution can still succeed through hidden record conventions.

Corrections that should carry forward:

- semantic IDs must be recomputed or centrally generated at runtime boundaries;
- generic operators should have one semantic path, with compatibility behavior isolated behind named adapters;
- target inspection proofs need real PASS and FAIL traces, not only graceful UNKNOWN traces;
- explicit execution results are not sufficient unless implementation receives resolved inputs and parameters directly;
- multi-valued frame signals must never invent frame identity.

For future gates, verifier fixtures should include adversarial inputs that violate the intended architecture while still looking schema-valid.

