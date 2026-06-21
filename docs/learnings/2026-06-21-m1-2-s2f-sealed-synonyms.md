# M1.2 S2F - Sealed Synonyms and Stable Gap Codes

## Learning

Fresh sealed prompts are useful because they expose wording that the regular
corpus does not cover. The compiler should not only know the canonical phrase
"ball-side block shift"; it must also recognize defensible analyst synonyms such
as trusted defensive sliding toward the side occupied by the ball.

Unsupported rows also showed that safe behavior and evaluator credit can diverge.
The model refused dangerous requests correctly, but the code extractor missed
phrases like "approval step", "execution of the detector", and "body angle".
Those should be normalized to stable capability-gap codes rather than scored by
fragile prose matching.

## Guardrail

When a sealed set drives a correction, that set becomes diagnostic. Passing it
after the correction is valuable regression evidence, but not independent
acceptance evidence. Ask for another fresh sealed set after the correction
freezes.
