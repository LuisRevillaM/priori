# F2-0 Report — Capability Envelope Scaffolding

Branch: `packet/f2-0`  
Implementation commit: `4baafe3` (`Add F2 envelope scaffolding`)  
Protocol: local commit only; no push.

## Scope outcome

Implemented F2-0 scaffolding only:

- Added `src/tqe/runtime/envelope.py` with typed envelope dataclasses, evidence records, witness refs, an optional coverage-channel slot, legacy-signal envelope construction, and conformance checks.
- Added `src/tqe/runtime/capabilities/__init__.py` as the explicit dispatch registry metadata and migrated executor dispatch construction to that registry without moving implementations.
- Wired conformance checks into catalog-node execution only when `TQE_ENVELOPE_CONFORMANCE=warn`; default is `off`.
- Added `scripts/runtime/envelope_conformance_report.py` and `make envelope-conformance-report`.
- Added envelope, registry-completeness, boundary-freeze, and synthetic/report smoke tests.

No catalog declarations, primitive semantics, generated artifacts, frozen expectations, N1D artifacts, or semantic-registry files were changed.

## Signals survey

The envelope had to represent these current `state.signals` shapes:

- Declared episode-set outputs such as `episodes`, `anchors`, and relation `episodes`.
- Anchor-evaluation episode sets emitted as `anchor_evaluations` with paired `anchor_evaluations_records`.
- Frame signals emitted as `FrameSignal`, including enum status signals and numeric scalar-over-frame signals.
- Output record sidecars using `<output>_records`; legacy predicate facts using `predicate_facts`.
- Legacy metadata keys such as `source_results`, `summary`, `anchor_source`, and `candidate_evaluations_records`.

The envelope can represent all of these without loss. Legacy metadata remains metadata, not declared output channels. Coverage is present as an optional slot only; F2-0 does not change coverage semantics.

## Shadow conformance report

Command exercised:

```sh
make envelope-conformance-report
```

Output path: `artifacts/check-runs/envelope-conformance-report.json` (gitignored check-run artifact).

Representative plans:

- `config/query-plans/high_bypass_completed_pass.experimental.v1.json`
- `config/query-plans/q6_throw_in_first_action_under_pressure.experimental.v1.json`

Findings are warnings/report data only; they do not fail execution in F2-0.

| Capability | Findings |
|---|---:|
| `action_event_anchor` | 34 |
| `controlled_line_break_episode` | 34 |
| `controlled_pass_episode` | 1123 |
| `multi_line_model` | 34 |
| `opponents_bypassed_by_action` | 1132 |
| `pressure_on_carrier` | 34 |
| `relative_position_to_line` | 68 |
| `tracking_quality` | 34 |
| `velocity` | 51 |
| **Total** | **2544** |

Finding shape: current legacy emissions carry more evidence fields than the catalog declarations expose. This is the expected F2 input, not a runtime behavior change.

## Frozen shared-code leak allowlist

`tests/test_executor_boundaries.py` freezes the current capability-name mentions in shared executor code, excluding bodies of `primitive_*` and `relation_*` implementations. The allowlist is intentionally exact-line based so future packets can only shrink or explicitly amend it.

Frozen names:

- `acceleration`
- `join_episode_sets`
- `lane_occupancy`
- `local_number_relation`
- `marking`
- `relation_destination_entry`
- `relation_destination_entry_classification`
- `relative_position_to_line`
- `time_to_arrival`
- `velocity`

The destination-entry entries are the audit-named shared-code leaks. The import/helper entries are existing capability-family code that still lives outside implementation bodies until later extraction packets move the families out of `executor.py`.

## Noop debt list

Pinned V10 debt in `LEGACY_NOOP_CAPABILITIES`:

- `wide_channel_dwell`
- `shift_persistence`
- `robust_team_width`
- `analysis_rate`

These remain registered to `primitive_noop` for F2-0 and are explicitly acknowledged by the registry test. They are not catalog capabilities and are deferred to F2-X.

## Zero-drift proof

Pre-change baseline gate transcript:

- `/tmp/f2-0-baseline-gates.log`
- SHA-256: `3e4b4cd35122700ce07d56936b4922b0feb39edd8a9e102144d6f4f204e3d68a`

Committed-tree after transcript:

- `/tmp/f2-0-after-committed-gates.log`
- SHA-256: `37e42d303c9671c0a199ea9a6ecdcf6152caff266e1c98bb15428238a138524c`

Raw transcripts are not byte-identical because unittest timing lines differ. Stable verification result fields are unchanged.

| Gate | Result | Stable proof |
|---|---|---|
| `scp-0-verify` | PASS | SCP-0 status counts unchanged; runtime bound capabilities remain 44. |
| `afl-passport-verify` | PASS | generated/stored passport hash unchanged: `03579912782c89be0ec757ee0c0607e307ba734b4c3d59a1b4593f9fa7030b3e`. |
| `afl-09a-verify` | PASS | frozen expectation hashes unchanged: `b114d793eba25a481b0e2563abd1430f79cd371bb69cc1c8d54a8d77be83816f`, `264f0cd1223f9dfa259904a847dfe89d63a7a8cb47ab2aa3980d0cc99f55d72a`. |
| `n1d1-verify` | PASS | `attestation_status=VERIFIED`, no blocking reasons. |
| `afl-substrate-q4-verify` | PASS | bound plan hash `b467bd8f1a87361d6680b285a836a0990fd1694091e1cad162baaed2af65adcd`; result signature `89cc48842fc6b9852fc6941fc56e2147e524de7a2d3ae7fe718d29c96d382199`. |
| `afl-substrate-q6-verify` | PASS | bound plan hash `3f1fe004bc16bb029f82635a80f26c2a2e8865de4ec7d1490d943fb1c36c81b5`; result signature `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`. |

Tracked git state was clean for the committed-tree after run. A pre-existing unrelated untracked file remains: `docs/visual-explainers/tactical-compilation-concept.png`.

## Full-suite table

| Command | Result |
|---|---|
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_envelope tests.test_executor_boundaries` | PASS, 9 tests in 3.237s |
| `make envelope-conformance-report` | PASS, report written, 2544 shadow findings |
| `make scp-0-verify afl-passport-verify afl-09a-verify n1d1-verify afl-substrate-q4-verify afl-substrate-q6-verify` | PASS on committed tree |
| `make test` | PASS, 346 tests in 343.601s on final committed tree |

The `make test` subprocess completed successfully; a shell wrapper used for tailing the saved log then failed on zsh's readonly `status` variable after the suite had already reported `OK`.
