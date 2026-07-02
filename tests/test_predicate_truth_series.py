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
    execute_predicate_with_resolved_inputs,
    record_persistence_evidence,
)
from tqe.runtime.ir import (
    Cardinality,
    CatalogOutput,
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


if __name__ == "__main__":
    unittest.main()
