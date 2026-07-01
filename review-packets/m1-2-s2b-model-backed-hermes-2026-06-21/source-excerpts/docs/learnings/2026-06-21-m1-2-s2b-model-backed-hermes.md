# M1.2 S2B Model-Backed Hermes Learning

Date: 2026-06-21

Fact: A deterministic compiler shell can prove the tool contract but not the
agent capability. S3 depends on a real model interpreting language, because S3
will ask Hermes to interpret feedback and propose semantic changes.

Decision: S2 is split into S2A deterministic compiler contract and S2B
model-backed Hermes evaluation. S2B must pass before S3 starts.

Learning: Prompt-corpus rows must be executed and scored, not merely counted.
The agent can satisfy structural schemas while still over-clarifying supported
language or under-refusing unsupported concepts.

Follow-up: Do not begin S3 until external review accepts the S2B model-backed
agent path and corpus report.
