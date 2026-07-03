"""Adversarial tests for live comparison-predicate truth evidence (G8).

The persisted ``truth_series`` on predicate records feeds the persistence
adapter (``record_persistence_evidence``); before the F1-A fix it was always
computed with ``>=`` regardless of the bound operator, so ``gt`` and ``lte``
plans persisted wrong truth evidence. These tests assert, threshold-free, that
the truth series and the per-frame pass statuses always agree with the actual
operator and with each other.
"""

import unittest

import pandas as pd

from tqe.runtime.executor import (
    MatchContext,
    RuntimeParameters,
    RuntimeAnchor,
    execute_predicate_with_resolved_inputs,
    predicate_trace_from_runtime_value,
    record_persistence_evidence,
)
from tqe.runtime.ir import (
    Cardinality,
    CatalogOutput,
    CoverageDeclaration,
    EntityScope,
    MissingDataSemantics,
    OperatorRef,
    OperatorSignature,
    PayloadType,
    SignalRef,
    TemporalContainer,
    TypedValue,
    Unit,
)
from tqe.runtime.ir import BoundPredicateNode
from tqe.runtime.values import FrameSignal, RuntimeValue


THRESHOLD = 5.0
MEASURES = [4.0, 5.0, 6.0, None]
FRAME_IDS = [100, 101, 102, 103]


def comparison_node(operator_name: str) -> BoundPredicateNode:
    signal_type = CatalogOutput(
        name="measure",
        temporal_type=TemporalContainer.FRAME_SIGNAL,
        payload_type=PayloadType.NUMBER,
        cardinality=Cardinality.SINGLE,
        unit=Unit.METRE,
        missing_data_semantics=MissingDataSemantics.UNKNOWN,
    )
    output_type = CatalogOutput(
        name="predicate",
        temporal_type=TemporalContainer.FRAME_SIGNAL,
        payload_type=PayloadType.BOOLEAN,
        cardinality=Cardinality.SINGLE,
        unit=Unit.NONE,
        missing_data_semantics=MissingDataSemantics.UNKNOWN,
    )
    return BoundPredicateNode(
        node_id=f"{operator_name}_node",
        input=SignalRef(source_node_id="source_node", output_name="measure"),
        input_type=signal_type,
        operator=OperatorRef(name=operator_name, version="1.0"),
        operator_signature=OperatorSignature(
            name=operator_name,
            version="1.0",
            purpose="test comparison",
            input_temporal_types=[TemporalContainer.FRAME_SIGNAL],
            input_payload_types=[PayloadType.NUMBER],
            input_cardinalities=[Cardinality.SINGLE],
            compare_payload_types=[PayloadType.NUMBER],
            compare_required=True,
            output_temporal_type=TemporalContainer.FRAME_SIGNAL,
            output_payload_type=PayloadType.BOOLEAN,
            output_cardinality=Cardinality.SINGLE,
        ),
        compare=TypedValue(payload_type=PayloadType.NUMBER, value=THRESHOLD, unit=Unit.METRE),
        output=output_type,
    )


def execute_comparison(operator_name: str) -> dict:
    node = comparison_node(operator_name)
    records = [{"anchor_frame_id": frame_id, "measure_series": pd.Series(MEASURES)} for frame_id in FRAME_IDS]
    runtime_value = RuntimeValue(
        output=node.input_type,
        value=FrameSignal(
            frame_ids=FRAME_IDS,
            values=MEASURES,
            unknown_mask=[value is None for value in MEASURES],
            unit=Unit.METRE,
            entity_scope=EntityScope.NONE,
        ),
        records=records,
    )
    return execute_predicate_with_resolved_inputs(
        context=MatchContext(
            match_id="synthetic",
            period="firstHalf",
            frame_ids=tuple(FRAME_IDS),
            params=RuntimeParameters(values={"analysis_rate_hz": 5}),
        ),
        node=node,
        inputs={"measure": runtime_value},
        parameters={"compare": node.compare},
    )


