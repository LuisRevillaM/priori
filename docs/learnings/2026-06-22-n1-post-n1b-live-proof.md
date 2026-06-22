# N1 Post-N1B Live Proof

Type: proof learning

Fact: After N1B, the same frozen hero question succeeded through live Hermes and deterministic host execution. Hermes authored a structurally novel experimental plan, validation accepted it, Hermes stopped before execution, and the controller host-confirmed the bound plan.

Decision: Count N1 as a backend engine proof, not as final product polish. The system has now demonstrated language-to-typed-plan-to-real-results for a new composition using the bounded Hermes MCP path.

Learning: The major gap was not Hermes' ability to compose the tactical graph; it was the host contract around output domains and runtime globals. Once `entry_status` exposed `PASS/FAIL/UNKNOWN` and runtime defaults were injected, Hermes authored the correct `entry_status == PASS` predicate without prompt or vocabulary tuning.

Evidence: Live session `20260622_141849_63e2a6` produced `draft_26912b2c452106e8` and `bound_f619f6c9677a4d2a`; host execution `exec_5466f201a479ba0f` returned 64 generic results. The first cache-aware execution was a `MISS`, and the first result has PASS traces plus replay window `replay_63574966cd34b86d`.

Integrity follow-up: Opus correctly identified that the proof needed cleaner artifact provenance and narrower claims. N1C now records both the knowledge-pack file hash (`7cf720c8210b1d81f12574c5c8299a1dc309930eb1ce17f8eb934d8814119962`) and semantic hash (`fd6d0843d32cc9632bc864b3dad11af4fea060fa2a5fd827196b3458af37b7a0`) in a canonical freeze manifest, exercises PASS/FAIL/UNKNOWN through actual generic destination-entry node execution, proves `entry_status == PASS` preserves UNKNOWN, and scans executor runtime-parameter accesses against host defaults plus checked-in recipe parameters.

Scope: The enum-domain guarantee applies only to catalog outputs that explicitly declare `allowed_values`; N1C enforces that runtime contract for declared enum outputs and currently covers `relation_destination_entry.entry_status`. The live first result's `time_to_entry_seconds=0.0` means destination-region presence at the corridor open frame/immediate same-sample entry, not a separately observed later transition. Workbench should use `entry_mode` (`PRESENT_AT_OPEN`, `ENTERED_AFTER_OPEN`, `NOT_ENTERED`, `UNKNOWN`) to avoid overstating transition semantics.

Follow-up: Bring this exact N1 loop into Workbench with honest `HERMES_NOVEL_COMPOSITION` provenance, visible typed-plan interpretation, host confirmation, cache status, result evidence, traces, and replay. Do not expand the runtime again unless Workbench exposure reveals a concrete execution defect.
