# Scope

## Target

M1.2 S0R2/S1R2 trust-boundary correction before Hermes S2.

## Source Of Truth

- `delivery/m1.2/SPEC.md`
- `delivery/m1.2/status.yaml`
- commit `a003bc898560570445a00feaafc2507d4036d21c`

## Assumptions

- The reviewer does not have repository access.
- This is an inspection packet, not a self-contained reproducible package.
- S2 must remain blocked unless this packet is approved or required changes are
  integrated.

## Non-Goals

- Do not review final UI polish.
- Do not require Hermes behavior; Hermes is intentionally not implemented in this
  slice.
- Do not reopen M1.1S runtime architecture unless this packet reveals a concrete
  regression.
- Do not add new primitives or tactical families inside this correction.