def anchor_evaluation_node(
    *,
    operator_name: str,
    status_field: str,
    count_field: str | None = None,
) -> BoundPredicateNode:
    evidence_fields = ["anchor_id", "anchor_frame_id", status_field]
    if count_field is not None:
        evidence_fields.append(count_field)
    input_type = CatalogOutput(
        name="anchor_evaluations",
        temporal_type=TemporalContainer.EPISODE_SET,
        payload_type=PayloadType.BOOLEAN,
        cardinality=Cardinality.COLLECTION,
        unit=Unit.NONE,
        entity_scope=EntityScope.ANCHOR,
        missing_data_semantics=MissingDataSemantics.UNKNOWN,
        evidence_fields=evidence_fields,
        coverage=CoverageDeclaration(status_field=status_field, count_field=count_field),
    )
    output_type = CatalogOutput(
        name="predicate",
        temporal_type=TemporalContainer.FRAME_SIGNAL,
        payload_type=PayloadType.BOOLEAN,
        cardinality=Cardinality.SINGLE,
        unit=Unit.NONE,
        missing_data_semantics=MissingDataSemantics.UNKNOWN,
    )
    return BoundPredicateNode(
        node_id=f"{operator_name}_{status_field}",
        input=SignalRef(source_node_id="source_node", output_name="anchor_evaluations"),
        input_type=input_type,
        operator=OperatorRef(name=operator_name, version="1.0.0"),
        operator_signature=OperatorSignature(
            name=operator_name,
            version="1.0.0",
            purpose="test anchor coverage",
            input_temporal_types=[TemporalContainer.EPISODE_SET],
            input_payload_types=[PayloadType.BOOLEAN],
            input_cardinalities=[Cardinality.COLLECTION],
            compare_payload_types=[PayloadType.NUMBER] if operator_name == "count_at_least" else [],
            compare_required=operator_name == "count_at_least",
            output_temporal_type=TemporalContainer.FRAME_SIGNAL,
            output_payload_type=PayloadType.BOOLEAN,
            output_cardinality=Cardinality.SINGLE,
        ),
        compare=TypedValue(payload_type=PayloadType.NUMBER, value=2, unit=Unit.COUNT)
        if operator_name == "count_at_least"
        else None,
        output=output_type,
    )


def episode_predicate_node() -> BoundPredicateNode:
    input_type = CatalogOutput(
        name="source_signal",
        temporal_type=TemporalContainer.FRAME_SIGNAL,
        payload_type=PayloadType.BOOLEAN,
        cardinality=Cardinality.SINGLE,
        unit=Unit.NONE,
        missing_data_semantics=MissingDataSemantics.UNKNOWN,
    )
    output_type = CatalogOutput(
        name="predicate",
        temporal_type=TemporalContainer.EPISODE_SET,
        payload_type=PayloadType.BOOLEAN,
        cardinality=Cardinality.COLLECTION,
        unit=Unit.NONE,
        missing_data_semantics=MissingDataSemantics.UNKNOWN,
    )
    return BoundPredicateNode(
        node_id="episode_predicate",
        input=SignalRef(source_node_id="source_node", output_name="source_signal"),
        input_type=input_type,
        operator=OperatorRef(name="persists_for", version="1.0.0"),
        operator_signature=OperatorSignature(
            name="persists_for",
            version="1.0.0",
            purpose="test episode traces",
            input_temporal_types=[TemporalContainer.FRAME_SIGNAL],
            input_payload_types=[PayloadType.BOOLEAN],
            input_cardinalities=[Cardinality.SINGLE],
            duration_required=True,
            output_temporal_type=TemporalContainer.EPISODE_SET,
            output_payload_type=PayloadType.BOOLEAN,
            output_cardinality=Cardinality.COLLECTION,
        ),
        duration=TypedValue(payload_type=PayloadType.NUMBER, value=1.0, unit=Unit.SECOND),
        output=output_type,
    )


def runtime_anchor(frame_id: int = 100, *, result_id: str | None = None) -> RuntimeAnchor:
    attributes = {"anchor_id": "anchor_a", "anchor_frame_id": frame_id}
    if result_id is not None:
        attributes["result_id"] = result_id
    return RuntimeAnchor(
        anchor_id="anchor_a",
        semantic_key="anchor_a",
        match_id="synthetic",
        period="firstHalf",
        anchor_frame_id=frame_id,
        source_node_id="anchors",
        output_name="anchor_evaluations",
        start_frame_id=frame_id,
        end_frame_id=frame_id,
        attributes=attributes,
    )


