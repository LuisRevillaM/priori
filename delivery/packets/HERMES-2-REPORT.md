# HERMES-2 Report — GPT-5.6 Sol measured before default selection

Branch: `packet/hermes-2`

Frontier base: `ab28c64`; final frontier integration: merge of `2829d1e` in
`f89a8126eec6931273af2223fdca3b8358b22dcd`

Status: `DELIVERED-with-evidence` — the fourth committed-tree landing is valid
under producer-v2 access rules and passes the default-flip gate at `9 / 15`.

No push was performed.

## Resolution

The final committed-tree GPT-5.6 Sol landing is `9 PASS / 6 FAIL / 15 total`
against the frozen DEV set. Relative to the standing GPT-5.5 result (`7 / 15`),
two cases became newly passing, no case became newly failing, and every
remaining failure is an unchanged genuine compiler/synthesis gap. Producer v2
found zero model-access failures and requires no wrong-answer review. The
packet's default-flip gate therefore passes and the flip **STANDS**.

The compiler default, harness default, and canonical Hermes profile now select
`openai-codex/gpt-5.6-sol` at `xhigh`.  `max` is not accepted by installed
Hermes, so `xhigh` is the actual ceiling.

Two later landing attempts are retained but are **not model measurements**:
OAuth access failed partway through the first and before every case in the
second.  The first evidence-producer version exposed an oracle gap by counting
access failures as ordinary DEV failures; the producer now invalidates the
whole comparison whenever any model-access failure appears.

A third committed-tree landing attempt on merged frontier `71f4794` is also
retained and invalid. Producer v2 classified all 15 cases as
`model_access_failure`: the canonical `~/.hermes-priori` route reported
`No Codex credentials stored`. The raw `0 / 15` is access evidence only and is
not presented as compiler capability.

The fourth landing is the first access-valid post-flip landing. It was produced
from committed merge tree `f89a812` after integrating frontier `2829d1e`, on
`openai-codex/gpt-5.6-sol` at `xhigh`, through ChatGPT subscription billing
with an empty fallback chain.

## Leg Zero And Route

| Check | Result |
| --- | --- |
| Initial packet frontier | `ab28c64a4aaaf5cb81ddab74e44e846e8210216d` |
| Final merged frontier | `2829d1ed59b29efaec11f8870dce8b5e1523c31b` via merge commit `f89a8126eec6931273af2223fdca3b8358b22dcd` |
| Frozen DEV SHA-256 | `07a10d76b1f3322e94131090068f19157975fbea65aefbebdb8e17aba2da4b7a` — PASS |
| Leg-zero harness SHA-256 | `70ba3b0723b118be0c8c3e7420510831b1487d5c15a2c2337b74089d3b1a905f` — PASS |
| DEV edits | None |
| Landing harness delta | Exactly one authorized default string: `gpt-5.5` to `gpt-5.6-sol` |
| Blind-set access | None; blind contents remained sealed |
| Provider | `openai-codex` |
| Fallback chain | Empty |
| Billing | ChatGPT subscription; no metered provider invoked |
| Hermes home | `/Users/luisrevilla/.hermes-priori` |
| Hermes version | `0.17.0 (2026.6.19)`, upstream `2a58fee1` |
| `reasoning_effort: max` | Rejected by installed Hermes parser |
| Selected effort | `xhigh` |

The packet-authoring commit `108ef86` is one commit beyond the mandated
frontier and is not in this branch.  I read that immutable packet before
branching, then created `packet/hermes-2` exactly at `ab28c64`; no packet text
was imported into the builder diff.

## Effort-Wiring Finding And Repair

Investigation found that the repository's custom Hermes product shim passed
`max_tokens` but did not pass `agent.reasoning_effort` into `AIAgent`.  The
transport therefore used its implicit `medium` effort even though the
canonical profile and prior report said `xhigh`.

Consequences:

- The standing `7 / 15` GPT-5.5 artifact remains the director-mandated
  historical baseline, but it is not an actual xhigh run.
- Measuring Sol without repair would have repeated the same false effort
  label.
- `src/tqe/workshop/hermes_invocation.py` now resolves the configured effort,
  rejects unknown values instead of silently demoting them, and passes the
  accepted configuration into every product invocation.
- Regression tests prove `xhigh` reaches `AIAgent` and `max` is rejected.

