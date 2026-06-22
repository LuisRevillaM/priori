# N1 Proof Integrity

Type: controller learning

Fact: The N1 backend proof was real, but the first packet mixed two hash meanings and overclaimed two semantic guarantees. The generated Tactical Knowledge Pack has an internal semantic hash, while freeze artifacts often need the JSON file checksum. Both are useful, but they must be labeled separately.

Decision: Future proof packets should record `knowledge_pack_file_sha256` for artifact immutability and `knowledge_pack_semantic_sha256` for generated-content identity. Backwards-compatible aliases are allowed only when the hash kind is recorded explicitly.

Learning: A claim that a tri-state or enum path is "preserved" is not enough unless a verifier actually exercises the non-happy-path value. N1B now includes a missing-ball fixture that drives destination entry to `UNKNOWN`, and a structural scan that fails if executor runtime-parameter reads are not backed by host defaults or checked-in recipe parameters.

Scope: `time_to_entry_seconds=0.0` means the ball is present in the destination region at the same frame the corridor opens. Product copy should call that immediate or present-at-opening evidence, not a later after-open transition.
