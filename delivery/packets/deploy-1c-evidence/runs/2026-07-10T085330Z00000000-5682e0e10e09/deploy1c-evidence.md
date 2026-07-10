<!-- evidence_metadata: {"git_branch":"packet/deploy-1c","git_commit":"ae440bc37d7afde48dd8454ee96ef91fec3a640e","git_tree":"6e7be55cc5583f716eab80e11eb543488e2901db","oracle_path":"delivery/oracles/DEPLOY-1C/gallery_ready.py","oracle_sha256":"a3ef8770f86fea8762ace34a8675f3e9410809d77b68837b4e3d450a10f03d3c","packet_base":"9eef466","produced_by":"scripts/packets/deploy1c_evidence.py","producing_script_sha256":"5682e0e10e09652421b590b6ff7ff57ee5fe26e44d3e9cfc1de3a44e5b1c0614","run_dir":"delivery/packets/deploy-1c-evidence/runs/2026-07-10T085330Z00000000-5682e0e10e09","run_started_at":"2026-07-10T08:53:30+00:00","schema_version":"deploy1c.evidence_metadata.v1"} -->
# DEPLOY-1C Evidence

| Verification | Status | Duration ms | Tests | Evidence |
| --- | --- | ---: | ---: | --- |
| Focused Python | PASS | 3955.69 | 20 | `delivery/packets/deploy-1c-evidence/runs/2026-07-10T085330Z00000000-5682e0e10e09/focused-python-tests.txt` |
| Focused Film Room UI | PASS | 159.57 |  | `delivery/packets/deploy-1c-evidence/runs/2026-07-10T085330Z00000000-5682e0e10e09/focused-film-room-ui-test.txt` |
| UI typecheck | PASS | 2051.768 |  | `delivery/packets/deploy-1c-evidence/runs/2026-07-10T085330Z00000000-5682e0e10e09/ui-typecheck.txt` |
| Fenced gallery oracle + replay | PASS | 86.783 |  | `delivery/packets/deploy-1c-evidence/runs/2026-07-10T085330Z00000000-5682e0e10e09/gallery-ready-oracle.txt` |
| Full Python suite | PASS | 546701.404 | 590 | `delivery/packets/deploy-1c-evidence/runs/2026-07-10T085330Z00000000-5682e0e10e09/full-python-suite.txt` |
| Leg zero | PASS |  |  | packet base `9eef466` |

## Gallery proof

- Bootstrap state: `True`.
- No plan execution: `True`.
- Replay lazy before request: `True`.
- Replay frames served: `101`.
- Bootstrap: `delivery/packets/deploy-1c-evidence/runs/2026-07-10T085330Z00000000-5682e0e10e09/film-room-bootstrap.json`.
- Replay: `delivery/packets/deploy-1c-evidence/runs/2026-07-10T085330Z00000000-5682e0e10e09/film-room-replay-window.json`.
- Memory-read limitation: `FLAGGED_NON_BLOCKING`; returned Arrow tables are window-filtered, but full-half Parquet row groups may still be scanned/decoded.
- Semantics deviation: `RATIFICATION_REQUESTED`; certified tables omit chain source records, so bootstrap items are honestly labelled partition previews, not R-BB chain moments.
