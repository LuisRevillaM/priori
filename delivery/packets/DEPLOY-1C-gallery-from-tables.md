# DEPLOY-1C — the gallery serves from committed certified tables

Status: READY  Grade: B
Branch: packet/deploy-1c (worktree /private/tmp/entrelineas-deploy1c)
Oracle: delivery/oracles/DEPLOY-1C/gallery_ready.py (FENCED)
Headline risk: the public URL currently reports honest-warming forever
on 2GB instances — prewarm executes full plans (OOM crash-loop at any
worker count; the disk's caches are stale under current code epoch, so
the Merkle keys rightly refuse them). The gallery must become servable
WITHOUT execution.

## Scope
1. A serve-from-certified-tables prewarm path in app_service.py: when
   a flagship plan's hash matches a committed certified table
   (film_room_certified_table_for_plan_hash), construct the bootstrap
   answer FROM the table + committed plan document — interval card,
   moments list, labels, provenance — with NO plan execution. Replay
   windows stay lazy (built on first request per moment; single-window
   memory is fine). Evidence-rows kind stays honestly "certified".
2. Flag semantics: table-based prewarm ALWAYS runs (it is cheap);
   WORKBENCH_PREWARM_FILM_ROOM gates only the EXECUTION variant
   (which upgrades answers in place when it completes). Render env
   keeps execution prewarm off until DEPLOY-2 refreshes bundle caches.
3. Local proof: run the service locally with execution prewarm
   disabled and the oracle against it (state=ready, interval law,
   servable replay window). Commit output as R-AZ evidence.
4. Flag any memory reads in the lazy replay path that would load more
   than the requested window.

## Ground rules
House law. Fences: the oracle above, DEPLOY-1 oracle, dev sets, blind
pins, sealed evidence, docs/design. Do NOT touch
src/tqe/semantic_compiler/ (HERMES-2 owns that surface in the main
tree — worktree isolation is the point).

## Acceptance
Leg zero fence-diff; oracle green locally (director reproduces);
after merge+deploy, oracle green against the live URL — that run
closes the packet.
