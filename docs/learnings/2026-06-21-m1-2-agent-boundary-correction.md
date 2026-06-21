# M1.2 Agent Boundary Correction Learning

Date: 2026-06-21

Fact: Trusted local Python functions are not automatically safe agent tools.
Hermes-facing APIs need concrete schemas, opaque handles, immutable execution
records, and host-selected runtime behavior.

Decision: M1.2 S2 may only use the serialized `dispatch_tool` boundary and the
generated capability context. Hermes must not supply local paths, choose
compatibility profiles, inspect by re-executing a plan, or receive raw coordinate
dumps.

Learning: The manual reference workshop is only meaningful if it calls the exact
same serialized tool boundary future Hermes calls. Verifiers may inspect records,
but the primary workflow must prove submit -> validate -> execute -> inspect ->
replay through handles.

Follow-up: Regenerate the external review packet from a clean committed S0R/S1R
state before starting Hermes S2.

