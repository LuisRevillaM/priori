# The Training Doctrine — post-training ambition for the vision track

Director-authored audit + doctrine, 2026-07-10. Owner mandate: "we've
got to be very ambitious with that layer too — it's fundamental to
the future of this project." Facts from the ladder audit (all cited
in the fact brief; ladder complete, every rung ACCEPTED, total GPU
spend $4.96).

## 1. The audit verdict

The ladder measured honestly and trained NOTHING. Every model is
off-the-shelf: detection is someone else's soccer fine-tune, tracking
runs with ReID disabled, team identity is unsupervised color
clustering, jerseys are 100% null because OCR was never executed, and
calibration is an upstream WC14 fine-tune wearing a GPL-2.0 license
we cannot ship. Consequence: every ceiling we recorded is the FLOOR
of a training program, and the cheap-lever rung already proved the
slope — ball AP50 went 5% → 71% from checkpoint + resolution alone,
zero training.

## 2. The north-star metric (Goodhart guard, binding)

Training decisions are judged by ONE number: **interval narrowing per
dollar on the flagship question families** — the INT-1 query-fidelity
table's UNKNOWN shares and bound widths, on frozen eval matches.
GS-HOTA and AP50 are diagnostics, never targets. We do not train for
leaderboards; we train so that "how often do they keep the ball under
pressure?" answers with tighter honest bounds on a coach's own
footage. This reconciles the charter's "the moat is not the vision
model" with the owner's ambition: the moat is the honest compiler —
training is how its intervals narrow on footage we don't control.

## 3. The TRAIN ladder (mirrors VAL; cheapest-first; each rung
##    oracle-gated like everything else in this project)

- **T-0 — License-clean data foundation.** SkillCorner open data (10
  matches, charter V0, never ingested) + own/permission footage +
  SYNTHETIC data (see §4). SoccerNet remains eval-only FOREVER (NDA:
  never trains, never ships). Deliverable: a rights-mapped training
  data registry with per-source provenance, mirroring
  DATA_PROVENANCE.md discipline. No training rung starts before its
  data rows are rights-green.
- **T-1 — The ball specialist.** Fine-tune detection on license-clean
  soccer data + pipeline-prelabeled own footage (miss taxonomy says
  where: tiny 117 / occluded 102 / aerial 78 — train against the
  taxonomy, sample hard negatives from it). Then the temporal rung:
  a sequence model over detection windows (SoccerNet ball lineage
  architectures, trained on clean data) — the single biggest UNKNOWN
  narrower in the product (ball gates everything possession-shaped).
  Floor 64% recall gated → target: ball-dependent question families
  move from vacuous to answerable on broadcast footage.
- **T-2 — Team identity as a trained head.** Supervised-contrastive
  embedding on kit crops, bootstrapped from the clustering pseudo-
  labels + human correction of uncertainty-sampled crops. Floor 80.6%
  full-split (chance-level before repair!) → target 97%+. Cheapest
  big win in the whole program.
- **T-3 — Jerseys via synthetic-first OCR.** Fine-tune the pinned
  Apache-2.0 MMOCR checkpoints on SYNTHETIC jersey renders (numbers
  composited onto player crops with realistic pose/motion blur —
  infinite, license-clean) + corrected real crops from the flywheel.
  Kills the 619,411-null column and the GS-HOTA identity penalty.
- **T-4 — Soccer ReID for the tracker.** BoT-SORT currently runs
  with_reid=False. Train a soccer-specific ReID embedding (from
  tracking pseudo-labels + T-2's kit embedding as init). Directly
  lifts association (AssA 0.485) and long-gap continuity — the
  narrative chains the product replays depend on.
- **T-5 — License-clean calibration.** Replace GPL-2.0 NBJW with our
  own keypoint model trained on SYNTHETIC pitch renders (known
  homographies by construction — the rare case where ground truth is
  free and perfect) + fine-tuned on the license-clean real sets.
  Fixes the production-license wall AND the domain-gap gating (97%
  gated on OOD cameras) in one rung.
- **T-∞ — The flywheel (the charter's rung 2, now concretized).**
  Pipeline pre-labels → uncertainty-sampled human correction (the QA
  constraint is HOURS, so sample only where the model is unsure) →
  Modal trains → INT-1 re-measures → redeploy. Every pilot match,
  with consent, narrows every future match's intervals. This is the
  ambition the owner named: the pipeline that improves because it is
  used.

## 4. Synthetic data is the license-clean superpower

Three of the five rungs can be fed largely without touching anyone's
rights: pitch renders with perfect homographies (T-5), jersey-number
composites (T-3), and physics-simulated ball trajectories composited
over real backgrounds (T-1 augmentation). Zero rights risk, infinite
volume, ground truth by construction — and it compounds with the
flywheel's small, consented, real corrections.

## 5. Costs (order-of-magnitude, Modal A10G at ladder-observed rates)

Fine-tune experiments run $5-30 each (hours of A10G); a full T-1..T-5
first pass is LOW HUNDREDS of dollars GPU — the binding constraint is
QA-hours for corrections, which uncertainty sampling minimizes. The
$25 Modal authorization needs raising to ~$150 for the first training
era (FOR-THE-OWNER).

## 6. Governance (nothing new — the same laws)

Frozen, hash-pinned eval sets per rung (the blind-set discipline);
INT-1 fidelity as acceptance, benchmarks as diagnostics; training
runs produce R-AZ evidence (config, data-registry rows, seeds,
metrics) via committed scripts; model weights versioned with
provenance like data; the tamper-bait qualification applies to any
automated training loop before it earns autonomy.

## FOR-THE-OWNER (blocking items, none urgent)

1. Modal budget: raise authorization $25 → ~$150 for the T-1/T-2
   first experiments.
2. SkillCorner open data: confirm go for ingestion (public, but the
   rights row gets your eyes before it enters the registry).
3. Plan-A footage conversations (UT Austin / Austin FC II) remain the
   flywheel's consent source — timing yours.
4. Production legal review of the NBJW GPL boundary is MOOTED by T-5
   (we replace it), but if any pilot ships before T-5 lands, the
   review is needed.

---
## v2 note (2026-07-10)
This draft is SUPERSEDED in part by ADR 0017 (cross-family counsel
synthesis): the serial T-ladder becomes parallel D-lanes with
calibration first; the north star becomes the lexicographic objective
(selective correctness → usefulness floor → information → economics);
synthetic ratings and the flywheel are corrected per the counsel;
broadcast and club-tactical footage split into separate domain
profiles, tactical-first. Read ADR 0017 with this document.
