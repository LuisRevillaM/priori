# M1.1S Gate S3 Learning - Anchors Are The Right Review Boundary

Date: 2026-06-20

Fact: The most important remaining M1-specific coupling after S2 was target evaluation and trace extraction reading from `state.candidates`.

Decision: Introduce `RuntimeAnchor` and derive anchors from declared runtime output records. Use those anchors for target evaluation and accepted-result trace reconstruction.

Learning: The right near-term architecture is not to erase every M1 tactical attribute immediately. It is to stop generic control paths from depending on the mutable M1 candidate list, while leaving M1 primitive attributes available as anchor metadata until S4/S5 replace result emission and evidence projection.

Evidence:

- `make m1-1-gate-s3-verify` passes and writes `artifacts/m1.1/gate-s3-verification-report.json`.
- The verifier proves the runtime anchor set is broader than accepted results.
- Target evaluation now reports anchor IDs and explicit UNKNOWN reasons without reading `state.candidates`.
- R5 and Gate C still pass after the anchor-core refactor.

Follow-up: Send an external review checkpoint after S3. Ask specifically whether this anchor core is strong enough for S4, or whether anchor schema normalization must be tightened first.
