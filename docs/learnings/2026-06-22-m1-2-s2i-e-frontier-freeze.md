# Learning: Frontier Freeze Must Separate Alias, Snapshot, and Acceptance

S2I-E clarified three distinct claims that are easy to conflate:

1. Hermes is the intended product route, authenticated through the ChatGPT/Codex subscription path and configured as `openai-codex` with model alias `gpt-5.5`.
2. Direct Responses API probes are the control route and prove exact snapshot access to `gpt-5.5-2026-04-23`.
3. A frozen route plus successful unseeded authoring is not the same as final sealed acceptance.

Future review packets should preserve that distinction. It prevents accidental overclaiming while still giving agents a stable, hash-recorded runtime target.

Implementation note: the freeze verifier should remain a configuration/provenance gate. It should not run new model prompts, tune vocabulary, mutate runtime semantics, or decide final acceptance.
