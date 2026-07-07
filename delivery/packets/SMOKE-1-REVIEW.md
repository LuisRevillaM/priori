# SMOKE-1 Review: ACCEPTED

Reviewed 2026-07-07 at e1f41d4. The owner's first smoke-test ask,
closed with its truth restored: the request was never bad — the
synthesizer honestly refused the model's composition (rate subset-law
missing_constraint) and the old blanket handler blamed the payload.
Now: schema errors are scoped to request parsing; internal failures
log tracebacks with correlation ids; truncated model output routes to
continuation or a typed MODEL_OUTPUT_TRUNCATED refusal; the UI renders
three distinct error identities; and the owner's exact question,
re-run live, returns an honest refusal naming the real constraint.
The legacy Playwright e2e failure is honestly disposed (pre-existing
route arrangement, recorded). Director's suite green (576).

Capability-program note carried forward: the owner's natural phrasing
of the flagship question should LAND on the flagship composition, not
refuse — the few-shot library gains that mapping as its next entry.
