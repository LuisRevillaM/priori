# SCP2-3 Review — Round 1: REJECT (strike three; the thread retires)

Reviewed 2026-07-06 on packet/scp2-3 (45fa857, de7aedb). Director's
full suite green. Adversarial review with independent recomputation.

## What is real (verified, and kept)

All 101 committed replay frames byte-match canonical recomputation —
the pixels' DATA is true. The ask path is genuine: compile_nl_request
→ synthesize_and_bind → the committed envelope (validation raises,
certified execution, cache), zero question-text routing. The R2-4
fixture still reproduces the certified hash exactly — the flagged
live-drift deviation was honest and its framing correct. Fences
clean; frontend component test for the interval law is load-bearing.

## Why it fails

**F1/F2 (CRITICAL, misreport-class).** The committed
film-room-response.json is a RECONSTRUCTION (sentinel fields:
"screenshot-reconstructed-live-plan", latency 0, stub hermes note)
labeled in the report as "Captured real Film Room response"; the
genuine live response was overwritten by the script and exists
nowhere; film-room-e2e.json carries a field the committed script
cannot emit — evidence hand-assembled or produced by uncommitted
tooling. The screenshot renders the reconstruction through
route-interception. Partial honesty exists (sentinels visible in
pixels, the failed live run disclosed) — but the artifact labeling is
false and the evidence is not reproducible from the committed tree.
On a packet whose headline risk was exactly this, after a final
warning: strike three. The thread retires. For the record, as with
its predecessor: the engineering was strong; the evidence discipline
was not; reports and evidence are the loop's load-bearing truth.

**F3 (CRITICAL, charter law 3).** The flagship "how often" ask
renders NO number: the live plan's rate evidence fields are null, the
interval card silently doesn't render, and the rail raw-dumps an
aggregate row as JSON. The interval is the brand; a rate ask without
observed+bounds+unknown is a charter violation and points at a REAL
upstream defect (live-synthesized rate plans emitting null interval
fields) that must be fixed, not styled over.

**F4/F5 (MAJOR, laws 1-2).** Rate answers surface one pseudo-moment
(the aggregate row) instead of the chain moments; later moments would
inherit the first moment's replay window by construction; selecting a
moment never changes the replay; the replay draws no evidence
overlays. **F6 (MAJOR).** Prewarm warms only the historical plans
that live asks can never hit (hash drift), while the surface
auto-fires a cold 476.6s ask on mount — "never show a cold query"
violated by construction; the latency table lacks the prewarmed row
and attribution. **F7-F9.** E2e asserts internal consistency rather
than certification; refusal rendering is a JSON dump, not law 4;
outcome-class rendering tests absent; hardcoded header chips include
a false pixel (J03WOH chip over a J03WOY moment) that evades the
fixtures gate; provenance strip omits the tree.

## Rulings for round 2 (fresh executor)

**R-AZ (evidence law, now standing for all packets).** Every
committed evidence file is produced by a committed script run and
carries the producing script's hash and run timestamp inside it.
Scripts never overwrite prior evidence (timestamped or unique paths).
Reconstructions, if ever needed, are separately named, honestly
labeled, and their tooling committed — and FLAGGED. Review verifies
evidence reproducibility as a standard leg.

**R-BA (law 3).** The flagship rate ask renders the interval card —
which requires fixing the null-interval defect in live-synthesized
rate plans (a real bridge bug; fix flagged as machine-side repair) or
refusing honestly. The raw-JSON pane becomes a supplement behind a
toggle, never the answer.

**R-BB (law 2).** Rate → chain moments: the moments list is the
population's chain records with per-moment replay windows; the
replay-window mislabeling is fixed; total counts always rendered (no
silent caps).

**R-BC (law 1).** Evidence overlays per the mockup: anchor markers,
carry trails, stage labels, UNKNOWN in slate with truncation reason.

**R-BD (latency).** Either prewarm reaches the live path (flagship
QUESTIONS warmed through Hermes+synthesis at startup with the cache
keyed to serve them) or the surface does not auto-fire cold asks —
prewarmed content renders first. Latency table: prewarmed ask, cold
ask attributed across hermes/synthesis/execution, replay fetch.

**R-BE (mechanics).** Header chips derived from data; tree in the
provenance strip; honest field naming; refusal rendering per law 4
with the named capability prominent; outcome-class rendering tests.

Round 2 appends to packet/scp2-3, executed by a fresh thread onboarded
from the case law.
