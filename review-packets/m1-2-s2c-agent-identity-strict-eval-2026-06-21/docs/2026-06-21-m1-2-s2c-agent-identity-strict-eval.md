# M1.2 S2C Learning

Fact: A model-backed compiler can call the bounded workshop tools, but that is
not the same as integrating a concrete Hermes runtime.

Decision: S2C names the current component `ModelBackedTacticalQueryCompiler`.
Hermes remains an interchangeable future client over the same bounded caller
profile unless and until a real Hermes adapter is wired.

Learning: Category-only agent evaluation is too weak. A supported prompt must
score the exact recipe family and exact requested parameter overrides; otherwise
wrong tactical compilation can look successful.

Learning: Strict schema validation is necessary but not sufficient. The model
can produce schema-valid refusals for concepts the capability context explicitly
supports. A small semantic validator around explicit capability rules prevents
that drift and gives the model one repair turn before failing closed.

Follow-up: Do not start S3 until the S2C packet is externally reviewed. S3
revision behavior must reuse the strict output, semantic validation, trace, and
host-confirmation contracts rather than inventing a separate revision channel.
