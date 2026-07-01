# Next Steps

## If Reviewer Approves

Proceed to M1.1S Gate S4:

- make classification rules responsible for result inclusion and labels;
- prove changing required predicates changes inclusion;
- make multiple-label behavior explicit;
- keep M1 parity intact.

## If Reviewer Requires Changes Before S4

Address required changes against S3 before starting S4. Likely areas:

- stricter `RuntimeAnchor` schema;
- stronger verifier proving no generic target/trace path reads M1 candidate state;
- tighter separation between anchor metadata and public result evidence.

## If Reviewer Rejects S3

Do not proceed to S4. Record rejection in `docs/reviews/`, update `delivery/m1.1/status.yaml`, and define an S3R corrective gate.