This is general invocation wiring; it does not inspect a DEV case or alter
compiler prompts, expectations, or synthesis behavior.

## Live Model-ID Probe

The committed R-AZ producer made one bridge call with
`HERMES_SCP2_2_MODEL=gpt-5.6-sol` through the canonical profile.

| Field | Result |
| --- | --- |
| OAuth/model accepted | PASS |
| Requested route | `openai-codex/gpt-5.6-sol` |
| Transcript route | `openai-codex/gpt-5.6-sol` |
| Outcome | `understood_but_not_expressible` |
| Gap | `BODY_ORIENTATION` |
| Elapsed | `15.334s` |

This closed model-ID acceptance without using a metered fallback.

## Final Committed-Tree DEV Headline

Evidence run:
`delivery/packets/hermes-2-evidence/runs/2026-07-13T081029Z00000000-landing-gpt-5.6-sol-3c11332369e1`

| Field | Historical GPT-5.5 | Final GPT-5.6 Sol landing |
| --- | ---: | ---: |
| PASS | 7 | 9 |
| FAIL | 8 | 6 |
| Total | 15 | 15 |
| Elapsed | `761.554s` | `1495.149s` |
| Long-run flag | true | true |
| Model-access failures | 0 | 0 |
| Model-output-shape failures | 0 | 0 |
| Truncation failures | 0 | 0 |

The final landing was `733.595s` / `96.3%` slower than the historical run. The
semantic gain is two net passes; the ask-path latency concern remains open.

## Final Per-Case Comparison

| Case | GPT-5.5 | Sol | Transition | 5.5 sec | Sol sec | Sol failure attribution |
| --- | --- | --- | --- | ---: | ---: | --- |
| `dev_same_meaning_controlled_pass` | FAIL | FAIL | unchanged fail | 47.931 | 100.065 | genuine gap |
| `dev_same_meaning_sequence_rate` | FAIL | FAIL | unchanged fail | 188.228 | 235.291 | genuine gap |
| `dev_same_meaning_line_break_support` | FAIL | FAIL | unchanged fail | 89.993 | 148.591 | genuine gap |
| `dev_changed_rate_vs_count` | FAIL | PASS | **newly passing** | 117.798 | 149.831 | — |
| `dev_changed_controlled_vs_bypass` | PASS | PASS | unchanged pass | 40.463 | 55.363 | — |
| `dev_known_possession_corridor` | FAIL | FAIL | unchanged fail | 22.656 | 109.962 | genuine gap |
| `dev_known_high_bypass` | PASS | PASS | unchanged pass | 24.712 | 64.958 | — |
| `dev_known_first_time_relay` | FAIL | FAIL | unchanged fail | 25.017 | 88.293 | genuine gap |
| `dev_novel_sequence_rate` | PASS | PASS | unchanged pass | 71.564 | 132.277 | — |
| `dev_refusal_body_orientation` | PASS | PASS | unchanged pass | 6.326 | 5.673 | — |
| `dev_refusal_pass_probability` | PASS | PASS | unchanged pass | 5.932 | 9.205 | — |
| `dev_refusal_player_intent` | PASS | PASS | unchanged pass | 6.441 | 77.972 | — |
| `dev_refusal_video_modality` | PASS | PASS | unchanged pass | 5.520 | 80.650 | — |
| `dev_clarification_support_definition` | FAIL | PASS | **newly passing** | 76.596 | 116.385 | — |
| `dev_clarification_distance_threshold` | FAIL | FAIL | unchanged fail | 32.377 | 119.918 | genuine gap |

Transition totals: `2 newly passing`, `0 newly failing`, `7 unchanged pass`,
`6 unchanged fail`. Producer v2 reports `run_valid_for_model_comparison=true`,
`model_access_closed=true`, and no cases requiring wrong-answer review.

## Additional Equal-Effort Control

Because the historical result was not actually xhigh, I ran GPT-5.5 once on
the repaired same tree and exact harness invocation.  Raw count was `6 / 15`
in `2346.108s`, but four cases suffered model-access timeouts.  It is therefore
**not admissible as a semantic model comparison** and is not used to justify
the default flip.

Evidence run:
`delivery/packets/hermes-2-evidence/runs/2026-07-10T082951Z00000000-control-gpt-5.5-7c9ae363d70d`

