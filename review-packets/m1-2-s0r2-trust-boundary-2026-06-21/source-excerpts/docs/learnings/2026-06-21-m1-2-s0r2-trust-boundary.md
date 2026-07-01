# M1.2 S0R2 Trust Boundary Learning

Date: 2026-06-21

Fact: A typed tool API is still unsafe if the model can choose caller privileges,
execution authorization, recipe status, local paths, or handles that map directly
to filesystem locations.

Decision: M1.2 treats Hermes as a restricted caller profile. Hermes can submit
experimental plans and consume schema-valid handles, but host code owns
confirmation, compatibility profile selection, approved recipe trust, and replay
artifact resolution.

Learning: The workshop needs two surfaces: a narrow Hermes S2 surface and a
host/manual reference surface. Both call the same dispatcher, but they must not
have identical authority.

Follow-up: Send the S0R2/S1R2 packet for external review before starting Hermes
drafting. If approved, S2 should implement natural-language drafting as a client
of this boundary rather than expanding the runtime.
