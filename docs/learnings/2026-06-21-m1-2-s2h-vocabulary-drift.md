# M1.2 S2H - Vocabulary Drift Control

## Learning

The repeated fresh sealed sets are mostly exercising synonym drift. The model
often understands the safety boundary but over-refuses analyst wording unless a
host-owned semantic rule maps that wording to an existing supported family or a
clarification dimension.

Capability-gap codes should be host-owned. When a request says "head checks" and
the model summarizes it as "body orientation", the refusal is still safe, but
the evaluator needs the original request text to preserve the `SCANNING` code.

## Guardrail

Do not call a sealed set acceptance evidence after it drives vocabulary changes.
Record it as diagnostic regression and request a fresh set after the correction
freezes.
