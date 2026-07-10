# DEPLOY-2 Review — Round 1: STOP HONORED, ruling recorded

Reviewed 2026-07-10 at cbc7398. The mandatory 2GiB proof fired the
packet's stop condition: cache-hit prewarm peaked at 2048.004 MiB
(one page over the limit) and was OOM-killed; the executor made zero
Render mutations, refused to commit a crash-encoding config, and
preserved every failed run per R-AZ — including its own evidence
producer's defect (a wrong 4GiB cap, disclosed and removed). Stop
law followed exactly.

DIRECTOR'S RULING (the fork): Option A — lazy chain hydration within
the 2GB envelope (descriptors in RAM, chain payloads and replay
windows hydrated from disk per request). Zero new spend;
RAM-independence scales with the corpus where a bigger box only
postpones the wall. Option B (plan upgrade, ~2x monthly) remains the
owner-priced fallback if hydration proves unexpectedly deep. Round 2
executes A under the same fenced chain oracle and the same 2GiB
proof.

Round 2 attempt 1: killed by the subscription usage limit before its
first commit (budget event in STATE). Restarts clean when a lane
opens.

Process note, director's own: the STATE budget commit was made while
standing on this packet branch and an explicit push fast-forwarded
the frontier to it — honest content, skipped merge ceremony. Repaired
forward with this review; branch-check-before-governance-commit added
to the director's checklist.

---

# DEPLOY-2 Round 2: ACCEPTED — ship executed by the director

Reviewed 2026-07-10 at 5d9b182. The round survived two failovers (Sol
capacity → Terra tail) with the design commit (lazy hydration) from
Sol and the mechanical proof from Terra — the tier-routing law's
first real outing. Leg zero clean. The 2GiB proof: cache rebuild,
prewarm, bootstrap, and two hydrations inside --memory=2g with zero
OOM and three fenced local oracles green. The refreshed bundle
(658MB, hash-verified single-part) is on S3 with its manifest;
Terra's deploy attempt correctly 404'd against origin (never-push
law) and it restored prewarm=0 rather than leave a half-armed config
— exemplary boundary behavior on the cheap tier. The director now
merges, pushes, arms prewarm, deploys, and runs the live chain oracle
as the closing acceptance.