Access-invalid cases: `dev_same_meaning_sequence_rate`,
`dev_same_meaning_line_break_support`, `dev_changed_rate_vs_count`, and
`dev_novel_sequence_rate`.

## Owner-Phrasing Spot-Check — CAP-1 Scope

Sentence:

> When the ball carrier is pressed and no support arrives, how often does his
> team keep the ball?

| Field | Result |
| --- | --- |
| GPT-5.5 baseline | Honest refusal (packet baseline) |
| Final Sol attempt | No outcome; `TimeoutExpired` at the committed budget |
| Elapsed | `180.291s` |
| Route | `openai-codex/gpt-5.6-sol`, subscription, `xhigh`, no fallback |
| Expression bind | Not applicable |
| CAP-1 implication | The owner phrasing remains open as a latency/capability gap despite restored model access |

The spot-check is not a gate and did not affect the valid 9/15 landing. Its
append-only evidence is `owner-phrasing.json` beside the final landing run.

## Defaults Selected On Evidence

| Surface | Final value |
| --- | --- |
| `src/tqe/semantic_compiler/hermes_nl.py` | `DEFAULT_MODEL = "gpt-5.6-sol"` |
| `scripts/scp2_2/eval_harness.py` | fallback model `gpt-5.6-sol` |
| `~/.hermes-priori/config.yaml` | provider `openai-codex`, model `gpt-5.6-sol`, effort `xhigh` |

The post-measurement harness change is exactly the packet-authorized default
string.  Frozen DEV content is unchanged.

## Landing Attempts And Oracle Flag

| Run | Raw count | Valid comparison? | Finding |
| --- | ---: | --- | --- |
| `2026-07-10T091005Z...-landing...` | 1/15 | No | OAuth failed after nine successful calls; eleven DEV cases contain `HermesNLAccessError` |
| `2026-07-10T094003Z...-landing...` | 0/15 | No | Recovered Codex-CLI token was revoked; all 15 cases invalidated by producer v2 |
| `2026-07-13T004027Z...-landing...` | 0/15 | No | All 15 cases invalidated by producer v2 because the canonical Hermes home had no stored Codex credential |
| `2026-07-13T081029Z...-landing...` | **9/15** | **Yes** | `COMPLETE`; zero access failures, two newly passing, zero newly failing, six unchanged genuine gaps |

The committed harness exposes compiler exceptions but not every underlying OAuth
reason. Producer v1 therefore exposed a real oracle gap by treating access
failures as ordinary DEV failures. Producer v2 keeps the structurally necessary
`model_access_failure` category and invalidates the entire run whenever one
appears. The three invalid attempts remain immutable access evidence and are
never presented as capability measurements.

The fourth run closes that flag: its fence passed, its only harness delta is the
authorized default-model flip, its route remained
`openai-codex/gpt-5.6-sol` / ChatGPT subscription / `xhigh` with no fallback,
`run_valid_for_model_comparison=true`, `model_access_closed=true`, and no case
requires wrong-answer review. The flip stands.

The owner-phrasing call then ran separately through the committed producer
function and timed out at `180.291s`; that is preserved as a CAP-1 latency
finding, not used to invalidate the completed DEV landing.

## Verification — Final Full-Suite Table

| Check | Result | Notes |
| --- | --- | --- |
| `TMPDIR=/private/tmp PYTHONPATH=src:. .venv/bin/python -m unittest tests.test_hermes2_evidence tests.test_hermes_invocation tests.test_scp2_2_hermes_nl -v` | PASS | 24 tests in `0.438s`; producer-v2 access invalidation and `xhigh` transport wiring covered |
| `scripts/packets/hermes2_evidence.py --phase landing` on merge commit `f89a812` | PASS | Producer v2 `COMPLETE`; valid `9 / 15`, zero access failures, two newly passing, zero newly failing |
| Committed producer `model_call` owner spot-check | FINDING | `TimeoutExpired` at `180.291s`; non-gating CAP-1 latency/capability evidence |
| `TMPDIR=/private/tmp MPLCONFIGDIR=/private/tmp/priori-matplotlib-hermes2 PYTHONPATH=src:. make test` | PASS | 603 tests in `625.877s`; attestation `VERIFIED`, blocking reasons `[]` |
| `TMPDIR=/private/tmp npm --prefix apps/workbench-alpha run test:unit` | PASS | Eight frontend unit modules |
| `TMPDIR=/private/tmp npm --prefix apps/workbench-alpha run build` | PASS | Contract generation, TypeScript, and Vite build |
| Frozen DEV SHA-256 | PASS | `07a10d76b1f3322e94131090068f19157975fbea65aefbebdb8e17aba2da4b7a` |
| Harness fence | PASS | Leg-zero bytes plus only the authorized default-model string change |
| `git diff --check` | PASS | Report and evidence handoff tree has no whitespace errors |

