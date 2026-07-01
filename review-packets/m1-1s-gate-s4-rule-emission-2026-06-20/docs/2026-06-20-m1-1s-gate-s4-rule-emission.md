# Learning: The Plan Becomes The Program At Result Emission

S4 showed that trustworthy generic predicate traces are necessary but not sufficient. The missing layer was the generic result emitter:

```text
anchors -> predicate traces -> classification rules -> evidence projection -> QueryResult
```

The experimental corridor plan now emits 15 generic rows from canonical data with both declared labels. Legacy parity remains isolated behind explicit legacy helpers.

Two implementation lessons matter for future agents:

- Generic temporal intervals should preserve links to declared source records when downstream primitives need to continue from the interval.
- Final `QueryResult` construction must not overwrite evidence that has already been projected from declared runtime outputs.
