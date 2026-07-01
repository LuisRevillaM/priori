# Learning: Agent-Facing Contracts Need Host-Owned Boundaries

S7R fixed relation coverage, but S7R2 exposed the agent-facing version of the same problem: a correct internal path is not enough if Hermes can author a nearby unsafe path.

The final correction narrowed what the agent can bind:

- relation existence must use anchor-indexed coverage, not raw relation episode lists;
- witnesses must be scoped to the evidence source;
- self-declared complexity limits are only requests and cannot exceed host-owned ceilings;
- mixed missing evidence is `UNKNOWN` unless the relation is already proven.

This is the right stopping point for runtime refinement. The next milestone should use these contracts through Hermes rather than continue abstract runtime work in isolation.
