# Learning: Optional Evidence Must Be Explicit

Making missing evidence fail visibly exposed an important distinction: some evidence is required for a result to be valid, while other evidence is naturally optional.

The S4 corridor-destination plan can legitimately have no `destination_entry_frame_id` when the ball never enters the destination region. That field is now explicitly marked `required: false`; required evidence still causes `INCOMPLETE` execution if it projects to `null`.

Two lessons matter for future agents:

- Do not infer optionality from a `null` value. Put it in the plan contract.
- Evidence tests should mutate node names and evidence sources, not just check keys on one happy-path row.
