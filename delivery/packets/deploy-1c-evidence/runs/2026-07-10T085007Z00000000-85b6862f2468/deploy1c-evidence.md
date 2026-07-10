<!-- evidence_metadata: {"git_branch":"packet/deploy-1c","git_commit":"d495ea998fe29259e9d4d538f2ba66416011bc70","git_tree":"394049064ded24e42ced2247514e22d916b4b247","oracle_path":"delivery/oracles/DEPLOY-1C/gallery_ready.py","oracle_sha256":"a3ef8770f86fea8762ace34a8675f3e9410809d77b68837b4e3d450a10f03d3c","packet_base":"9eef466","produced_by":"scripts/packets/deploy1c_evidence.py","producing_script_sha256":"85b6862f2468ff0621e3162123ed371983897568d432f77f39e4eddc12ca55a9","run_dir":"delivery/packets/deploy-1c-evidence/runs/2026-07-10T085007Z00000000-85b6862f2468","run_started_at":"2026-07-10T08:50:07+00:00","schema_version":"deploy1c.evidence_metadata.v1"} -->
# DEPLOY-1C Evidence

| Verification | Status | Duration ms | Tests | Evidence |
| --- | --- | ---: | ---: | --- |
| Focused Python | PASS | 5049.128 | 20 | `delivery/packets/deploy-1c-evidence/runs/2026-07-10T085007Z00000000-85b6862f2468/focused-python-tests.txt` |
| Focused Film Room UI | PASS | 269.062 |  | `delivery/packets/deploy-1c-evidence/runs/2026-07-10T085007Z00000000-85b6862f2468/focused-film-room-ui-test.txt` |
| UI typecheck | PASS | 2726.673 |  | `delivery/packets/deploy-1c-evidence/runs/2026-07-10T085007Z00000000-85b6862f2468/ui-typecheck.txt` |
| Fenced gallery oracle + replay | PASS | 195.81 |  | `delivery/packets/deploy-1c-evidence/runs/2026-07-10T085007Z00000000-85b6862f2468/gallery-ready-oracle.txt` |
| Full Python suite | FAIL | 56702.645 | 558 | `delivery/packets/deploy-1c-evidence/runs/2026-07-10T085007Z00000000-85b6862f2468/full-python-suite.txt` |
| Leg zero | PASS |  |  | packet base `9eef466` |

## Gallery proof

- Bootstrap state: `True`.
- No plan execution: `True`.
- Replay lazy before request: `True`.
- Replay frames served: `101`.
- Bootstrap: `delivery/packets/deploy-1c-evidence/runs/2026-07-10T085007Z00000000-85b6862f2468/film-room-bootstrap.json`.
- Replay: `delivery/packets/deploy-1c-evidence/runs/2026-07-10T085007Z00000000-85b6862f2468/film-room-replay-window.json`.
- Memory-read limitation: `FLAGGED_NON_BLOCKING`; returned Arrow tables are window-filtered, but full-half Parquet row groups may still be scanned/decoded.
- Semantics deviation: `RATIFICATION_REQUESTED`; certified tables omit chain source records, so bootstrap items are honestly labelled partition previews, not R-BB chain moments.
