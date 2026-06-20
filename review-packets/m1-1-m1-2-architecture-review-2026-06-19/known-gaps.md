# Known Gaps

## gap: M1.1 not implemented

Classification: `not_in_scope`

What is missing: Tactical Query IR, binder, generic executor, relation layer, parity proof, no-code composition proof, predicate traces.

Why it matters: The packet only asks whether this should be built, not whether it works.

Default boundary: Treat all M1.1 behavior as planned until implemented and verified.

Next action: External review should approve, reject, or revise M1.1 before implementation.

## gap: M1.2 not implemented

Classification: `not_in_scope`

What is missing: Hermes tool boundary, draft/bind/execute flow, feedback loop, revision diffs, recipe versioning, workshop UI.

Why it matters: Hermes behavior is intentionally deferred until M1.1 proves the deterministic runtime.

Default boundary: Do not begin Hermes/workshop work until M1.1 passes.

Next action: External review should assess whether M1.2 sequencing and gates are strong enough.

## gap: independent approval pending

Classification: `requires_human_decision`

What is missing: external reviewer decision on the split.

Why it matters: The owner asked for this review before starting implementation.

Default boundary: Do not treat M1.1/M1.2 as externally approved until feedback is received and integrated.

Next action: Paste `EXTERNAL_REVIEW_PROMPT.md` into the external agent.

## gap: full repo and local data unavailable to reviewer

Classification: `requires_full_repo`

What is missing: raw/canonical data, implementation code, generated artifacts.

Why it matters: Reviewer cannot reproduce local M1 verification or inspect source-level implementation details.

Default boundary: The reviewer should focus on architecture, sequencing, gates, and downstream implications.

Next action: If they request specific implementation evidence, generate a follow-up packet.
