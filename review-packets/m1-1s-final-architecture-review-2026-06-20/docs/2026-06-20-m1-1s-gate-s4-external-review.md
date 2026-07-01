# M1.1S Gate S4 External Review

Decision: `APPROVE_WITH_REQUIRED_CHANGES_BEFORE_SECOND_PATTERN`

The external reviewer approved S4's central architectural result: generic execution now turns plan-designated anchors and predicate traces into real `QueryResult` rows using declared classification rules.

The reviewer did not recommend reopening the architecture. The second tactical pattern remains blocked only until a focused S4R / S5-opening correction proves:

- all three `unknown_evidence_policy` modes work end to end in real generic execution;
- generic trace generation no longer depends on `_predicate_status` side channels;
- classification conflict resolution is explicit and not lexical;
- the inclusion verifier proves count-changing inclusion behavior, not relabeling through overlapping rules;
- requested evidence uses stable aliases and relation-specific correlation.

The review specifically says not to add Hermes, UI work, another primitive family, or the second detector during this correction.

Required next step:

- implement the narrow S4R correction;
- rerun S4 and regression gates;
- then proceed immediately to the second dissimilar tactical pattern.
