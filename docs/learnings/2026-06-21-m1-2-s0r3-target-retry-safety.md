# M1.2 S0R3 Target And Retry Safety Learning

Date: 2026-06-21

Fact: Structural inspection and coordinate replay are one user-facing claim. If
they resolve target time independently, the system can explain one moment while
the human watches another.

Decision: M1.2 uses one resolved target contract for target inspection and replay
retrieval. The resolved frame is included in inspection output and must match the
replay anchor frame.

Learning: Immutable content-addressed records still need idempotent retry
semantics. Agent retries should return the existing resource when canonical
payloads match, and fail only when the same handle maps to conflicting content.

Follow-up: S2 Hermes drafting should remain a client of this resolved-target and
retry-safe model-visible boundary. Do not add runtime architecture work during
S2 unless this boundary reveals a concrete regression.
