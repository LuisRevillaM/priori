# GEO-0a — observation-manifest enforcement (substrate law 1 of 3)

Era: GEO (ADR 0018 governs; charter §3.1)  Grade: B
Branch: packet/geo-0a off the frontier
Oracle: the charter's own sentence, executable — "absence becomes
negative evidence only when relevant coverage is certified" — proven
by tests on BOTH sides (certified-coverage absence → FAIL permitted;
uncertified absence → UNKNOWN forced), plus the standing suite.
Headline risk: retrofitting coverage semantics into existing
primitives changes certified behavior — any change to an EXISTING
certified result is a STOP-and-report, not a silent migration.

## The law (charter §3.1, operative)

Event absence, ball absence, or missing player tracks may count as
negative evidence (FAIL) ONLY when the observation manifest certifies
coverage for the relevant modality and window. Uncertified absence is
UNKNOWN, always, everywhere.

## Scope

1. A manifest-coverage interface at the evidence layer: for a
   (modality, match, period, window), answer certified/uncertified
   from the observation manifest. Demo data ships with its manifest
   truthfully populated (what SkillCorner-derived canonical data
   actually certifies); absent manifest = uncertified (fail-closed).
2. Wire the existing absence-sensitive primitives to consult it —
   inventory them first and DISCLOSE the list in the report (the
   charter names event/ball/player-track absence; find every place
   the runtime currently converts absence into FAIL).
3. Tests both directions per the oracle line, with the mutation
   standard (break the gate, watch named tests fail).
4. If ANY existing certified table/result would change value under
   the law, STOP and report the delta — the director rules on
   re-certification; nothing re-certifies silently.
5. SHADOW-1 tie-in: the vision adapter's manifest rows must express
   "possession/ball uncertified" so the vacuous table's UNKNOWNs flow
   from THIS law rather than ad-hoc handling — one mechanism, both
   data sources.

## Fences

Charter thresholds/definitions (ADR 0018 is director-only), oracles,
dev sets, sealed evidence, certified tables (read-only — see STOP).

## Acceptance

Leg zero; both-directions tests reproduced by the director; the
disclosed inventory adversarially checked (grep the runtime for
absence-to-FAIL conversions the inventory missed); full-suite table;
STOP honored if certified values move.
