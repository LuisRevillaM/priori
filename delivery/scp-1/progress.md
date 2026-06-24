# SCP-1 Progress Ledger

| Slice | Status | Evidence | Notes |
| --- | --- | --- | --- |
| Charter | DONE | `delivery/scp-1/SPEC.md`, `delivery/scp-1/status.yaml` | SCP-1 success now requires a semantic language broader than the executable library, typed semantic gaps, Football Query Normal Form, anchor synthesis, and recipe-free evaluation. |
| SCP-1L - Minimal Executable Language | DONE_WITH_CONCERNS | `src/tqe/semantic_compiler/`, `delivery/scp-1/semantic-programs/`, `src/tqe/verification/scp1.py`, `tests/test_scp1_semantic_compiler.py`, `artifacts/scp-1/verification-report.json` | Implemented `SemanticExpression`, Football Query Normal Form, support facts, typed semantic gaps, and lowering into existing `TacticalQueryDocument`. Two executable pilots compile and bind: Ball-Side Block Shift and High-Bypass Completed Pass. Three non-executable fixtures return typed gaps: reconstructed goal-kick restart candidate, player-intent modality gap, and support-arrival clarification. Concern: this is not yet natural-language compilation or broad held-out generality. |
| SCP-1C - Natural-Language Compiler | NOT_STARTED | pending | Compile natural language into semantic programs or precise typed gaps. |
| SCP-1G - Generality Harness | NOT_STARTED | pending | Build Football Program Corpus, closed-book/open-library evaluation, held-out combinations, semantic-equivalence checks, and gap-localization metrics. |
| Verification | DONE_FOR_SCP_1L | `make scp-1-verify`, `artifacts/scp-1/verification-report.json` | SCP-1L verifier passes 22/22 checks plus 8 unit tests. Full SCP-1 remains incomplete until NL compilation, held-out program corpus, recipe-free evaluation, and protected promotion are added. |

## Current Decision

SCP-1L is implemented as a minimal semantic compiler kernel, not a final
compiler. It proves the language can represent executable football programs and
typed non-executable gaps, then lower supported programs through the existing
runtime authority chain.

SCP-1 acceptance must prove that Priori can compile held-out, recipe-free
natural-language football descriptions into either novel executable typed
programs or precise typed gaps while preserving claim boundaries, uncertainty,
and evidence requirements.
