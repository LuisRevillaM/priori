# Learning: Temporal Absence Is Not Necessarily Failure

The S3R3 review identified an important distinction for agent-authored tactical plans: a missing qualifying persistence episode can mean definitive FAIL or indeterminate UNKNOWN.

The runtime now treats temporal predicates as explicit PASS, UNKNOWN, and FAIL intervals. UNKNOWN covers windows where missing evidence could have completed the duration requirement, and target tracing returns UNKNOWN outside evaluated coverage.

Typed duration values must be normalized before execution. Accepting seconds, milliseconds, and frames while interpreting every value as seconds is worse than rejecting units outright.

