# DEPLOY-1B — provision the public Film Room via the Render API

Status: READY  Grade: B
Branch: packet/deploy-1b  Oracle: delivery/oracles/DEPLOY-1/deploy_smoke.py
(committed, FENCED — leg-zero diff applies; if it cannot pass as
written against the live URL, FLAG with evidence and request a ruling)
Headline risk: an outward-facing deploy — the first URL a stranger
could hit. It must serve the gallery honestly or not exist; nothing
half-configured stays reachable.

## Context
The owner authorized Render deployment and directed the loop to
provision itself: RENDER_API_KEY and RENDER_OWNER_ID are in the
executor environment. Existing priori-era services are already paid
for and may carry usable data. DEPLOY-1 (merged) made the service
public-mode-ready: bind-before-warm, token gate, honest degradation.

## Ground rules
- The API key is used, never printed, never committed, never echoed
  into logs or reports. Report service IDs and URLs only.
- NO Hermes credential upload — gallery-first. Live asks ship
  disabled (typed ASKS_DISABLED); the Hermes secret remains an
  owner-runbook option for later.
- Fences: delivery/oracles/**, sealed evidence, ledger, atlas,
  docs/design/**. House law: stage-commit, never push, R-AZ evidence,
  full-suite table, deviation law, DELIVERED-with-evidence.
- Do not delete or stop any existing service — the owner retires old
  services himself after Gate 1.

## Scope
1. INVESTIGATE (report before acting): list the account's services,
   disks, and env groups via the API. For each priori-era service:
   what runs there, branch, disk size/contents indications, plan
   (cost), last deploy. State whether canonical match data already
   lives on a reachable disk and how the old service was provisioned
   with data (the answer determines the data path below).
2. DECIDE per the standing ruling and record which branch fired:
   REUSE-AND-RENAME an existing service (rename to
   entrelineas-film-room, repoint to branch codex/afl08-passport-loop,
   new start command per render.yaml, keep the disk) IF the disk
   carries usable data and repointing is clean; otherwise CREATE the
   blueprint service fresh. Either way the result must match
   render.yaml's intent; flag any divergence.
3. CONFIGURE env via API: TQE_PUBLIC_MODE=1,
   WORKBENCH_HERMES_ENABLED=0,
   DEMO_ACCESS_TOKEN=a0d3420ff73834135a4fa5e62cf1177b,
   TQE_EXECUTION_WORKERS, TQE_NODE_CACHE_ROOT per render.yaml.
4. PROVISION data + warm caches (the demo-bundle machinery; reuse the
   old service's data source if step 1 found one). Idempotent,
   hash-verified.
5. DEPLOY, wait for live, then run the COMMITTED oracle from this
   machine against the live URL (no --demo-token; asks are disabled
   and the gate check must pass on ASKS_DISABLED). Commit oracle
   output as R-AZ evidence with the live URL in the report.

## Deliverables
Investigation report (step 1 findings), the decision record (which
branch fired and why), provisioning evidence, live URL + oracle PASS
output, stage-committed report, full-suite table on the committed
tree (code changes expected to be minimal-to-none; if none, say so).

## Out of scope
Hermes-on-server; DNS/custom domain; retiring old services (owner);
enabling live asks publicly (owner decision after gallery validates).

## Acceptance
Leg zero fence-diff; oracle PASS against the LIVE URL reproduced by
the director from this machine; adversarial review of the
investigation's honesty (services enumerated vs. what the API
actually returns).
