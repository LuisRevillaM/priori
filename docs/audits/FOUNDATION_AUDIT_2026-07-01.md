# Foundation Audit — 2026-07-01

Scope: the lower layers the general football-language compiler will stand on —
runtime core (`ir.py`, `binder.py`, `executor.py`, `values.py`,
`artifacts.py`), the pass/possession kinematic kernels, the spatial-relation
kernels of the AFL standard-library expansion, and the vocabulary-coherence
layer (catalog ↔ registry ↔ passports ↔ coverage map ↔ product claims).
Branch: `codex/afl08-passport-loop`. Method: four parallel deep reviews; all
HIGH-severity defects were **empirically reproduced** with synthetic geometry
or live regeneration, not just read off the code. This report is the
director-level synthesis and verdict; the four detailed sub-reports' findings
are folded in below with file:line references preserved.

## Director's verdict

**The architecture is right. The discipline that made it right has not been
applied evenly to the machinery that maintains it.**

Keep, unchanged, as foundations:

- The typed IR + fail-closed binder (`ir.py`, `binder.py`): strict models,
  typed units/enums/cardinality, issue-accumulating validation, structural
  DAG (cycles impossible), canonical hashing. This is genuinely good.
- The tri-state PASS/FAIL/UNKNOWN design and the claim-boundary doctrine
  ("product language cannot exceed evidence strength"). The doctrine is
  correct; the defects below are places the code fails its own doctrine, and
  they are findable precisely *because* the doctrine names them.
- The registry-as-source / passports-as-generated-projections design, and the
  server-side claim gate concept in `app_service.py` (genuinely fail-closed
  at its two narrow points).

Not sound yet, and blocking further vocabulary expansion:

1. **The executor is a god-module.** ~11k lines, 57 commits, 91% of all lines
   ever added still present; ~67% is per-capability code pasted inline behind
   an untyped `state.signals` dict convention. Capability names have leaked
   into the *shared* trace/evidence layer. Every new primitive compounds it.
2. **Tri-state fail-open paths are real and reproduced** in the executor,
   controlled-pass, one-touch, and corridor kernels (details below). Missing
   evidence can become FAIL — and in specific latent paths, PASS.
3. **The reconciliation machinery around the vocabulary is stale-green.**
   The checked-in SCP-0 parity report says PASS/35 capabilities/0 findings;
   a fresh regeneration says FAIL/44/51. Nine capabilities added on this very
   branch are executable and Hermes-authorable with no registry binding, no
   passport, no exposure policy. Verifiers regenerate-and-attest their own
   writes; artifacts are written on PASS only, so a FAIL leaves stale PASS
   evidence in place. There is no CI.
4. **`make test` is red on this branch: 277 tests, 11 failures** (verified
   directly during this audit; `test_scp0_semantic_registry` asserts a
   capability count three revisions old, 6/8 `test_coach_interpret_surface`
   tests fail against renamed claim ids). A gate that nobody re-runs against
   the moving tree is the same stale-green failure mode as the parity
   report.

The one-sentence summary: **the substrate primitives are mostly honest, the
binder is honest, the product gate is honest — but the connective tissue
(executor accretion, catalog declarations, parity artifacts, tests) has
drifted, and the system currently has no mechanism that forces it back into
truth.** That mechanism — not more primitives — is the next unit of work.

## Consolidated defect register

Severity key: **H** = wrong answers possible now; **M** = latent/one
composition away; **L** = hygiene.

### Tri-state violations (UNKNOWN discipline)

| # | Sev | Where | Defect |
|---|-----|-------|--------|
| T1 | H | `controlled_pass.py:410-481` | Reception window truncated by period end → FAIL (`reception_window_expired`) with zero frames inspected. A pass in flight at the whistle = "contradicted reception". Reproduced. |
| T2 | H | `controlled_pass.py:351-357` | Release check: any single non-missing far frame → FAIL `release_not_confirmed` even at 1/101 frames tracked; `max_missing_frame_ratio` never applied to release. SPEC declares this field PASS/UNKNOWN-only. Many of the case study's 84 `release_not_confirmed` FAILs are plausibly UNKNOWNs. Reproduced. |
| T3 | H | `relations.py:152-156, 331-449` | Corridor episodes silently bridge missing frames (PASS states adjacent across dropout → fabricated continuity); UNKNOWN frames also counted as failures for hysteresis close. Reproduced. |
| T4 | H | `relations.py:378` | `duration_seconds = pass_frame_count / rate` — off by one interval, wrong under flicker; drives witness selection and ≥0.8 s thresholds. |
| T5 | M | `executor.py:1921,1936` + `catalog.py:5532-5558` | `exists`/`count_at_least` live fallbacks: empty-because-uncovered episode set → FALSE. The "anchor-evaluations only" rule is enforced in the workshop layer, not binder/runtime. |
| T6 | M | `executor.py:1940-1947` | Coverage detection keys on `evaluation_status`/`relation_count` field names; newer kernels emit different names → `exists` over their `anchor_evaluations` returns PASS for every record incl. FAIL/UNKNOWN. Latent (shipped plans use `eq` on status), one Hermes composition away. |
| T7 | M | `executor.py:10419` | Episode-trace path: anchor uncovered by any window → FAIL with no UNKNOWN channel. |
| T8 | M | `one_touch.py:389-391`, `:210-214` | Relay-touch: 90% missing frames → FAIL; missing gameclock silently drops the 3 s pairing gate. |
| T9 | M | `relative_position_to_line.py:286-297` | Non-numeric coordinate → uncaught TypeError instead of UNKNOWN. Reproduced. |

