# ADR 0002 - IDSSE/DFL Is the Primary M1 Dataset

Date: 2026-06-19

Status: Accepted for planning

## Context

The project needs real soccer tracking data with enough fidelity to support top-down spatial replay and deterministic tactical predicates. The latest recommendation from the context-rich ChatGPT conversation is to use IDSSE / Sportec Open DFL Tracking and Event Data instead of SkillCorner as the primary M1 source.

## Decision

Use IDSSE/DFL as the only accepted match-evidence source for M1.

Gate A provisions and canonicalizes only `J03WOH` to prove source lock, parser, canonical store, raw parity, quality, orientation, resource use, and replay viability. After Gate A acceptance, provision and canonicalize the remaining six matches. Use the five Fortuna Dusseldorf matches as the tactical corpus, with `J03WOH` for calibration and the remaining four Fortuna matches for evaluation. Use `J03WMX` and `J03WN1` as portability holdouts for away-team perspective and orientation checks.

## Alternatives Considered

- SkillCorner as primary source.
- Synthetic or fixture-based data.
- One-match-only IDSSE final milestone.
- Full mixed-team evaluation corpus.

## Consequences

- M1 can be self-contained around an open dataset.
- Provider code must eventually handle all seven matches, not just Fortuna.
- Gate A prevents corpus-wide and tactical work from starting before one-match source/canonical/replay viability is proven.
- Accepted evidence must trace to source locks and raw hashes.
- SkillCorner becomes a future provider-adapter concern, not the M1 proof source.
