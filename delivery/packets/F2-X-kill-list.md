# Work Packet F2-X — Kill List & Legacy Quarantine

Issued: 2026-07-03 by the project director. ADR 0012 §4. UNLIKE the
extraction packets, this one deletes code and relocates control flow — it
will face a full adversarial review. Every deletion requires PROOF OF
DEADNESS in the report: the call-graph evidence that nothing live reaches
it, plus the gates that prove behavior held.

Branch `packet/f2-x` off the frontier (tip `2910f03` or later). Stage
commits (one per kill-list item). Standing bars: full-suite table on the
committed tree, the eight pinned gates, fences (catalog untouched;
semantic-registry/generated/frozen-expectations/n1d/artifacts untouched).

## The kill list (from the audit + F2-0/F2-7 censuses)

1. **Noop dispatch registrations** (`wide_channel_dwell`,
   `shift_persistence`, `robust_team_width`, `analysis_rate` ->
   `primitive_noop`): delete the registrations, `primitive_noop` itself,
   and the LEGACY_NOOP allowlist in the registry test (which must now
   assert the debt list is EMPTY). Proof: names absent from catalog, binder
   rejects them already.
2. **Dead duplicate predicate family** (the registered-but-bypassed
   `predicate_*` implementations circa old executor.py:9570-9745, now
   wherever they live): the live path uses
   `execute_predicate_with_resolved_inputs`; the registry copies have
   drifted and are dead. Prove no caller, delete, and delete their
   registration mechanism if it becomes empty.
3. **Fabricated experimental traces**
   (`experimental_predicate_traces_for_result`: hard-coded
   `has_opposite_corridor` always-PASS traces): INVESTIGATE consumers
   first. If any live path (workshop/app_service experimental flows, M1.2
   artifacts) still consumes it, DO NOT delete — report the consumer chain
   and defer to director decision. If dead, delete with proof.
4. **`select_proof_results` M1 labels** in shared code: if reachable only
   from the legacy M1 profile, it moves with the quarantine (item 5); if
   dead, delete.
5. **Legacy M1 profile quarantine**: move every `legacy`/M1-parity branch
   interleaved in the executor core loop (audit: old lines 488-527,
   674-717, 902-905 region — find current locations) into
   `src/tqe/runtime/legacy_m1.py`, invoked ONLY behind the existing
   explicit profile flag. The M1 parity gates (`make m1-verify` if
   runnable, `m1-1-gate-*` where data allows, and the pinned-gate set) must
   stay green — the profile still works, it just stops living in the core
   loop.

## Expected ripples

Deletions of genuinely dead code = zero drift (prove via the pinned gates).
The quarantine is control-flow relocation — the M1.1 suite and parity
gates are its drift proof. If ANY kill-list item turns out live, the report
says so and leaves it standing; killing live code on a technicality is the
failure mode this packet must not have.

## Deliverables

Branch `packet/f2-x`; one commit per item with proof-of-deadness in the
report (call-graph evidence per deletion); executor.py line count
before/after; full-suite table; pinned-gate proof; the boundary-freeze
allowlist SHRUNK by every deleted leak; `delivery/packets/F2-X-REPORT.md`.
