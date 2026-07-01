# M1.2 S2D External Review Integration

External decision: `APPROVE_WITH_REQUIRED_CHANGES_BEFORE_S3`.

S2C was accepted as a useful bounded compiler milestone, but S3 remained blocked
on session provenance and evaluation integrity.

Integrated S2D corrections:

- added host-owned `session_id`, `turn_id`, and `parent_turn_id` to compiler
  requests and responses;
- persisted session records under `artifacts/m1.2/workshop/compiler-sessions/`;
- linked clarification question turns, answered turns, and confirmed execution
  events in the same session record;
- added model decision `attempts`, `repair_count`, and `final_accepted_output`
  to compile and execution traces;
- added first-pass accuracy and repair-rate-by-category to evaluation reports;
- removed `requested_evidence` from the model decision schema until it has real
  plan semantics;
- updated milestone terminology to use model-backed compiler, agent caller
  profile, and model-visible tool boundary;
- added sealed-set runner support for
  `config/evaluation/m1_2_s2d_sealed_prompt_set.json`.

Controller verification:

- `make m1-2-gate-s2-verify`: pass, 21/21.

Remaining required artifact before S3:

- owner or independent reviewer must provide the sealed 8 supported / 4
  ambiguous / 4 unsupported prompt set after compiler code/prompt freeze;
- run the frozen compiler once and preserve
  `artifacts/m1.2/agent-sealed-evaluation-report.json`.

S3 remains blocked until that sealed run is complete and reviewed.
