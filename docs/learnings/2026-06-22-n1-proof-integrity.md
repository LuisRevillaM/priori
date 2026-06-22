# N1 Proof Integrity

Type: controller learning

Fact: The N1 backend proof was real, but the first packet mixed two hash meanings and overclaimed two semantic guarantees. The generated Tactical Knowledge Pack has an internal semantic hash, while freeze artifacts often need the JSON file checksum. Both are useful, but they must be labeled separately and captured in one canonical manifest.

Decision: Future proof packets should record `knowledge_pack_file_sha256` for artifact immutability and `knowledge_pack_semantic_sha256` for generated-content identity. N1C records both, plus Hermes configuration, MCP allowlist, hero question, draft/bound/execution/replay IDs, structural fingerprint, runtime hashes, and data-manifest hashes in `artifacts/n1c/n1c-canonical-freeze-manifest.json`.

Learning: A claim that a tri-state or enum path is "preserved" is not enough unless a verifier actually exercises the non-happy-path value. N1C now drives actual generic `relation_destination_entry` execution through PASS, FAIL, and UNKNOWN, then proves the bound `entry_status == PASS` predicate returns true/false/unknown rather than collapsing unknown evidence to false. It also enforces declared enum output domains during runtime-value normalization.

Scope: `time_to_entry_seconds=0.0` means the ball is present in the destination region at the same frame the corridor opens. Product copy should call that immediate or present-at-opening evidence, not a later after-open transition. The new `entry_mode` evidence field gives Workbench an explicit value: `PRESENT_AT_OPEN`, `ENTERED_AFTER_OPEN`, `NOT_ENTERED`, or `UNKNOWN`.
