# M1.2 S2C External Review Integration

External decision: `APPROVE_WITH_REQUIRED_CHANGES_BEFORE_S3`.

The S2B packet proved a real model-backed compiler path but did not yet prove
reliable unseen-language compilation, strict output handling, complete session
traceability, or actual Hermes runtime integration.

Integrated S2C corrections:

- renamed the proven component identity to `ModelBackedTacticalQueryCompiler`
  and recorded that Hermes remains a future interchangeable client;
- added strict Pydantic action variants for recipe selection, corridor drafting,
  clarification, and capability gaps;
- added one bounded repair turn for invalid model output, then fail-closed
  `MODEL_OUTPUT_INVALID`;
- added semantic validation over model decisions so supported recipe aliases
  cannot be refused, unsupported concepts must be named, support language
  clarifies, and answered clarifications are authoritative;
- changed failed binding to `PLAN_VALIDATION_FAILED`;
- replaced broad category scoring with expected recipe, expected parameter,
  clarification-dimension, and gap-concept scoring;
- added a separate blind corpus under `config/evaluation/`;
- recorded full tool-schema and trusted-recipe-context hashes;
- preserved clarification answers and complete confirmed-execution session
  traces;
- added adversarial tests for bad parameters, wrong units, unsupported
  parameters, hostile complexity limits, prompt injection, and unauthorized
  execution.

Controller verification:

- `make m1-2-gate-s2-verify`: pass, 19/19.
- `make m1-2-verify`: pass, 3/3.
- `make test`: pass, 27 tests.
- `make m1-1-gate-s7r-verify`: pass, 13/13.

S3 remains blocked pending external review of the S2C packet.