def execute_anchor_evaluation_predicate(node: BoundPredicateNode, records: list[dict]) -> dict:
    runtime_value = RuntimeValue(output=node.input_type, value=records, records=records)
    parameters = {"compare": node.compare} if node.compare is not None else {}
    return execute_predicate_with_resolved_inputs(
        context=MatchContext(
            match_id="synthetic",
            period="firstHalf",
            frame_ids=tuple(record["anchor_frame_id"] for record in records),
            params=RuntimeParameters(values={"analysis_rate_hz": 5}),
        ),
        node=node,
        inputs={"anchor_evaluations": runtime_value},
        parameters=parameters,
    )


def truth_list(record: dict) -> list[bool | None]:
    return [None if value is None else bool(value) for value in record["truth_series"].tolist()]


class ComparisonTruthSeriesTest(unittest.TestCase):
    def test_truth_series_honors_each_operator(self) -> None:
        # Measures are below / equal to / above the threshold / missing, so
        # the three operators must persist three different truth series.
        expected = {
            "gt": [False, False, True, None],
            "gte": [False, True, True, None],
            "lte": [True, True, False, None],
        }
        for operator_name, expected_truth in expected.items():
            with self.subTest(operator=operator_name):
                output = execute_comparison(operator_name)
                for record in output["predicate_records"]:
                    self.assertEqual(expected_truth, truth_list(record))

    def test_truth_series_agrees_with_pass_statuses_for_every_operator(self) -> None:
        # The persisted truth evidence and the frame pass statuses come from
        # the same measures; they must never disagree on the operator.
        for operator_name in ("gt", "gte", "lte"):
            with self.subTest(operator=operator_name):
                output = execute_comparison(operator_name)
                statuses = output["predicate"].values
                for record in output["predicate_records"]:
                    self.assertEqual(statuses, truth_list(record))

    def test_operators_are_mutually_distinguishable(self) -> None:
        gt_truth = truth_list(execute_comparison("gt")["predicate_records"][0])
        gte_truth = truth_list(execute_comparison("gte")["predicate_records"][0])
        lte_truth = truth_list(execute_comparison("lte")["predicate_records"][0])

        self.assertNotEqual(gt_truth, gte_truth)
        self.assertNotEqual(gte_truth, lte_truth)
        self.assertNotEqual(gt_truth, lte_truth)
        # gt and lte partition the non-missing frames around equality.
        for gt_value, lte_value, measure in zip(gt_truth, lte_truth, MEASURES, strict=True):
            if measure is None:
                self.assertIsNone(gt_value)
                self.assertIsNone(lte_value)
            elif measure == THRESHOLD:
                self.assertFalse(gt_value)
                self.assertTrue(lte_value)
            else:
                self.assertNotEqual(gt_value, lte_value)

    def test_persistence_adapter_consumes_operator_correct_truth(self) -> None:
        # The persistence adapter reads truth_series; under lte the persistent
        # window is the low-measure prefix, not the >=-threshold suffix the
        # defect fabricated.
        lte_record = execute_comparison("lte")["predicate_records"][0]
        persistence = record_persistence_evidence(
            record=lte_record,
            minimum_frames=2,
            analysis_rate_hz=5,
        )

        self.assertTrue(persistence["persistent"])
        self.assertEqual(0, persistence["start_frame_id"])
        self.assertEqual(1, persistence["end_frame_id"])

    def test_exists_runtime_rejects_plain_episode_sets_instead_of_bool_fallback(self) -> None:
        input_type = CatalogOutput(
            name="episodes",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.BOOLEAN,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.POSSESSION,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
        )
        output_type = CatalogOutput(
            name="predicate",
            temporal_type=TemporalContainer.FRAME_SIGNAL,
            payload_type=PayloadType.BOOLEAN,
            cardinality=Cardinality.SINGLE,
            unit=Unit.NONE,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
        )
        node = BoundPredicateNode(
            node_id="plain_episode_exists",
            input=SignalRef(source_node_id="possession", output_name="episodes"),
            input_type=input_type,
            operator=OperatorRef(name="exists", version="1.0.0"),
            operator_signature=OperatorSignature(
                name="exists",
                version="1.0.0",
                purpose="test exists",
                input_temporal_types=[TemporalContainer.EPISODE_SET],
                input_payload_types=[PayloadType.BOOLEAN],
                input_cardinalities=[Cardinality.COLLECTION],
                output_temporal_type=TemporalContainer.FRAME_SIGNAL,
                output_payload_type=PayloadType.BOOLEAN,
                output_cardinality=Cardinality.SINGLE,
            ),
            output=output_type,
        )
        runtime_value = RuntimeValue(
            output=input_type,
            value=[{"anchor_frame_id": 100}],
            records=[{"anchor_frame_id": 100}],
        )

        with self.assertRaisesRegex(RuntimeError, "source lacks declared anchor-evaluation coverage"):
            execute_predicate_with_resolved_inputs(
                context=MatchContext(
                    match_id="synthetic",
                    period="firstHalf",
                    frame_ids=(100,),
                    params=RuntimeParameters(values={"analysis_rate_hz": 5}),
                ),
                node=node,
                inputs={"episodes": runtime_value},
                parameters={},
            )

    def test_exists_uses_declared_coverage_status_fields(self) -> None:
        for status_field in ("team_press_status", "open_space_status", "evaluation_status"):
            with self.subTest(status_field=status_field):
                node = anchor_evaluation_node(operator_name="exists", status_field=status_field)
                output = execute_anchor_evaluation_predicate(
                    node,
                    [
                        {"anchor_id": "a", "anchor_frame_id": 100, status_field: "PASS"},
                        {"anchor_id": "b", "anchor_frame_id": 101, status_field: "FAIL"},
                        {"anchor_id": "c", "anchor_frame_id": 102, status_field: "UNKNOWN"},
                    ],
                )

                self.assertEqual([True, False, None], output["predicate"].values)
                self.assertEqual([False, False, True], output["predicate"].unknown_mask)

    def test_count_at_least_uses_declared_count_field(self) -> None:
        node = anchor_evaluation_node(
            operator_name="count_at_least",
            status_field="evaluation_status",
            count_field="opponents_bypassed_count",
        )
        output = execute_anchor_evaluation_predicate(
            node,
            [
                {
                    "anchor_id": "a",
                    "anchor_frame_id": 100,
                    "evaluation_status": "PASS",
                    "opponents_bypassed_count": 3,
                },
                {
                    "anchor_id": "b",
                    "anchor_frame_id": 101,
                    "evaluation_status": "PASS",
                    "opponents_bypassed_count": 1,
                },
                {
                    "anchor_id": "c",
                    "anchor_frame_id": 102,
                    "evaluation_status": "UNKNOWN",
                    "opponents_bypassed_count": None,
                },
            ],
        )

        self.assertEqual([True, False, None], output["predicate"].values)
        self.assertEqual(
            ["opponents_bypassed_count"] * 3,
            [record["source_evidence"]["coverage_count_field"] for record in output["predicate_records"]],
        )

    def test_episode_trace_plain_episode_non_match_is_fail(self) -> None:
        node = episode_predicate_node()
        runtime_value = RuntimeValue(
            output=node.output,
            value=[{"start_frame_id": 10, "end_frame_id": 20}],
            records=[{"start_frame_id": 10, "end_frame_id": 20}],
        )

        trace = predicate_trace_from_runtime_value(
            node=node,
            runtime_value=runtime_value,
            anchor=runtime_anchor(100),
            result_id="r1",
            common_evidence={"result_id": "r1"},
        )

        self.assertIsNotNone(trace)
        self.assertEqual("FAIL", trace.status)
        self.assertNotIn("reason", trace.source_evidence)

    def test_episode_trace_temporal_unknown_remains_unknown(self) -> None:
        node = episode_predicate_node()
        runtime_value = RuntimeValue(
            output=node.output,
            value=[{"start_frame_id": 90, "end_frame_id": 110, "temporal_status": "UNKNOWN"}],
            records=[{"start_frame_id": 90, "end_frame_id": 110, "temporal_status": "UNKNOWN"}],
        )

        trace = predicate_trace_from_runtime_value(
            node=node,
            runtime_value=runtime_value,
            anchor=runtime_anchor(100),
            result_id="r1",
            common_evidence={"result_id": "r1"},
        )

        self.assertIsNotNone(trace)
        self.assertEqual("UNKNOWN", trace.status)
        self.assertEqual({"start_frame_id": 90, "end_frame_id": 110}, trace.window)

    def test_episode_trace_explicit_temporal_fail_remains_fail(self) -> None:
        node = episode_predicate_node()
        runtime_value = RuntimeValue(
            output=node.output,
            value=[{"start_frame_id": 90, "end_frame_id": 110, "temporal_status": "FAIL"}],
            records=[{"start_frame_id": 90, "end_frame_id": 110, "temporal_status": "FAIL"}],
        )

        trace = predicate_trace_from_runtime_value(
            node=node,
            runtime_value=runtime_value,
            anchor=runtime_anchor(100),
            result_id="r1",
            common_evidence={"result_id": "r1"},
        )

        self.assertIsNotNone(trace)
        self.assertEqual("FAIL", trace.status)
        self.assertEqual({"start_frame_id": 90, "end_frame_id": 110}, trace.window)

    def test_episode_trace_temporal_records_no_match_is_fail(self) -> None:
        node = episode_predicate_node()
        runtime_value = RuntimeValue(
            output=node.output,
            value=[{"start_frame_id": 10, "end_frame_id": 20, "temporal_status": "FAIL"}],
            records=[{"start_frame_id": 10, "end_frame_id": 20, "temporal_status": "FAIL"}],
        )

        trace = predicate_trace_from_runtime_value(
            node=node,
            runtime_value=runtime_value,
            anchor=runtime_anchor(100),
            result_id="r1",
            common_evidence={"result_id": "r1"},
        )

        self.assertIsNotNone(trace)
        self.assertEqual("FAIL", trace.status)
        self.assertNotIn("reason", trace.source_evidence)

    def test_anchorless_legacy_trace_records_bridge_by_identity(self) -> None:
        node = episode_predicate_node()
        cases = [
            (
                runtime_anchor(100, result_id="result-1"),
                {"result_id": "result-1", "match_id": "other", "period": "secondHalf", "anchor_frame_id": 999},
            ),
            (
                runtime_anchor(100),
                {"match_id": "synthetic", "period": "firstHalf", "anchor_frame_id": 100},
            ),
        ]
        for anchor, source_record in cases:
            with self.subTest(source_record=source_record):
                runtime_value = RuntimeValue(
                    output=node.output,
                    value=[],
                    records=[
                        {
                            "predicate_id": node.node_id,
                            "status": "PASS",
                            "value": None,
                            "threshold": None,
                            "unit": Unit.NONE.value,
                            "frame_id": 100,
                            "window": None,
                            "source_evidence": {},
                            "source_record": source_record,
                        }
                    ],
                )

                trace = predicate_trace_from_runtime_value(
                    node=node,
                    runtime_value=runtime_value,
                    anchor=anchor,
                    result_id="result-1",
                    common_evidence={"result_id": "result-1"},
                )

                self.assertIsNotNone(trace)
                self.assertEqual("PASS", trace.status)
                self.assertNotIn("reason", trace.source_evidence)

    def test_uncovered_frame_signal_trace_is_unknown_with_reason(self) -> None:
        node = comparison_node("gte")
        runtime_value = RuntimeValue(
            output=node.output,
            value=FrameSignal(
                frame_ids=[90],
                values=[True],
                unknown_mask=[False],
                unit=Unit.NONE,
                entity_scope=EntityScope.NONE,
            ),
            records=[],
        )

        trace = predicate_trace_from_runtime_value(
            node=node,
            runtime_value=runtime_value,
            anchor=runtime_anchor(100),
            result_id="result-1",
            common_evidence={"result_id": "result-1"},
        )

        self.assertIsNotNone(trace)
        self.assertEqual("UNKNOWN", trace.status)
        self.assertEqual("anchor_frame_missing_from_predicate_signal", trace.source_evidence["reason"])


if __name__ == "__main__":
    unittest.main()
