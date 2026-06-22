# N1 Live Hermes Failure

Type: proof learning

Fact: The first live N1 Hermes run authored a structurally novel plan and stopped before execution, but the plan was not executable. Host execution failed with `KeyError: 'analysis_rate_hz'`, and the destination-entry predicate compared `entry_status` to `DESTINATION_ENTERED` instead of `PASS`.

Decision: Do not count N1 as passed and do not rerun the frozen hero after observing this failure. The result should open a narrow N1B correction focused on capability output domains and runtime-required parameter contracts.

Learning: Schema-valid typed plans are not enough when output enum domains and hidden runtime-global parameters are under-specified. Hermes can compose the right graph and still author an impossible comparison unless the host exposes and validates allowed output values.

Evidence: Live Hermes session `20260622_131836_38c3fb` used only the bounded `priori_tactical` tools, submitted `draft_412f54700786817a`, validated `bound_a4cdbc77075c85e7`, and stopped before execution. Local host execution of the validated draft fails before result emission because `analysis_rate_hz` is absent.

Follow-up: Add N1B gates before any rerun: runtime-required parameter presence, enum-domain validation for `entry_status`, rejection of tactical labels in status predicates, and a regression fixture using this exact failed plan.
