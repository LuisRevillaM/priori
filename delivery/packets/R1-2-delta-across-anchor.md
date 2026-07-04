# Work Packet R1-2 — Operator: delta_across_anchor + edge detection

Issued: 2026-07-04 by the project director. Second operator of the R1 era.
Governing: ADR 0013 AND ITS ADDENDUM (the nine-rule template is binding —
R1-1's three rounds are your case law; read delivery/packets/R1-1-REVIEW.md
in full before writing code).

## Ground rules (standing; all laws)

Branch `packet/r1-2` off the frontier (tip f5db8c1 or later). Report
stage-committed from commit one. Fences standard; catalog/IR/registry edits
only as declarations require, enumerated, with registry citizenship
(bindings, exposure policy, projections regenerated via write paths) done
IN-PACKET as R1-1 established. Full-suite table; pinned gates; zero hash
drift for existing plans.

## The operator

`delta_across_anchor@0.1.0`: consume a scalar-bearing channel (frame signal
or per-record scalar) and an anchor set; emit the signed change of the
signal across each anchor (declared before/after windows), plus
`rising_edge` / `falling_edge` outputs under a declared threshold and
hysteresis.

Template compliance from day one: input typing from the census's channel
family (unions where the family needs them); field parameters validated at
bind time against the bound input's declared evidence_fields; NO provider
defaults — required parameters; any orientation/frame dependence is a
declared parameter recorded in evidence; degenerate-input policies declared
(anchor at signal boundary, window truncation -> UNKNOWN per the
could-change-answer discipline); units policy explicit; coverage/witness
rule ids from the registered vocabulary; search-tool insertion
signature-driven — if the R1-1 builder isn't yet generic enough to admit a
second operator without a second hand-built branch, GENERALIZE IT FIRST
(that refactor is in-scope and its absence was named in the template).

## Acceptance composition

Target an atlas dual-pair row whose ledger meaning the composition
actually realizes (the review will check correspondence): e.g.
pressure-onset (rising edge of the pressure count/status signal across
possession anchors) or line-height change across a transition anchor —
pick per the census's honest channel availability, DECLARE the
correspondence in the target file, report the discovery space honestly,
and earn the delta through the constraint-faithful synthesis path R1-1
round 3 built. compiler_reachable before/after via the tool's own sweep.

## Required tests

House standard: signed-delta correctness both attack directions; edge
detection with hysteresis at boundaries (rise exactly at threshold, flicker
suppression); window truncation -> UNKNOWN; missing signal frames ->
UNKNOWN (could-change-answer); executor-path test through real
bind->execute; hash invariance spot.

## Deliverables

Branch `packet/r1-2`; the operator; generalized search insertion if
needed; the earned reachability delta with declared correspondence;
enumeration of all declaration edits; full-suite table; pinned-gate proof;
`delivery/packets/R1-2-REPORT.md`.
