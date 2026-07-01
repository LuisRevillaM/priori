# Workbench — Opus UI / System Review

Reviewer: Opus 4.8, independent senior product/UI systems critic
Date: 2026-06-22
Branch: `codex/integrated-alpha` · Commit: `25f29a14`
Scope companion to: `docs/audits/WORKBENCH_PRODUCT_AUDIT_V1.md` (verdict: SENDABLE_AFTER_P0_P1)

## Thesis

The Workbench is an honest, well-built **deterministic recipe runner** wearing the costume of an **AI tactical author**. The engineering underneath (host scope model, cache keying, generation-guarded inspection, exact-geometry caution) is genuinely good and I would not gate on it. What I *would* gate on is that the UI currently stages a magic trick the product cannot yet perform, and in two places it actively launders provenance. The product does not fail because it lacks primitives; it fails because the first thing a viewer does — type a football question and hit Interpret — either 500s or returns a plan that has nothing to do with what they typed. That is not a "polish later" defect. It is the demo's whole premise breaking on contact. Until the entry point tells the truth about what just happened, the link should not go in an email.

## The entry point lies by default, then lies on first interaction

The app boots in `mode = "manual"` ("Browse recipes") while the topbar proudly shows `HERMES_FRONTIER_READY` and the segmented control leads with **Ask Hermes**. So the staged invitation is "ask in natural language," but the loaded reality is "pick a recipe." A first-time viewer does the obvious thing — leaves the default block-shift sentence in the box and clicks Interpret. Two outcomes, both bad:

- **Ask Hermes:** live `/api/interpret` returns HTTP 500 (audit-confirmed across supported, ambiguous, unsupported, and novel prompts). The single most important journey is dead on the deployed link.
- **Browse recipes:** it "works," but the natural-language box is **decorative**. In manual mode interpretation keys off `preset_id`, not the query text (`app_service.py:836`, `infer_plan_path` only as fallback). The query is consulted *only* to detect capability gaps/clarifications; otherwise the selected preset's plan loads verbatim. Type "infer what the midfielder meant from his scanning and body angle," keep the corridor preset selected, and — if those terms aren't in the gap list — you get a corridor plan presented as the interpretation of your sentence.

That second path is the more dangerous one, because it looks like success. It is the product quietly answering a question you didn't ask. No legend, no "I ignored your text and ran a preset" signal. For a tool whose entire trust proposition is *faithful translation of football language into measurement*, a decorative language box at the front door is a P0 credibility hole, independent of the Hermes 500.

## Does it prove its magic? No — and the UI can't currently tell the truth about it

The novel-composition gate fails today, which the audit states. The UI-layer problem is worse than "we haven't shipped it": the front end **cannot represent the distinction even when the backend makes it**. `sourceLabel()` (`App.tsx:103-109`) collapses *any* source string containing "hermes" into the single label **"Hermes frontier agent."** So a Hermes *recipe selection* (`outcome=select_recipe`, loading a reviewed artifact) and a Hermes *authored draft* (`outcome=draft`) render identically — both as model authorship. That is exactly the provenance confusion the requested ontology exists to prevent: `HERMES_RECIPE_SELECTION` must never read as `HERMES_NOVEL_COMPOSITION`, and a `MANUAL_PRESET` must never read as either. Right now the UI has no vocabulary for `REVIEWED_RECIPE`, `MANUAL_PRESET`, `HERMES_RECIPE_SELECTION`, `HERMES_NOVEL_COMPOSITION`, `DETERMINISTIC_REPAIR`, or `CAPABILITY_GAP` as distinct, visible sources — it has three soft strings and a color pill. The email would therefore be sending a screen that *structurally cannot* prove the headline claim, even on the happy path where the backend behaves.

My position: do not try to ship novel composition for the first preview. Ship **truthful provenance** and let recipe execution be the hero. A workbench that says "Reviewed recipe — block-shift" plainly is far more sendable than one that whispers "Hermes authored this" over a preset.

## Visual / tactical replay — the strongest surface, undermined by one overclaim

