# Learning: Relation Coverage Is A Predicate Input, Not An Episode Side Effect

The S7 external review identified a real semantic bug: an empty relation episode list cannot distinguish "no relation exists" from "we could not evaluate the relation."

The runtime now treats relation coverage as an explicit anchor-indexed output:

- `PASS`: one or more qualifying relation episodes exist.
- `FAIL`: the anchor was evaluated and zero qualifying episodes exist.
- `UNKNOWN`: relation evidence was unavailable or unreliable.

This keeps Hermes-facing explanations honest. Raising a threshold can now turn a match into a definitive `FAIL` instead of making the anchor disappear from the predicate signal.

Witness selection also belongs in predicate evidence. Evidence projection should answer "which relation satisfied this predicate?" before reading relation fields. Deterministic list order is useful for reproducibility, but it should not become an undocumented tactical decision.
