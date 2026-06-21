# M1.2 S0/S1 Manual Workshop Learning

Date: 2026-06-20

Fact: The manual workshop must execute each canonical plan once and reuse the
result execution for traces and replay generation. Re-executing per result makes
the gate too slow and obscures real failures behind avoidable runtime cost.

Decision: Keep the S0 boundary stricter than the internal runtime catalog.
`exists` and `count_at_least` remain internal operators, but the workshop and
future Hermes context expose them only for `anchor_evaluations` until broader
collection semantics are deliberately designed and tested.

Learning: Human tactical inspection needs coordinate replay even before UI
polish. A static replay artifact plus predicate traces is enough for S1; the
final delightful interface should build on this evidence path rather than create
a separate visualization path.

Follow-up: Do not start Hermes S2 until the S0/S1 packet is externally reviewed.
If approved, Hermes should call the same validation, execution, inspection,
replay, feedback, and recipe tools rather than receive direct runtime or raw data
access.

