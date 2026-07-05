# Work Packet R2-4: sequence_pattern — moments become narratives

**Era**: R2 grammar widening under the SCP-2 bridge (ADRs 0013/0014/
0015 all govern)
**Branch**: `packet/r2-4` off the frontier
**Executor ground rules**: unchanged (stage-committed report at
`delivery/packets/R2-4-REPORT.md`; full-suite table on the committed
tree; commit locally, never push; clone route with prominent
provenance if blocked; deviation law: STOP, flag, request
ratification).

**Fences**: unchanged (ledger director's-only — note the guarded
writer now requires double-explicit sanction; atlas; sealed evidence;
autonomous artifacts except the search tool's canonical report; no
freezes/re-pins).

## Headline risk (the spec is the math)

A sequence asks "did B happen after A?" — and the honest answer is
three-valued. The risk is collapsing "no successor OBSERVED" into "no
successor EXISTED". The chain-status law:

For a chain of declared stages S1..Sn, each stage matched within a
declared window after its predecessor's anchor frame, with declared
continuity constraints (same_team_perspective always; same_possession
and same_player optional, validated against the composition-constraint
vocabulary):

- Chain PASS: every stage has a PASS-status match in order within its
  window, satisfying continuity.
- Chain FAIL: some stage's window is FULLY OBSERVED (window end within
  the period's observed frames, no coverage gap) and contains no
  PASS-or-UNKNOWN candidate satisfying continuity.
- Chain UNKNOWN: otherwise — a window truncated by period end or
  coverage gap, or a window whose only continuity-satisfying
  candidates are UNKNOWN-status anchors. UNKNOWN is not FAIL: an
  unobserved successor is not a disproven one.

Declared match policy (enum: first | all) and overlap policy are
bind-time parameters — no implicit greediness. Each chain record
carries per-stage witnesses (anchor ids, frames, statuses) so every
narrative is replayable stage by stage.

## Scope

### 1. The operator
`src/tqe/runtime/operators/sequence_pattern.py`, registry citizen
behind the binder (nine-rule template; structural dispatch; ratchet
extended; constraint defaults per R-Z: same_team_perspective_required
TRUE with declared-reason opt-out). Stages reference bound anchor
relations from the existing grammar — any composition that emits
anchor evidence can be a stage. Output: chain records (anchor-level
evidence, one per chain) with tri-state chain status per the law,
composable downstream (aggregate_over/rate must bind over chain
records — that composition is part of acceptance, not a rider).
Registration flows into the knowledge pack's composition_grammar
automatically at regeneration — verify and state the pack delta in
the report (the director re-verifies at merge).

### 2. Flagship: counter-attack initiation
"After a regain, does the team progress the ball forward and keep it?"
Chain: transition_anchor (regain) → carry with
forward_progression_m >= 3.0 starting within 5.0s of the regain →
controlled pass completed within 4.0s of the carry end, all same team
perspective, same possession continuity. Per team per match, all
seven matches, both perspectives: chain counts via aggregate_over
(count intervals per ADR 0014) and the initiation rate via rate
(chains-completed over regains, subset law, six-way partition).
Committed under `delivery/packets/r2-4-flagship/` with a
byte-reproducing generator (timestamps in an uncommitted sidecar).
Flag long executions rather than running them to death.

### 3. A meaning expression for the flagship
Because the bridge exists now: commit the flagship's meaning
expression fixture and show it synthesizes the same target the
generator uses (the first operator to land AFTER the bridge should
prove the loop: new grammar → pack → expressible → synthesizable →
certified). If any layer cannot express sequences yet, that is a
FLAGGED deviation with the smallest missing piece named — do not
silently extend bridge schemas beyond what R-AE ratified; request
ratification.

### 4. Tests (mutation standard)
Hand-computable chain fixtures covering: full PASS chain; FAIL by
fully-observed empty window; UNKNOWN by truncated window; UNKNOWN by
UNKNOWN-status candidate; continuity violation excluded (and the
R1-5 case-law both-teams pattern); match policy first vs all;
window-boundary off-by-one (a successor exactly AT the window edge —
declare the boundary semantics and test it); chain records compose
under aggregate_over. Mutations: collapse UNKNOWN-truncated-window
into FAIL → named test fails; drop continuity check → named test
fails.

## Explicitly OUT of scope
entity_set_algebra, spatial_join; any NL/model work (SCP2-2); ledger
targets or flips; dossier surface.

## Deliverables
Operator + registration + pack delta statement; flagship evidence +
generator + meaning-expression fixture; tests; stage-committed report
with full-suite table. Nothing pushed.
