# Scope

## Review Target

Review whether Beta 1C may expose `HERMES_NOVEL_COMPOSITION` in the Workbench product using the N1I/N1D.1 proof state at commit `54eef2e6f6d90f4004fcb6e6020241774e552de7`.

## Binary Question

Can the product move from "novel composition pending proof refresh" to a real, user-visible `HERMES_NOVEL_COMPOSITION` path, assuming the implementation preserves the existing confirmation, provenance, evidence, trace, replay, and cache boundaries?

## Included

- N1I successful faithful Render rerun report and artifacts.
- N1D.1 machine attestation showing `VERIFIED`.
- Origin bundle, render logs, freeze manifest, hero plan, and entry-mode audit.
- N1D.1/N1I/N1G verifier source and focused runtime/workshop source files.
- Hermes-visible knowledge/capability pack at the reviewed commit.
- Workbench Beta 1A, Beta 1A.1, and Beta 1B reports and source shell files.
- Local command logs for the narrow gates rerun during packet assembly.

## Excluded

- Implementing Beta 1C itself.
- Any new code changes after commit `54eef2e6f6d90f4004fcb6e6020241774e552de7`.
- Render credentials, paid-model credentials, or live runner access.
- Full repo dependency tree, virtualenv, node_modules, caches, or raw deployed filesystem.
- Broad tactical-library expansion or second tactical family.

## Assumptions

- The external reviewer does not have repo access.
- The reviewer can inspect source/artifacts but cannot faithfully rerun deploy-origin Hermes without the project environment.
- The product exposure decision can be made from the integrity of the proof, the source boundaries, and the Workbench shell reports.
