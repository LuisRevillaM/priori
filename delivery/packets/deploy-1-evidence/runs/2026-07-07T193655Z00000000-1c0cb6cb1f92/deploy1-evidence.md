<!-- evidence_metadata: {"git_branch":"packet/deploy-1","git_commit":"cb4cf97bd08a381964c70f253808e0bc1ff68229","git_tree":"b44ac83ba68ce6b4f2b35a459ecc549163a71bf8","oracle_path":"delivery/oracles/DEPLOY-1/deploy_smoke.py","oracle_sha256":"9aead6611095a41c9ddcf9b7525dd8fcb85c186d20add691a7f6dbbc5e4b8f3f","produced_by":"src/tqe/verification/deploy1_evidence.py","producing_script_sha256":"1c0cb6cb1f92637ffe365bd7e478b7fbb2b39dd0948999612bdc1a7a08fa7ae0","run_dir":"delivery/packets/deploy-1-evidence/runs/2026-07-07T193655Z00000000-1c0cb6cb1f92","run_started_at":"2026-07-07T19:38:59+00:00","schema_version":"deploy1.evidence_metadata.v1"} -->
# DEPLOY-1 Evidence

| Area | Status | Duration ms | Output |
| --- | --- | ---: | --- |
| DEPLOY-1 Python | PASS | 3163.024 | `delivery/packets/deploy-1-evidence/runs/2026-07-07T193655Z00000000-1c0cb6cb1f92/focused-python-tests.txt` |

| Oracle mode | Status | Duration ms | Output | Subscription billed |
| --- | --- | ---: | --- | --- |
| without token | PASS | 74.459 | `delivery/packets/deploy-1-evidence/runs/2026-07-07T193655Z00000000-1c0cb6cb1f92/oracle-without-token.txt` | False |
| with token | PASS | 120139.682 | `delivery/packets/deploy-1-evidence/runs/2026-07-07T193655Z00000000-1c0cb6cb1f92/oracle-with-token.txt` | True |

Cache provenance: The local public-mode service used run-local TQE_RUNTIME_ROOT, TQE_CACHE_ROOT, and TQE_NODE_CACHE_ROOT under this evidence directory. The with-token oracle may invoke Hermes live through the ChatGPT subscription; the without-token oracle must be answered by the public gate before any model call.