### Wrong-answer geometry/kinematics

| # | Sev | Where | Defect |
|---|-----|-------|--------|
| G1 | H | `controlled_pass.py:484-501` | "Control" = proximity + near-nearest *teammate*; opponents invisible; no touch/settle evidence. Opponent 0.3 m from ball, receiver 2.4 m away, never touching → PASS. Reproduced. High-bypass reception endpoint inherits this. |
| G2 | H | `lane_occupancy.py:257,494-511` | Requirements count player-frames: 1 player × 2 frames satisfies "2 players in CENTRAL" → false PASS. Reproduced. |
| G3 | H | `controlled_line_break.py:263-272` | No temporal-order check: reception before release → PASS; line frame never tied to pass frames. Reproduced. |
| G4 | H | Two lane geometries | `lane_occupancy` (five equal 13.6 m lanes, asymmetric boundaries) vs `relations.destination_lane` (0.33/0.66 fractional): y=8.0 is "central" to one, RIGHT_HALF_SPACE to the other. Composed queries disagree with themselves. Reproduced. |
| G5 | M | `defensive_line.py:96-97,335` | GK-inclusion fail-open default (`goalkeeper_id=None` + `goalkeeper_id_known=True` accepted) skews the line. Reproduced. Also fabricated y=0.0 coordinates in evidence (`:352`). |
| G6 | M | `one_touch.py:272-277,383-388` | Dwell measured from release-adjacent proximity frame, not first arrival → ~1 s holds pass the ≤0.56 s "one-touch" bound. Nothing counts touches. Kinematic core untested. |
| G7 | M | `local_number_relation.py:192-201` | Player on both sides double-counted (1v1 → 2v1 PASS); no roster-uncertainty input unlike `defensive_line`. Reproduced. |
| G8 | M | `executor.py:1789-1791` | Live gt/gte/lte `truth_series` always computed with `>=` regardless of operator — wrong persisted-truth evidence for gt/lte. |
| G9 | M | `controlled_pass.py:634-637`, `one_touch.py:222` | Event filter `"Pass" in event_type` admits 76/639 (11.9%) set pieces vs SPEC `Play_Pass`; throw-ins judged by ground-plane control radius. |
| G10 | L | `high_bypass_pass.py:481`, `executor.py:96`, `controlled_pass.py:592` | Hardcoded 25 Hz / 100 ms alignment (SPEC says 250 ms param); frame-id-tick assumption undeclared. Correct for this corpus, silently wrong elsewhere. |

### Vocabulary drift & stale-green machinery

| # | Sev | Where | Defect |
|---|-----|-------|--------|
| V1 | H | SCP-0 parity | Checked-in report PASS/35/0 vs fresh regeneration FAIL/44/51. Nine capabilities (acceleration, cover_shadow, join_episode_sets, marking, off_ball_run, off_ball_run_type, set_piece_structure, space_region_generation, team_press) executable + Hermes-authorable with no registry binding/passport/exposure policy. Root cause: 10 newest AFL verifiers dropped the `generate_scp0_artifacts` call. |
| V2 | H | No CI; write-on-PASS | Parity/passport artifacts written only on PASS and consumed as evidence by `afl_gate.py`; a FAIL preserves stale PASS. `afl_passport.py:48-53` regenerates before comparing (self-attesting). `registry.lock.json` stale and never verified. |
| V3 | H | Test suite | Full suite on this branch: **277 tests, 11 failures** (verified 2026-07-01). `tests/test_scp0_semantic_registry.py:53-54` asserts bound==30 (live: 44); 6/8 `test_coach_interpret_surface` tests fail on renamed claim ids. |
| V4 | M | Catalog fictions | Declared-but-never-emitted evidence fields (`catalog.py:3983-4004` vs `executor.py:8708-8725`); module-vs-catalog default contradictions (support_arrival 1.0/0.0/5.0 vs 2.0/0.4/8.0; line-break/relative-position buffers 0.0 vs 0.5) masked by executor shadow defaults (`executor.py:10533-10552`) that bypass all catalog validation; undeclared result-driving knobs (`signed_lateral_shift`, one-touch windows). |
| V5 | M | Hermes exposure | Gated by a 4-name blocklist (`m1_2.py:107,763`), not the registry — unbound capabilities authorable by default. |
| V6 | M | Coverage map | 734/741 "supported" rows are asserted (`handwired`), only 7 compiler-reachable; support_angle/width/depth rows are inflated (no vector/component operators exist); `COVERAGE_MAP_V0.md` numbers stale; `aggregate.py:80-98` normalizes instead of validating. Gap rows spot-checked correct. |
| V7 | M | Product claim boundary | Server gate solid, but claim_ids are dotted JSON paths, not registry refs; `coachProductClaims.ts` is dead code; `CoachSurface.tsx:56,108-131` and `MomentZero.tsx:48-59` render claim headlines even when the server denies; audit flags at `app_service.py:1031-1032` are tautologies. |
| V8 | M | Witness binding | Evidence witness selection is a global name-based scan with frame-id fallback (`executor.py:1251-1296,1399-1412`) — same-frame anchors can bind another anchor's record; `record_runtime_values` silently aliases missing outputs to `"episodes"` (`:1720-1721`). |
| V9 | M | Binder holes | `ParameterRef` durations bypass the temporal-horizon ceiling (`binder.py:277-289`); `max_relations_per_anchor` only enforced on outputs named `episodes`; node-output cache key carries no data-content hash (`executor.py:852-866`). |
| V10 | L | Dead vocabularies | `docs/primitives/registry.yaml` (M1-era, referenced by nothing); noop dispatch registrations (`executor.py:288-291,2216`); duplicate drifted predicate implementations (`executor.py:302-311` vs `9570-9745`). |

