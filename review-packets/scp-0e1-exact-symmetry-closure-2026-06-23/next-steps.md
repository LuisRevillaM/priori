# Next Steps

If accepted:

1. Mark SCP-0E.1 accepted.
2. Unblock SCP-1 implementation.
3. Begin SCP-1 with the existing-runtime lowering path:

```text
SemanticExpression
-> existing TacticalQueryDocument
-> existing binder
-> existing deterministic runtime
```

4. Use High-Bypass Completed Pass and Ball-Side Block Shift as dual-run pilots.
5. Keep full operator conformance as an early SCP-1 acceptance criterion.

If rejected:

1. Preserve this patch.
2. Identify the concrete remaining false-`EXACT` path.
3. Add one focused adversarial test.
4. Patch only the validator/registry surface required to close that path.
