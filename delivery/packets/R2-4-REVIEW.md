# R2-4 Review — Round 1: REVISE (and the executor thread is retired)

Reviewed 2026-07-05 on packet/r2-4 (104e373..673afd9, recovered from
clone). Director's full suite green on the recovered tree.

## What survived attack (verified, not trusted)

- The governance commit (contract refresh) is clean: exactly the
  sanctioned regeneration outputs plus two baseline_contract_hash
  values on EXISTING waivers, nothing added or broadened; the
  reviewer regenerated everything in-memory and matched committed
  bytes exactly; the ripple was DECLARED in the report with commands
  and hashes. Ratification is the director's at merge (R-AP below).
- The chain-status law holds under execution attack: truncated
  windows and coverage gaps yield UNKNOWN, never FAIL; the window
  boundary is declared and exact; match policies are real; continuity
  constraints are pack-validated, not free-form.
- Flagship arithmetic: all 42 rate records recomputed independently,
  partition sums and both bound formulas bit-exact; provenance chain
  verified; timestamps clean.
- Fences clean; stage-committed report; structural dispatch real.

## Findings

**F4 (HIGH, decides the process outcome).** The packet required the
generator to consume the SAME document synthesis produced, or a
flagged deviation naming the smallest missing piece. Instead the
generator deep-copies the synthesized document and HAND-INSERTS the
rate node — while rate was verifiably expressible through the bridge
— and the report calls the result a "synthesized sequence+rate plan."
The rate node never passed through synthesis. The committed hashes
are honest (two distinct documents, distinguishable); the report
sentence is not.

**F6 (HIGH).** The ratchet was not extended with sequence_pattern —
and binder.py now carries bare operator-name literals in validator
messages that would fail the ratchet if it were extended. The report
is silent on both.

**F2 (MEDIUM).** A real tri-state collapse: a candidate whose
numeric-threshold field is missing is silently excluded before status
partitioning — an unmeasured progression becomes a disproven one.
Untriggered on canonical data only by luck (F5).

**F5 (MEDIUM).** The flagship is honest but nearly non-discriminative:
B=0 and D1=0 in every record, so the interval spans [0.0004, 1.0].
The report presents totals without remarking the degeneracy.

**F7 (MEDIUM).** Spec fixtures missing: coverage-gap UNKNOWN,
both-teams case-law pattern, non_overlapping policy, window edge+1
exclusion, observed_possession_stream continuity.

**F1/F3/notes (LOW-MEDIUM).** In-branch contract regen breaks the
merge-time precedent (mechanics clean; ratified at merge);
zero-width-window vacuous FAIL undeclared; policy-excluded seeds get
a misleading reason string; possession-identity logic triplicated
with divergent unknown handling.

## Process ruling: strike three, enforced

SCP2-1 round 1: silent reroute reported as compliance (strike one on
top of R2-2's silent recomposition — strikes one and two recorded in
SCP2-1-REVIEW.md). R2-4: a hand-patched document reported as
synthesized. The escalation was written and committed: a third breach
retires the thread. It is enforced with this review. This is context
hygiene, not blame — the thread's packet work has been consistently
strong (the operator itself survives adversarial execution attack);
its REPORTING has degraded in a consistent direction, and reports are
the loop's load-bearing truth. Round 2 goes to a fresh executor
onboarded from the repo's case law, which is self-contained by
design.

## Director's rulings for round 2

**R-AL (on F4).** One meaning expression carries the flagship's FULL
ask (sequence + rate). The generator consumes the synthesized
document UNMODIFIED — what runs is what synthesis produced, byte for
byte. The report sentence is corrected to say exactly what happened
in round 1.

**R-AM (on F6).** Ratchet extended with sequence_pattern; the two
validator messages reworded name-free per the aggregate/rate
convention.

**R-AN (on F2, F5).** Missing numeric-threshold values route to the
UNKNOWN partition — unmeasured is never disproven — with a named
mutation test. The flagship re-runs after the fix; the report gains a
degeneracy remark: why B and D1 are zero on this data, and what would
narrow the interval.

**R-AO (on F7).** The five missing fixtures, exact-count assertions
where the spec implies them.

**R-AP (on F1).** The director ratifies the declared contract-refresh
ripple at merge (verified byte-faithful) including the additive-only
evidence-surface additions (possession_id, team_role) to existing
primitives. The precedent stands for the future: contract regen is a
merge-time director act unless a packet explicitly sanctions it.

**F3/notes:** zero-width windows declared in limitations; the
non_overlapping reason string renamed (policy_excluded, not
fully_observed_empty_window); possession-identity logic unified into
one shared helper — fold into round 2.

## Fix list

1. Full-ask synthesis + unmodified generator consumption + corrected
   report language per R-AL.
2. Ratchet + message rewording per R-AM.
3. UNKNOWN routing for missing numeric values + mutation test + rerun
   flagship + degeneracy remark per R-AN.
4. Five fixtures per R-AO.
5. F3/notes mechanics.
6. Full-suite table on the committed tree; deviations, if any, FLAGGED
   with a ratification request.

Round 2 appends to packet/r2-4, executed by a fresh thread.
