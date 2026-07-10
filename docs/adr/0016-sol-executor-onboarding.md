# ADR 0016 — GPT-5.6 Sol executor onboarding record

Date: 2026-07-10. Status: ACCEPTED.
Session: 019f4abb-3b78-7570-964b-f0ace45697c5 (CLI 0.144.1, Sol/max).

The new executor's candid onboarding critique, and the director's
rulings on each point:

1. "Oracles are instruments, not truth — the deploy oracle itself
   needed three corrections." ADOPTED: oracle amendments are recorded
   in the owning review file (already practiced; now law), and
   design-bearing oracles get cross-family review like any keystone.
2. "Fences should be machine-readable, not prose reconstructed from
   case law." ADOPTED as ledger item: a fences manifest per packet,
   checked mechanically at leg zero.
3. "Builder-never-judges must not become builder-never-thinks."
   AFFIRMED: dissent and spec-challenge are duties under the deviation
   law; judging own work remains forbidden. Authority and judgment
   are different things.
4. "R-AZ self-attestation is weak — separate deterministic evidence
   payloads from run-attestation envelopes, cross-hashed." ADOPTED as
   ledger item (R-AZ v2 design, director keystone).
5. "The director is an epistemic single point of failure on
   constitutional changes." ADOPTED with the new protocol's
   instrument: constitutional/semantic-law changes (ADRs, era
   constitutions, oracle semantics) receive CROSS-FAMILY review
   before merge; the owner remains the appeal path.
6. "Ruling IDs were reused across reviews; the case law needs a
   registry with supersession." CONFIRMED defect; ledger item
   (rules registry packet).
7. "STATE.md was stale at my cold boot." CONFIRMED and fixed in this
   commit; STATE freshness is henceforth part of every merge batch's
   governance step, not a periodic cleanup.

The executor accepted the evidentiary constitution in writing and
reserved the right to challenge weak oracles and vacuous gates —
which is the arrangement working as designed.
