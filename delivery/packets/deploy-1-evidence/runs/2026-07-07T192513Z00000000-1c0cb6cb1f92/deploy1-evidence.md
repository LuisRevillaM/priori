<!-- evidence_metadata: {"git_branch":"packet/deploy-1","git_commit":"c8921b0a27db381403459298c62d40258cd76290","git_tree":"0ec627fb29924d3f2235c3b8db8985eba8490c05","oracle_path":"delivery/oracles/DEPLOY-1/deploy_smoke.py","oracle_sha256":"9aead6611095a41c9ddcf9b7525dd8fcb85c186d20add691a7f6dbbc5e4b8f3f","produced_by":"src/tqe/verification/deploy1_evidence.py","producing_script_sha256":"1c0cb6cb1f92637ffe365bd7e478b7fbb2b39dd0948999612bdc1a7a08fa7ae0","run_dir":"delivery/packets/deploy-1-evidence/runs/2026-07-07T192513Z00000000-1c0cb6cb1f92","run_started_at":"2026-07-07T19:35:20+00:00","schema_version":"deploy1.evidence_metadata.v1"} -->
# DEPLOY-1 Evidence

| Area | Status | Duration ms | Output |
| --- | --- | ---: | --- |
| DEPLOY-1 Python | PASS | 5407.276 | `delivery/packets/deploy-1-evidence/runs/2026-07-07T192513Z00000000-1c0cb6cb1f92/focused-python-tests.txt` |

| Oracle mode | Status | Duration ms | Output | Subscription billed |
| --- | --- | ---: | --- | --- |
| without token | PASS | 79.406 | `delivery/packets/deploy-1-evidence/runs/2026-07-07T192513Z00000000-1c0cb6cb1f92/oracle-without-token.txt` | False |
| with token | FAIL | 600216.073 | `delivery/packets/deploy-1-evidence/runs/2026-07-07T192513Z00000000-1c0cb6cb1f92/oracle-with-token.txt` | True |

Cache provenance: The local public-mode service used run-local TQE_RUNTIME_ROOT, TQE_CACHE_ROOT, and TQE_NODE_CACHE_ROOT under this evidence directory. The with-token oracle may invoke Hermes live through the ChatGPT subscription; the without-token oracle must be answered by the public gate before any model call.
