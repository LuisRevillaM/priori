# N1 Post-N1B Live Proof

Type: proof learning

Fact: After N1B, the same frozen hero question succeeded through live Hermes and deterministic host execution. Hermes authored a structurally novel experimental plan, validation accepted it, Hermes stopped before execution, and the controller host-confirmed the bound plan.

Decision: Count N1 as a backend engine proof, not as final product polish. The system has now demonstrated language-to-typed-plan-to-real-results for a new composition using the bounded Hermes MCP path.

Learning: The major gap was not Hermes' ability to compose the tactical graph; it was the host contract around output domains and runtime globals. Once `entry_status` exposed `PASS/FAIL/UNKNOWN` and runtime defaults were injected, Hermes authored the correct `entry_status == PASS` predicate without prompt or vocabulary tuning.

Evidence: Live session `20260622_141849_63e2a6` produced `draft_26912b2c452106e8` and `bound_f619f6c9677a4d2a`; host execution `exec_5466f201a479ba0f` returned 64 generic results. The first cache-aware execution was a `MISS`, and the first result has PASS traces plus replay window `replay_63574966cd34b86d`.

Follow-up: Bring this exact N1 loop into Workbench with honest `HERMES_NOVEL_COMPOSITION` provenance, visible typed-plan interpretation, host confirmation, cache status, result evidence, traces, and replay. Do not expand the runtime again unless Workbench exposure reveals a concrete execution defect.
