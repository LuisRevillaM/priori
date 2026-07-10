# HERMES-2 — Hermes compiles on GPT-5.6 Sol (measured, never just flipped)

Status: READY  Grade: B
Branch: packet/hermes-2  Oracle: the COMMITTED eval harness
(scripts/scp2_2/eval_harness.py) + the FROZEN dev set
(delivery/packets/scp2-2-dev-cases.json, hash
07a10d76b1f3322e94131090068f19157975fbea65aefbebdb8e17aba2da4b7a) —
both FENCED (leg-zero diff; R-AW law: eval-case edits are
misreport-class).
Headline risk: a model swap that silently changes compile semantics —
the upgrade ships only on evidence, and a WORSE honest number is a
legitimate finding, not a failure to hide.

## Context
Owner directive 2026-07-10: move the product's NL compiler to the
GPT-5.6 Sol line at maximum effort, same ChatGPT subscription
(billing law holds). Baseline on gpt-5.5: 7 PASS / 8 FAIL on the
frozen dev set (SCP2-2 round 3, honest). A stronger compile may also
close the owner-phrasing gap ahead of CAP-1 — measure, don't assume.

## Scope
1. PROBE: one live interpret through the bridge with
   HERMES_SCP2_2_MODEL=gpt-5.6-sol via the canonical home
   (~/.hermes-priori). Confirm the OAuth provider accepts the model
   id; determine whether the Hermes agent config accepts
   reasoning_effort "max" (current: xhigh) — if max is rejected,
   xhigh is the ceiling; record which fired.
2. MEASURE: run the frozen dev set through the COMMITTED harness on
   gpt-5.6-sol at the highest accepted effort. Full per-case table vs
   the 7/15 baseline: newly passing, newly failing, unchanged; every
   failure attributed (genuine gap vs model output shape vs
   truncation). Latency per case recorded (Sol at max may be slower —
   the ask path budget cares).
3. FLIP ON EVIDENCE: if PASS count >= baseline AND no new wrong-answer
   class appears (honest refusals may shift category; fabrications
   are disqualifying), update the committed defaults
   (src/tqe/semantic_compiler/hermes_nl.py DEFAULT_MODEL, harness
   default, ~/.hermes-priori config default + effort) and rerun the
   dev set once on the committed tree as the landing evidence. If
   WORSE: report the honest table, flip nothing, and FLAG for the
   director's ruling.
4. OWNER-PHRASING SPOT-CHECK (evidence for CAP-1 scoping, not a
   gate): compile the owner's sentence "When the ball carrier is
   pressed and no support arrives, how often does his team keep the
   ball?" on Sol; report the outcome class and, if expression, whether
   it binds — the honest refusal on 5.5 is the baseline.

## Ground rules
House law (stage-commit, never push, R-AZ, full-suite table,
deviation law). Billing: subscription only — flag any metered
fallback as auto-REJECT territory. Fences: harness, dev set, blind
pins, oracles, sealed evidence.

## Acceptance
Leg zero fence-diff; director reproduces the headline comparison
numbers; adversarial review attacks the comparison's honesty
(same harness invocation both runs, no case-shaped accommodations).
