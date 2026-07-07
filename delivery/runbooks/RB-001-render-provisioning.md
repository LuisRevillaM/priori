# RB-001 — Render provisioning (owner runbook)

Execute AFTER DEPLOY-1 merges (the loop will tell you). Each step has
a verification; bring back the artifacts listed at the end.

1. Render dashboard → New → Blueprint → connect the GitHub repo
   (LuisRevillaM/priori or its renamed successor), branch
   codex/afl08-passport-loop. Render reads render.yaml and proposes
   `entrelineas-film-room`. Approve. Verify: the service appears with
   a 10GB disk attached.
2. Service → Environment → add secret env var DEMO_ACCESS_TOKEN =
   (generate: `openssl rand -hex 16` — keep it; it is your live-ask
   demo switch). Verify: var shows as set.
3. Service → Secret Files → add file at path /etc/secrets/hermes/
   (the exact path DEPLOY-1's report states) with the contents of
   ~/.hermes-priori/auth.json from your Mac. OPTIONAL — skip it and
   the gallery ships with asks disabled; add it later any time.
4. Trigger deploy. Verify: health check passes; the deploy log shows
   "state: warming" then "prewarm complete".
5. Bring back to the loop: the live URL, and the output of
   `python delivery/oracles/DEPLOY-1/deploy_smoke.py --base-url
   <live-url> --demo-token <token>` run from your Mac.

The oracle's PASS on step 5 is this runbook's completion proof.
