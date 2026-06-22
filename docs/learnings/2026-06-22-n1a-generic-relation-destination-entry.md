# N1A Generic Relation-Destination Entry

Type: implementation learning

Fact: The failed N1 preflight was a catalog contract defect, not a Hermes failure. The catalog exposed `relation_destination_entry_classification` as agent-authorable even though its implementation assumed an upstream M1-style `classification` field.

Decision: Split the reusable measurement from the recipe wrapper. `relation_destination_entry` is now the Hermes-authorable generic capability and emits relation-scoped `entry_status` values with PASS/FAIL/UNKNOWN semantics. `relation_destination_entry_classification` remains available for existing trusted recipes but is no longer agent-authorable.

Learning: Agent-composable capabilities need names and outputs that describe measured geometry, not recipe interpretation. If a capability requires upstream tactical labels, it is a macro or wrapper and should stay recipe-only until the dependency is explicit.

Evidence: `PYTHONPATH=src .venv/bin/python -m tqe.verification.n1a` passes 8/0, returning 5 real generic rows for the frozen hero candidate. The candidate fingerprint `79b852cd4f392e1ab5dbcb0e12fd516ee9d678c71da26e5e90c6fc3e510bc0a0` differs from registered recipe fingerprints, and S4/S6/S7R plus the runtime unit suite remain green.

Follow-up: Run the live Hermes N1 proof once against the refreshed freeze. Do not tune prompts, aliases, or model instructions after observing the live result.
