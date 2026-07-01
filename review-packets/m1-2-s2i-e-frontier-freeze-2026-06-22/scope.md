# Scope

## Packet Type

`inspection_packet_only`

Validation requires the full repo, local Hermes installation, Hermes home, credentials, and canonical project artifacts.

## In Scope

- S2I-E frontier configuration freeze.
- Product route and control route distinction.
- MCP tool allowlist and host-only exclusions.
- S2I-E verifier and generated proof report.
- S2I-D verifier repair needed to keep live Hermes proof durable after Workbench artifact turnover.
- Roadmap/status updates that keep final independent evaluation blocked before S3.

## Out Of Scope

- Workbench Alpha R1 commit `87b2441`.
- Any UI polish, replay rendering, or Workbench browser acceptance.
- Tactical runtime semantics, primitives, query IR, recipe families, or data pipeline changes.
- Final independent evaluation execution; this packet requests that next step.

## Source Of Truth

- `delivery/m1.2/frontier-runtime-freeze.json`
- `artifacts/m1.2/s2i-e-frontier-freeze-report.json`
- `delivery/m1.2/status.yaml`
- `CURRENT_STATE.md`

## Assumption

The external reviewer cannot access the repo. The packet therefore includes representative source files, generated artifacts, reports, and the commit patch, but not the full repository or credentials.