The coordinate replay is the part most likely to make a football person lean in, and it mostly earns it: equal-metre scale, real entities, scrub/play controls, canonical match time. But the corridor overlay overclaims in code, not just in copy. `PitchCanvas.tsx:96` draws the dashed ball→`target_player_id` line on **every frame where both entities exist**, with no gating to the relation's open/close interval — and the proof string literally reads "Exact corridor overlay." A persistent line that is present before and after the corridor actually opens reads, to any coach, as *the pass* or *the best pass*. It is neither; it is a hypothetical geometric connection for one witness frame. Two fixes carry almost all the value: (1) only draw the corridor between relation open/close frames and fade it elsewhere; (2) add the required legend ("a sufficiently clear forward connection… does not establish the optimal pass"). Also drop the raw `target {entity_id}` label burned onto the pitch — that is a developer artifact sitting on the hero visual. Keeping block-shift overlays hidden until exact geometry exists is the right call; don't reconstruct arrows from scalars.

## Recommended product shape for the next iteration

Collapse the implementation ladder into four honest stages and make provenance a first-class, always-visible badge:

1. **Ask or choose** — one input. If Ask Hermes is selected, hide the recipe presets (or demote them to labeled "examples"). If Browse recipes is selected, the NL box becomes a read-only restatement of the chosen recipe, *not* an editable field that implies it's being interpreted. Never present an editable language box whose text is ignored.
2. **Understand** — the lowering panel: `USER ASKED / INTERPRETED TACTICALLY / MEASURED AS / DOES NOT ESTABLISH`, topped by a **single provenance badge** from the six-value ontology. The badge is the product's integrity, not decoration.
3. **Approve & run** — one stage-aware primary action (Validate → Approve & run). Today there are *two* parallel triples (left-rail Submit/Host confirm/Execute **and** center Confirm/Host confirm/Run query) — redundant and confusing. Cold runs (60–170s observed) need elapsed time, selected-match count, the cache promise, and a Cancel — not a bare "MISS … running."
4. **Explore moments** — tactical headlines + two principal measurements per result card; move `RETAINED_NO_SWITCH`, result IDs, replay IDs, predicate JSON, and evidence aliases into one Developer drawer. The Known-Timestamp form is a debugging instrument occupying prime left-rail real estate; move it behind Developer details.

Fail-closed everywhere: editing the query after interpreting marks the plan stale and disables Validate; switching mode or preset clears validation/confirmation/execution/replay. Scope changes already do this well — extend that same discipline to mode, query, and preset (currently they don't, per `App.tsx` `choosePreset`/`handleInterpret`, which leave the query untouched).

## System-level implications that hit the product promise

- **The 500 is a contract gap, not a bug to swallow.** `/api/interpret` must convert model-invocation exceptions into a typed `MODEL_UNAVAILABLE` state with a stable trace id and a manual-recovery path. A raw 500 on the headline action reads as "the AI is broken," which is worse than "model offline, recipes available."
- **Bootstrap readiness and runtime reality disagree.** Advertising `HERMES_FRONTIER_READY` while interpret calls fail is itself a trust defect surfaced entirely through the UI. Readiness should reflect an actual interpret probe, not just binary-on-PATH.
- **Gap detection must run before preset fallback for *all* unsupported football language**, not a partial list. The architecture already orders gaps first (`app_service.py:811`); the coverage of `unsupported_gaps` is the single point that decides whether the decorative-box problem is contained.

## What must be fixed before an email preview

1. Kill the raw 500 → typed `MODEL_UNAVAILABLE`, and either make one real Ask-Hermes journey succeed or default the link to Browse recipes with Ask Hermes clearly marked "offline."
2. Stop the decorative-language-box behavior: in manual mode, don't present an editable NL field that is then ignored; in any mode, never let unsupported language silently resolve to the selected preset.
3. Ship the six-value provenance badge and stop collapsing every Hermes source to "Hermes frontier agent."
4. Gate the corridor overlay to its open/close interval and add the non-optimality legend; remove the on-pitch raw entity id and the "Exact corridor overlay" overclaim.
5. Fail-closed on mode/query/preset changes; collapse the duplicated action triples into one stage path.

Do **not** block on shipping live novel composition. Block on the link not lying.

## Opus Verdict

**NOT SENDABLE AS FRAMED — SENDABLE AS A "DETERMINISTIC RECIPE WORKBENCH" AFTER P0.** The underlying system is more trustworthy than its interface. The blocking issues are all interface-truth issues: an entry point that advertises AI and delivers a 500 or a decorative text box, and a provenance layer that cannot distinguish a preset from authored composition. Fix those five items and send it as what it honestly is today — a credible, inspectable, host-safe recipe runner with real tracking data. Reframe the email to claim faithful interpretation + transparent execution, **not** model-authored tactical composition, until the binary novel-composition gate passes live. The magic to sell right now is *honesty and inspectability*, and the product is one provenance badge and one honest entry point away from proving exactly that.
