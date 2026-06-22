# N1B Capability Contract

Type: proof learning

Fact: The first live N1 Hermes plan was structurally useful but should not have validated as executable. It omitted host runtime globals and compared `relation_destination_entry.entry_status` to the tactical label `DESTINATION_ENTERED` instead of the capability value `PASS`.

Decision: Treat output domains and runtime globals as host-owned execution contracts. Authored plans may omit hidden runtime defaults, but the binder must inject them deterministically. Enum outputs must declare allowed values, and validation must reject impossible comparisons before execution.

Learning: A model can compose the correct tactical graph and still fail by confusing a predicate output domain with a classification label. The host should make that distinction impossible to miss: `entry_status` is `PASS`, `FAIL`, or `UNKNOWN`; classification rules can then emit labels such as `DESTINATION_ENTERED`.

Evidence: `src/tqe/verification/n1b.py` replays the exact failed Hermes draft fixture through the model-visible submit/validate path and rejects it with `compare_value_not_allowed`. A corrected version with `entry_status == PASS` receives host-injected runtime globals, requires host confirmation, and executes generically over canonical match data.

Follow-up: Re-freeze the current Tactical Knowledge Pack and Hermes configuration, then rerun the same frozen N1 hero question once without prompt, catalog, alias, primitive, or operator tuning.