### Process finding (from the N1I investigation, same audit window)

Verifiers (`n1d`, `n1i`) regenerate pinned report files and knowledge packs
**in place** when run locally. This exact mechanism overwrote the historical
N1I VERIFIED report with a weaker "not run" record on a superseded branch —
the contradiction resolved by this audit. Same class as V2: gates must never
mutate accepted evidence as a side effect of being run.

## Remediation plan (ordered; this is the roadmap gate)

**Phase F0 — stop the bleeding (before any new primitive lands):**
1. Restore `generate_scp0_artifacts` in the 10 new AFL verifiers; regenerate
   SCP-0 artifacts; fix or re-freeze the failing tests; get the full suite
   green for real. (V1, V3)
2. Split every verifier into read-only check vs explicit `--write`
   regeneration; write FAIL reports instead of preserving stale PASS; stop
   gates from mutating pinned evidence in place. (V2 + process finding)
3. Stand up CI that runs the full suite + parity regeneration diff on every
   push. Stale-green becomes structurally impossible. (V2)

**Phase F1 — close the fail-open truth paths:**
4. Fix T1–T4 (kernel UNKNOWN discipline) and G8; move the
   exists/count_at_least anchor-evaluation rule into the binder and delete
   the bool/len fallbacks (T5–T7); make coverage a *typed* channel on
   `CatalogOutput` instead of a field-name convention (T6).
5. Fix wrong-answer geometry: unify the lane model (G4, G2), temporal-order
   and buffer-provenance checks in line break (G3), GK fail-closed default
   (G5), opponent-aware control or renamed fields (G1), one-touch dwell from
   first arrival (G6), overlap/roster honesty in local numbers (G7),
   Play_Pass filter (G9).

**Phase F2 — one source of truth for the vocabulary:**
6. Eliminate executor shadow defaults and module-default contradictions;
   implementations pull defaults from the catalog; add a mechanical
   conformance check: declared params/outputs/evidence ⇔ read/emitted. (V4)
7. Gate Hermes exposure by registry projection, not blocklist (V5); make
   claim_ids registry references and honor server denial in the client (V7).
8. Extract per-capability code from `executor.py` behind a typed
   implementation contract; quarantine the legacy M1 profile; kill the
   duplicate predicate family and noop registrations. (Core remediation 1,
   V10)

**Phase F3 — honesty upgrades:**
9. Witness binding as a declared chain (V8); binder holes (V9); coverage-map
   downgrades for inflated rows + regenerate the doc (V6); rename
   over-promising primitives (`one_touch_relay`, "controlled", support
   "arrival", half-space lanes) or fold the qualifier into the name — names
   are what programs, passports, and coach claims bind to.

**Test doctrine going forward:** `test_m2a_bypass.py` is the house standard
(mirroring, boundary, shuffle-determinism, missing→UNKNOWN, threshold-free
assertions). Every kernel gets synthetic adversarial tests at that standard;
frozen-count integration snapshots are regression pins, not correctness
evidence.

## What this means for the roadmap

The AFL-08 vocabulary expansion should pause at its current frontier until
F0–F1 land. Nothing in this audit undermines the thesis — the case study's
own lesson ("make each remaining overclaim easy to find and easy to fence")
is exactly what these findings are. But the system's honesty currently
depends on nobody re-running the gates; after F0 it will depend on nothing.
