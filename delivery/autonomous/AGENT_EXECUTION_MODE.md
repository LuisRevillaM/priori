# Agent Execution Mode

Lightweight operating rules for the autonomous run. Not a new milestone system, not another
contract. The spirit:

> **Agents own the run. The protocol exists to keep claims honest, not to slow execution down.**

Bias toward end-to-end progress, use the existing rails, and add ceremony only when it directly
prevents drift, false claims, or unreproducible work.

**Dimension this work improves: semantic breadth under evidence discipline** — Priori becomes less
"a few impressive tactical detectors" and more "an expanding football language where agents can
define, compile, test, and expose new football concepts without humans hand-holding every step."

**The most important correction:** do not let "definition-before-implementation" become
"definition *instead of* implementation."

## Working loop

```text
define enough
→ implement enough
→ verify honestly
→ replay / inspect
→ expose only what passed
→ move to the next capability
```

## Rules

```text
1. Default to vertical slices
   Pick one meaningful football capability/package and drive it from registry definition
   → generated passport
   → runtime binding if in scope
   → verifier
   → evidence/replay
   → agent/product projection only if allowed.

2. No new roadmap unless required
   Use existing AFL/SCP milestones. Do not invent new frameworks unless the current
   one cannot express the work.

3. Ceremony budget
   Each slice gets:
   - one short source-of-truth goal
   - one progress ledger update
   - one verifier/report
   - one learning only if durable
   Anything else needs a reason.

4. Definition work must unlock execution
   Do not spend weeks polishing 741 declarations abstractly.
   Batch/triage them by query-unlock value:
   "What new football questions become possible?"

5. Agents may pivot
   If implementation reveals a better route, agents can change tactics as long as:
   - the claim boundary stays intact
   - tests/verifiers are updated
   - the ledger records why
   - no protected contract is modified

6. Review only at meaningful gates
   Do not request external review after every file.
   Review when:
   - a capability becomes agent-visible
   - product claims change
   - protected-gate promotion is requested
   - evidence semantics change
   - a new standard-library package is complete

7. Human-in-loop only for hard boundaries
   Humans are needed for credentials, paid services, legal/data-governance choices,
   production cutovers, protected-contract amendments, or public claims.
   Not for routine continuation.
```

## 741 atlas strategy

```text
triage by usefulness
batch related concepts
generate registry objects
generate passports
select the smallest high-value executable subset
implement that subset
verify it end-to-end
repeat
```

First package (unlocks a lot of natural football language):

```text
defensive line
relative position to line
controlled line break
lane occupancy
support arrival
local number relation
```

## Practical reminders (from this repo)

- Imitate `verification/afl_g0.py` and `verification/n1d1.py` (verifier-as-spec, fail-closed). Do
  **not** imitate the human-loop `M1/M1.1/M1.2` per-slice `SPEC.md` + `reviews/*.md` + zipped
  review-packet + multi-state ledger pattern — that scaffolding was for a human controller in the
  loop and is dead weight for the autonomous run.
- The one non-negotiable that is *cheap*, not ceremony: fail-closed verifiers + typed gaps + no
  AI/product exposure without verification. Keep it; cut the rest.
- Binding architectural corrections live in `ONBOARDING_RECONCILE_WITH_REALITY.md`. Read it before
  acting on the broader onboarding brief.
