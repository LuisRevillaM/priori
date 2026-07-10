# DEPLOY-1B Review: ACCEPT-WITH-FIXES (fixes ratified at merge)

Reviewed 2026-07-10 at 6b483f4 — the Sol executor's first packet.
Leg zero: fence diff clean. Suite: director-run, green (the seven
sandbox-denied socket tests in the executor's run pass here).
Own-hands: every investigation claim re-verified against the live
Render API — name, plan, branch, auto-deploy, URL all as reported.

The reuse ruling fired correctly on real evidence: exactly one
repo-attached service existed, its 20GB disk already carried
manifest-verified demo data, so rename-and-keep beat re-provisioning.
Two defects honestly blocked the PASS and both resolutions are
RATIFIED here: (1) the starter-plan OOM — the already-paid standard
plan restored via API was the smallest safe deviation; render.yaml is
amended to match at merge so the blueprint tells the truth; (2) the
Docker image missing the flagship plans — the packaging repair is
correct and reaches Render via the director's push, which is the
never-push law operating as designed, not a workaround.

Exemplary honesty notes for the record: the executor preserved its
DNS-blocked oracle run as failure evidence rather than presenting it
as product evidence, and refused to claim acceptance it could not
verify. The live-URL oracle PASS — the packet's true acceptance — is
executed by the director post-push and appended below.

Residuals ledgered: the Render URL slug keeps the old name (slugs do
not follow renames); custom domain or slug migration is an owner
decision. Executor sandbox cannot bind sockets or resolve DNS —
future deploy packets state this expectation up front.
