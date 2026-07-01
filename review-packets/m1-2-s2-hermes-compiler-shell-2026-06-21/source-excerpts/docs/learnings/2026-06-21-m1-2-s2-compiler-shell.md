# M1.2 S2 Compiler Shell Learning

Date: 2026-06-21

Fact: S2 is not permission to make Hermes a privileged runtime. It is permission
to make Hermes a bounded client of the already verified tool surface.

Decision: Implement the first Hermes shell as a deterministic local compiler
contract: supported requests become experimental typed drafts, approved recipes
are selected as trusted host records, ambiguous requests ask clarification, and
unsupported requests return capability gaps.

Learning: Language provenance must be first-class. Two prompts may compile to
the same content-addressed draft or bound plan, but each prompt still needs its
own trace so later explanations and feedback remain tied to the actual user
request.

Follow-up: S2 verification must prove the Hermes caller profile path before
expanding prompt coverage or integrating a model-backed agent.
