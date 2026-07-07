# DEPLOY-1 — the Film Room goes public (gallery-first)

Status: READY  Grade: B
Branch: packet/deploy-1  Oracle: delivery/oracles/DEPLOY-1/deploy_smoke.py
Headline risk: a deploy that hangs or lies — the service today blocks
its port on prewarm (would fail Render health checks), and a public
surface must degrade honestly when the model or cache is unavailable.

## Ground rules
Unchanged house law (stage-commit, never push, R-AZ, full-suite table,
deviation law, DELIVERED-with-evidence). Fences: ledger, sealed
evidence, atlas, docs/design charter, blind pins. The oracle is
COMMITTED — do not modify it; if it cannot pass as written, FLAG with
evidence and request a ruling.

## Scope

1. **Bind-before-warm.** The service binds and serves immediately;
   prewarm runs in the background; /api/film-room/bootstrap returns an
   honest `state: warming` payload (with what is warming and since
   when) until ready. The UI renders the warming state per the design
   charter's tone (no spinners-forever: say what is happening).
2. **Demo-token gate for live asks.** /api/film-room/ask requires a
   token (env DEMO_ACCESS_TOKEN precedent) when TQE_PUBLIC_MODE=1;
   without it, a typed DEMO_TOKEN_REQUIRED response (the oracle checks
   this is never a schema lie). Local/dev mode unchanged.
3. **Render blueprint.** render.yaml gains the `entrelineas-film-room`
   service: gunicorn-or-equivalent single service, persistent disk
   (10GB) mounted for canonical data + node cache + workshop output,
   env vars (TQE_NODE_CACHE_ROOT, TQE_EXECUTION_WORKERS, TQE_PUBLIC_MODE,
   DEMO_ACCESS_TOKEN, HERMES_HOME secret file path), health check on
   /film-room, build that includes the frontend bundle.
4. **Data + cache provisioning.** Reuse the demo-bundle machinery
   (scripts/create-demo-data-bundle.py, provision-demo-data.py) to
   ship canonical data; extend the bundle to include the warmed node
   cache and prewarmed execution caches so first bootstrap on Render
   is fast. Provisioning is idempotent and verified (the provision
   script exits nonzero on hash mismatch).
5. **Hermes on Render (flagged degradation).** The service reads
   HERMES_HOME from a Render secret file when present; when absent or
   auth fails, asks return a typed ASKS_DISABLED/honest error — the
   gallery never breaks because the model is unavailable.

## Deliverables
The fixes + blueprint + provisioning; delivery/runbooks/RB-001 updated
with EXACT owner steps if any diverge from the committed draft;
stage-committed report; oracle run against LOCAL service (both modes:
public with token, public without) with output committed as evidence;
full-suite table.

## Out of scope
The actual Render dashboard actions (owner, RB-001); DNS/custom
domain; retiring the old priori-* service (owner, after Gate 1).

## Acceptance
Oracle green against local public-mode service (director re-runs);
after the owner executes RB-001, oracle green against the live Render
URL — that second run is the Gate-1 deploy evidence.
