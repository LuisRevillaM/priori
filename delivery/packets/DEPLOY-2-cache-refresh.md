# DEPLOY-2 — the story returns to the public gallery

Status: READY  Grade: B
Branch: packet/deploy-2  Oracle: delivery/oracles/DEPLOY-2/chain_gallery.py (FENCED)
Headline risk: OWNER FINDING 2026-07-10 — the live board does not map
to the question in the viewer's head. Root cause one is the D1-ratified
degradation: table-served moments carry no stage witnesses, so the
turf shows dots without the story. This packet expires that exception.

## Scope
1. Rebuild the demo data bundle with node/execution caches generated
   under the CURRENT code epoch (the PERF-1 cache machinery; the
   bundle host + SHA config discovered in DEPLOY-1B). Idempotent,
   hash-verified, provenance-stamped per R-AZ.
2. MEMORY PROOF BEFORE RENDER: run the service in a 2GB-limited local
   container (docker --memory=2g) with execution prewarm ON and the
   refreshed caches; prewarm must complete without OOM and the strict
   gallery oracle plus this packet's chain oracle must PASS locally
   under that limit. If 2GB cannot hold even cache-hit prewarm, STOP
   and report with the measured peak — the fallback fork (keep tables
   + lazy chain hydration vs plan upgrade) is the director's ruling,
   not yours.
3. Ship: upload bundle, update bundle SHA env, flip
   WORKBENCH_PREWARM_FILM_ROOM=1, redeploy, confirm no crash-loop
   (stability probe ≥5 min), then the chain oracle against the live
   URL — director reproduces as acceptance.
4. The D1 exception in DEPLOY-1C-REVIEW is marked EXPIRED in the
   report when the live oracle passes.

## Ground rules
House law; fences: both deploy oracles, sealed evidence, dev sets,
blind pins, docs/design (the constitution is director-only). Render
API key: use, never print. Subscription only.

## Acceptance
Leg zero; local 2GB-container evidence; live chain-oracle PASS
reproduced by the director; no crash-loop for 5+ minutes post-deploy.
