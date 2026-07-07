# RB-001 — Render provisioning (owner runbook)

Execute AFTER DEPLOY-1 merges (the loop will tell you). Each step has
a verification; bring back the artifacts listed at the end.

1. Render dashboard → New → Blueprint → connect the GitHub repo
   (LuisRevillaM/priori or its renamed successor), branch
   codex/afl08-passport-loop. Render reads render.yaml and proposes
   `entrelineas-film-room`. Approve. Verify: the service appears with
   a 10GB disk attached.
2. Service → Environment → set WORKBENCH_HERMES_ENABLED=1 (the
   deliberate-enable switch for live asks; leave 0/absent to ship
   gallery-only) and add secret env var DEMO_ACCESS_TOKEN =
   (generate: `openssl rand -hex 16` — keep it; it is your live-ask
   demo switch). Verify: var shows as set.
3. Build or select the DEPLOY-1 demo bundle produced by
   `scripts/create-demo-data-bundle.py`; set `TQE_DATA_BUNDLE_URL` and
   `TQE_DATA_BUNDLE_SHA256` from that bundle's manifest. If using the
   per-file manifest, set `TQE_DATA_BUNDLE_MANIFEST` too. Verify: deploy
   logs say "Demo data provisioned and verified." or "Demo data already
   satisfies manifest."
4. Service → Secret Files → add file at path
   `/etc/secrets/hermes/auth.json` with the contents of
   `~/.hermes-priori/auth.json` from your Mac. OPTIONAL — skip it and
   the gallery ships with typed `ASKS_DISABLED` for live asks; add it
   later any time.
5. Trigger deploy. Verify: health check passes; the deploy log shows
   "state: warming" then "prewarm complete".
6. Bring back to the loop: the live URL, and the output of
   `python delivery/oracles/DEPLOY-1/deploy_smoke.py --base-url
   <live-url> --demo-token <token>` run from your Mac.

The oracle's PASS on step 5 is this runbook's completion proof.
