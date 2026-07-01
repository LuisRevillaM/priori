# M1.1S Gate S4 Controller Review

Decision: `ACCEPTED_CONTROLLER_ONLY`

S4 implements rule-driven generic result emission.

The generic experimental corridor plan now emits real `QueryResult` rows under `compatibility_profile=generic` instead of returning zero rows or relying on the legacy M1 result emitter.

Accepted evidence:

- `make m1-1-gate-s4-verify`: pass, 13/0/0.
- Generic experimental execution emits 15 rows and 105 predicate traces.
- Both declared labels are present: `DESTINATION_ENTERED` and `CORRIDOR_PERSISTED_NO_DESTINATION_ENTRY`.
- Requested evidence resolves from declared runtime outputs.
- Generic rows do not expose `block_shift_score`, `wide_entry_frame_id`, or `signed_shift_metres`.
- Generic traces contain no legacy adapter evidence.
- `max_results`, `bind_only`, and `dry_run` are honored.
- Frozen M1 parity remains 180 rows and 900 traces through the explicit legacy helper.

Residual risk:

S4 does not prove a second tactical family, Hermes, UI behavior, or final demo readiness. The next architecture proof should be the second dissimilar tactical pattern.
