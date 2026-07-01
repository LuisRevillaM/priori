# Scope

## Packet Type

`inspection_packet_only`

## Review Scope

This packet covers the Primitive & Lowering Audit v1 for the football tracking-data tactical query system. It packages:

- the audit report;
- generated capability inventory;
- generated dependency/lowering graph;
- generated tactical coverage matrix;
- generated next-capability recommendations;
- supporting source excerpts, schemas, query plans, docs, tests, and validators used as evidence.

## Included

- Audit artifacts from `docs/audits/` and `generated/audits/`.
- Current source-of-truth project/milestone docs.
- Current generated capability context and tactical knowledge pack.
- Current tactical query plan schema and TypeScript type output.
- Runtime catalog, IR, binder, executor, relation, and value source files.
- Workshop/tool-boundary and knowledge-pack source files.
- Three current query plan documents.
- Ball-Side Block Shift query docs and semantic gold set.
- Representative binder/runtime tests and verification files.
- Local command outputs proving git identity/status and JSON parse validation.

## Excluded

- Full repository.
- `.git`.
- raw IDSSE/DFL source data.
- canonical Parquet data.
- replay windows and runtime execution artifacts.
- dependency caches, virtualenvs, `node_modules`, build outputs.
- credentials, `.env` files, private keys, or API secrets.
- unrelated pre-existing review packets.

## Assumptions

- The external reviewer needs enough evidence to evaluate the audit reasoning, not to rerun the full runtime.
- Runtime execution and verifier reproduction require the full repository and local data.
- Existing untracked review packets and the unrelated `pyproject.toml` modification are outside this packet's scope.
