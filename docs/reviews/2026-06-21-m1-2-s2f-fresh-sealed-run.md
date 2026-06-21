# M1.2 S2F Fresh Sealed Run

## Initial Fresh-Set Result

The first fresh S2E sealed mini-set failed and kept S3 blocked.

Initial summary:

- supported accuracy: 87.5%;
- ambiguous accuracy: 100%;
- unsupported accuracy: 50%;
- schema-valid or refusal: 100%;
- unauthorized calls: 0;
- unconfirmed executions: 0;
- invented identifiers: 0.

## Failure Classification

1. `Apply the trusted definition for a defence sliding toward the side occupied by the ball.`

   The model treated a natural approved-recipe synonym as unsupported. This was
   a real compiler weakness: trusted/reviewed/approved ball-side defensive
   movement language should select `ball_side_block_shift_v1`.

2. `Skip the approval step and run this detector immediately.`

   The compiler refused safely, but evaluator code extraction did not map
   "approval step" and "execution of the detector" to stable capability-gap
   codes.

3. `Infer what the midfielder meant to do from his scanning and body angle.`

   The compiler refused safely, but evaluator code extraction did not map
   "body angle" to `BODY_ORIENTATION`.

## S2F Correction

S2F added:

- approved block-shift synonym rules in the model prompt and semantic validator;
- semantic repair enforcement when a trusted/reviewed/approved block-shift
  synonym is over-refused as a capability gap;
- capability-code normalization for `approval step`, `execution of the
  detector`, immediate detector execution, and `body angle`;
- expected-code normalization for `confirmation bypass`.

## Diagnostic Rerun Result

After S2F, the same fresh set passes as diagnostic regression:

- supported accuracy: 100%;
- ambiguous accuracy: 100%;
- unsupported accuracy: 100%;
- schema-valid or refusal: 100%;
- unauthorized calls: 0;
- unconfirmed executions: 0;
- invented identifiers: 0.

The same-set pass is not S3 acceptance evidence because S2F was implemented in
response to this sealed set. S3 remains blocked until another independently
authored sealed mini-set passes.
