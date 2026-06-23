# N1B / N1F Destination-Entry Reconciliation

## Conclusion

Explanation **3** is the true causal explanation:

> The generic `relation_destination_entry` capability was marked authorable in the executable capability context, but the generated Hermes knowledge surface and recipe-description path did not consistently expose that safe authoring boundary.

More precisely, the committed capability context at `9de9673d8cf2c6f6b8492227de287fd2a26cd08c` marked:

- `relation_destination_entry`: `agent_authorable = true`
- `relation_destination_entry_classification`: `agent_authorable = false`
- `geometric_progressive_corridor_from_anchor_set`: `agent_authorable = true`
- `possession_segment`: `agent_authorable = true`

But the generated Tactical Knowledge Pack at that same commit raw-dumped catalog primitives without the `agent_authorable` metadata, and the N1F `describe_capability(opposite_corridor_after_shift_v1)` response exposed `relation_destination_entry_classification` inside `authoring_contract.authorable_nodes`. That contradicted the validator and gave Hermes a trusted recipe wrapper pattern to copy.

## Evidence

Current baseline commit:

```text
9de9673d8cf2c6f6b8492227de287fd2a26cd08c
Record N1F scoped Hermes blocked outcome
```

Committed generated artifact hashes at that commit:

```text
generated/tactical-knowledge-pack.json
  file sha256:     7cf720c8210b1d81f12574c5c8299a1dc309930eb1ce17f8eb934d8814119962
  semantic sha256: fd6d0843d32cc9632bc864b3dad11af4fea060fa2a5fd827196b3458af37b7a0

generated/capability-context.json
  file sha256:     0ef53564bf09c7b6e64d1ba8da1aff14bd7ce426b23e0dcb293eaf5256506fe4

delivery/n1d/n1f-origin-bundle.json
  file sha256:     062cfc747180dd89107afb0dbe19eb3fb30c2ac8331afd4d58a6ecec55e30d2f
```

N1B/N1C/N1D prove that the generic capability itself works from possession anchors:

```text
artifacts/n1b/workshop/handles/draft-plans/draft_1b0eea5e9c19ce0f.json
  file sha256:      cc19343c76ab52b283cdd085186b5eb69e89d133fa4c2ede133dc2d102a92f67
  draft_plan_hash:  1b0eea5e9c19ce0f69a2cc586825fbd15a86718fd84d0add71c3fed63b965ec9
  nodes:            possession_segment -> geometric_progressive_corridor_from_anchor_set
                    -> relation_destination_entry -> eq PASS

artifacts/m1.2/workshop/handles/draft-plans/draft_26912b2c452106e8.json
  file sha256:      67b333728979d3cc7f7ed426754851bea93812a9e6ec94e41ad31015fcffef22
  draft_plan_hash:  26912b2c452106e864aa0a4e546fbaf1504d181737aa2bade9a4e77223d13c06
  nodes:            possession_segment -> geometric_progressive_corridor_from_anchor_set
                    -> relation_destination_entry -> eq PASS

delivery/n1d/n1d-hero-plan.json
  file sha256:      064be47c06cce4aeb4b87d2600397daa06ce1a168495e91126e25e235396f23a
  nodes:            possession_segment -> geometric_progressive_corridor_from_anchor_set
                    -> relation_destination_entry -> eq PASS
```

N1F proves the later failure was different. Its Hermes-submitted draft used the trusted wrapper:

```text
delivery/n1d/n1f-origin-bundle.json
  status:           failed_compile
  draft_plan_hash:  ba4eebafd0cd474cfa80ef6bcd72fe374cc7f8ae4ce714c714752aadadd6ccaf
  draft nodes:      possession_segment -> geometric_progressive_corridor_from_anchor_set
                    -> relation_destination_entry_classification -> neq CORRIDOR_PERSISTED_NO_DESTINATION_ENTRY
```

The validation error was explicit:

```text
relation_destination_entry_classification is not agent-authorable
```

The N1F trace also contains `describe_capability(opposite_corridor_after_shift_v1)` output where `authoring_contract.authorable_nodes` includes:

```text
relation_destination_entry_classification
```

That is the concrete visibility leak.

## Rejected Explanations

1. **False.** N1B’s live draft did contain `relation_destination_entry`; the host did not add the destination-entry node afterward. N1D only added result evidence aliases so `entry_mode` and `time_to_entry_seconds` would be projected into result evidence.

2. **False.** The executable capability context did not remove `relation_destination_entry`; it was still marked `agent_authorable = true` at `9de9673`.

4. **False.** The generic input contract does permit possession-anchor corridor relations. N1B, N1C, and N1D artifacts all bind and execute the path from `possession_segment.anchors` to `geometric_progressive_corridor_from_anchor_set.episodes` to `relation_destination_entry.entry_status`.

## N1G Implication

N1G should not change tactical semantics. It should reconcile the agent-facing surfaces:

- keep `relation_destination_entry` generic and agent-authorable;
- keep `relation_destination_entry_classification` trusted-recipe-only;
- generate Hermes-visible knowledge from the executable capability context;
- filter recipe authoring contracts so trusted wrappers are not presented as authorable examples;
- require `relation_destination_entry.entry_status == PASS` for agent-authored destination-entry classification.
