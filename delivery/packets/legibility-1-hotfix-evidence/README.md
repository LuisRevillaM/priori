# LEGIBILITY-1 hotfix evidence

Producer: `scripts/packets/legibility1_hotfix_evidence.py`

Source cache bundle:
`artifacts/deploy-2/2026-07-10T174719.190195Z-c79f8e177bb9/stage/cache`
(four v1 fragments, 115 away counterattack chain descriptors, four durable
execution caches).

The container was fenced with `--memory=2g --memory-swap=2g` and
`WORKBENCH_PREWARM_FILM_ROOM=0`. The source cache was copied with hard links to
a fresh `/private/tmp` proof root so the committed bundle was not mutated.

## Attempt 1 — preserved failure

The first production-image run exited 1, was not OOM-killed, and peaked at
94,986,240 bytes. It exposed two independent deployment defects:

- the image omitted the LEGIBILITY-1 meaning-expression file, so the
  counterattack certified prewarm never reached its success event; and
- the old hydration shards recorded an absolute `/app/...` plan path while the
  rebuild initially proposed the repository-relative spelling, producing an
  honest `Conflicting Film Room hydration shard` refusal.

The empty `result.json` is intentional: the producer never reached its PASS
document. `stderr.log` and `container-state.json` preserve the failure.

## Final — canonical PASS

The final run used the exact current `app_service.py` and committed meaning
expression mounted into the production image while the amended Dockerfile
image was building. It exited 0, was not OOM-killed, migrated all four v1
fragments to v2, loaded no full fragile-retention payload, rebuilt 115 chain
descriptors, and reached `bootstrap_state=ready` with execution prewarm off.

- cgroup limit: 2,147,483,648 bytes (2,048 MiB)
- cgroup peak: 174,505,984 bytes (166.42 MiB)
- headroom: 1,973,977,664 bytes (1,881.58 MiB; 91.87%)

The concurrent full-suite and image-build load makes this the conservative
peak; an earlier isolated successful run peaked at 97,255,424 bytes.

The amended production image subsequently built as
`sha256:c79d8b28b825590a09e9d9aa1ce27dcf2a699987ef06baf2d686548b48964688`.
An in-container check found the meaning expression at its required `/app`
path with SHA-256
`e59bd793b8096bb5a266cff7774da9fc0bf3788936400f96d4241b2debc1e1f1`.
The same producer then ran inside that image without source or asset mounts:
PASS, ready, 115 moments, 100,507,648-byte peak (95.85 MiB), and 1,952.15
MiB headroom.

## SHA-256

| File | SHA-256 |
| --- | --- |
| `attempt-1/container-state.json` | `ee2b183dcc8cd5a8e5c401ee27e91353baeb314fb7d94c4ae9ab229cae6578f2` |
| `attempt-1/memory_max_bytes` | `604fec38960d7c5bd3bd6c06ad8f4b42eac0bb30ea02d43518d0f9f11d5e131e` |
| `attempt-1/memory_peak_bytes` | `8380736be2d31539a4aded32d88047ff5d7e53df7e9866dc6b340326a580861d` |
| `attempt-1/result.json` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `attempt-1/stderr.log` | `444df1359d0ff36bf74eefa5767c41f1114eeb36cf8d47bb4c5a2894db84266a` |
| `final/container-state.json` | `8f59b74783a93f20950079c6ef17a26f0f4725e3db199695c8d97e81da0a39b8` |
| `final/full-suite.log` | `1532f0858da27a27291d74b5cbf8a898d12b5c5564352bb589884555b17df14b` |
| `final/memory_max_bytes` | `604fec38960d7c5bd6c06ad8f4b42eac0bb30ea02d43518d0f9f11d5e131e` |
| `final/memory_peak_bytes` | `263bf9b22e9251c8d4127c73450ddb0a3dea84d71d5b8e77b7907385a57c76a1` |
| `final/production-image-check.txt` | `64024c5e4a9e344e754527f60b11ee7df366e11260d0b7855815c490b0ae902f` |
| `final/result.json` | `87dd1bd14dcaad0e027600852c800e717fd3e756ff9e086ff462487dd6831e5f` |
| `final/stderr.log` | `379664f0dd73dcfc3cb06d92d711984f68bc9820536c1d83785961ba4c7d3cee` |
| `production-image/container-state.json` | `55f0301e66b5005fe6c9fca0b8c31ae130f82f4a64e09fe199ff8c0f81a83266` |
| `production-image/memory_max_bytes` | `604fec38960d7c5bd3bd6c06ad8f4b42eac0bb30ea02d43518d0f9f11d5e131e` |
| `production-image/memory_peak_bytes` | `5af24522cd7d7886585da1198d0a7e04c0fa8561305c07fcef9ba2a497ec1617` |
| `production-image/result.json` | `b492c7c265865c26bf33145eba104c02bb21635a6a9a5b28ab821095ad52a4d3` |
| `production-image/stderr.log` | `2ac33a6c5f6924bc1ecf5e4e12b45deea14aa0515206a9411b74e8477d6a3a3e` |
