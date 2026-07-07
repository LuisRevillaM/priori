<!-- evidence_metadata: {"git_branch":"packet/deploy-1","git_commit":"2978bd3e1fd515e023b3126801bbc6925c9d4ff5","git_tree":"967754322adebe301b0dfff97f664ee67c450263","oracle_path":"delivery/oracles/DEPLOY-1/deploy_smoke.py","oracle_sha256":"9aead6611095a41c9ddcf9b7525dd8fcb85c186d20add691a7f6dbbc5e4b8f3f","produced_by":"src/tqe/verification/deploy1_evidence.py","producing_script_sha256":"055df6fd620c63fa88fa432821ada184c68e3ece835e65ed1741c9eb6e98cc86","run_dir":"delivery/packets/deploy-1-evidence/runs/2026-07-07T195358Z00000000-055df6fd620c","run_started_at":"2026-07-07T19:56:02+00:00","schema_version":"deploy1.evidence_metadata.v1"} -->
# DEPLOY-1 Evidence

| Area | Status | Duration ms | Output |
| --- | --- | ---: | --- |
| DEPLOY-1 Python | PASS | 3249.56 | `delivery/packets/deploy-1-evidence/runs/2026-07-07T195358Z00000000-055df6fd620c/focused-python-tests.txt` |

| Oracle mode | Status | Duration ms | Output | Subscription billed |
| --- | --- | ---: | --- | --- |
| without token | PASS | 75.066 | `delivery/packets/deploy-1-evidence/runs/2026-07-07T195358Z00000000-055df6fd620c/oracle-without-token.txt` | False |
| with token | PASS | 120204.815 | `delivery/packets/deploy-1-evidence/runs/2026-07-07T195358Z00000000-055df6fd620c/oracle-with-token.txt` | True |

Cache provenance: The local public-mode service used run-local TQE_RUNTIME_ROOT, TQE_CACHE_ROOT, and TQE_NODE_CACHE_ROOT under /private/tmp scratch named for this evidence run. The with-token oracle may invoke Hermes live through the ChatGPT subscription; the without-token oracle must be answered by the public gate before any model call.
