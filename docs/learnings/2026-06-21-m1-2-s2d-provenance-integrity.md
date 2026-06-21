# M1.2 S2D Learning

Fact: A clarification answer is not enough by itself. The system needs a stable
session object that links the original model question, the user answer, the
validated plan, host confirmation, execution, inspection, replay, and future
revision events.

Decision: S2D introduces host-owned session and turn IDs and persists session
records independently from individual compile traces.

Learning: Repair turns are acceptable only when they are visible. Evaluation
reports must distinguish first-pass behavior from after-repair behavior, or the
compiler can look more reliable than it really is.

Learning: No accepted model field may be decorative. `requested_evidence` was
removed from the decision schema until plan generation gives it real execution
semantics.

Follow-up: S3 must not begin until an owner or independent reviewer supplies the
sealed prompt set after code/prompt freeze and the frozen compiler run is
preserved.