Earlier access-invalid landings and the earlier socket-blocked suite remain
preserved in append-only evidence and git history; no test or DEV case was
altered to obtain this final green run.

## R-AZ Evidence

The producer is `scripts/packets/hermes2_evidence.py`.  It requires its own
committed bytes and a clean tracked tree, refuses to overwrite run directories,
self-stamps script/commit/tree identities, pins the frozen DEV and leg-zero
harness hashes, records the exact route/billing/effort configuration, invokes
the committed harness, retains raw completions and latency, and emits the full
comparison table.

All three access-invalid landing runs remain append-only evidence; none was
deleted or rewritten after the oracle defect was found. The final valid run is
`delivery/packets/hermes-2-evidence/runs/2026-07-13T081029Z00000000-landing-gpt-5.6-sol-3c11332369e1`.
It was produced from merge commit `f89a8126eec6931273af2223fdca3b8358b22dcd`
and carries the frozen DEV hash, committed producer hash, exact route, full
per-case observations, producer-v2 validity verdict, and the subsequent
append-only owner-phrasing timeout evidence.

## Deviations

| Deviation | Reason | Disposition |
| --- | --- | --- |
| Added a fresh GPT-5.5/xhigh control | Historical 7/15 was mislabeled xhigh because product shim dropped configured effort | Preserved, but excluded from semantic comparison after four access failures |
| Repaired product effort wiring before Sol measurement | Measuring without it would falsely claim xhigh again | General fix plus mutation-resistant regression tests |
| Added `model_access_failure` outside the packet's three semantic failure classes | Live 401/timeout failures are neither genuine compiler gaps, output shape, nor truncation | FLAGGED oracle mismatch; access now invalidates whole run |
| Preserved evidence logs with trailing tab columns | Committed harness prints an empty final TSV field for passing rows | R-AZ bytes kept immutable; source diffs remain `git diff --check` clean |
| Earlier full suite was not green in executor sandbox | Local socket bind was prohibited in that run | Exact seven environment errors remain reported; no test alteration |
| Used `/private/tmp/priori-hermes2-attempt4-20260713` clone route | Main workspace denied `.git/index.lock` on three checkout attempts | Merge, evidence, report, tests, and commits remain isolated on `packet/hermes-2`; clone path and SHAs disclosed |
| Invoked committed `model_call` directly for final owner spot-check | Landing phase intentionally does not repeat the non-gating owner call | Same committed function and 180-second timeout; one-write JSON preserved beside landing evidence |

## Appended Commits

| Commit | Summary |
| --- | --- |
| `c285176` | Wire configured Hermes reasoning effort into product invocations; add committed R-AZ producer |
| `b4c4383` | Record clean Sol measurement evidence |
| `9c10010` | Record equal-effort GPT-5.5 control evidence |
| `0546e0d` | Select GPT-5.6 Sol in committed compiler/harness defaults |
| `e3ea8d6` | Preserve first auth-invalid landing run |
| `04f40ff` | Make model-access failures invalidate comparisons |
| `fa00620` | Record second access-invalid landing evidence |
| `c49505e` | Merge frontier `71f4794` for the third landing |
| `138dde3` | Preserve third access-invalid landing evidence |
| `f89a812` | Merge final frontier `2829d1e` for the fourth landing |

## Residual Risk

- The valid Sol landing is materially slower than the historical baseline.
- The owner phrasing timed out at 180 seconds and remains a CAP-1 gap.
- Six of fifteen frozen DEV cases remain genuine compiler/synthesis gaps.
- Hermes OAuth pool health can change during a long sequential evaluation;
  producer v2 prevents false semantic scoring but does not renew credentials.
