from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from tqe.runtime.binder import BindError, bind_document, bind_error_codes
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows
from tqe.runtime.ir import CatalogOutput, MissingDataSemantics, TacticalQueryDocument, TypedValue
from tqe.runtime.operators.window import WINDOW_SIGNATURE, execute_window
from tqe.runtime.values import RuntimeValue, canonical_anchor_record_id, runtime_value_from_raw


PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")


def typed_enum(value: str) -> TypedValue:
    return TypedValue(payload_type="enum", value=value)


def typed_number(value: float, unit: str = "none") -> TypedValue:
    return TypedValue(payload_type="number", unit=unit, value=value)


def anchor_record(name: str, frame_id: int, *, team_role: str = "home", status: str = "PASS") -> dict[str, object]:
    item: dict[str, object] = {
        "match_id": "TST",
        "period": "firstHalf",
        "anchor_frame_id": frame_id,
        "start_frame_id": frame_id,
        "end_frame_id": frame_id,
        "entity_refs": [team_role, name],
        "team_role": team_role,
        "anchor_status": status,
    }
    item["anchor_id"] = canonical_anchor_record_id(item)
    return item


def continuity_record(name: str, start: int, end: int, *, team_role: str = "home") -> dict[str, object]:
    item: dict[str, object] = {
        "match_id": "TST",
        "period": "firstHalf",
        "anchor_frame_id": start,
        "start_frame_id": start,
        "end_frame_id": end,
        "entity_refs": [team_role],
        "team_role": team_role,
        "continuity_status": "PASS",
        "segment_name": name,
    }
    item["anchor_id"] = canonical_anchor_record_id(item)
    return item


def runtime_records_value(
    name: str,
    records: list[dict[str, object]],
    *,
    input_name: str = "anchors",
) -> RuntimeValue:
    input_def = {item.name: item for item in WINDOW_SIGNATURE.inputs}[input_name]
    return runtime_value_from_raw(
        node_id=name,
        output=CatalogOutput(
            name=input_name,
            temporal_type=input_def.temporal_type,
            payload_type=input_def.payload_type,
            cardinality=input_def.cardinality,
            unit=input_def.unit,
            entity_scope=input_def.entity_scope,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=[
                "anchor_id",
                "anchor_frame_id",
                "start_frame_id",
                "end_frame_id",
                "team_role",
                "anchor_status",
                "continuity_status",
            ],
        ),
        raw_value=records,
        frame_ids=[int(record["anchor_frame_id"]) for record in records],
        records=records,
    )


def operator_node(*, with_continuity: bool = False) -> SimpleNamespace:
    inputs = {"anchors": SimpleNamespace(source_node_id="anchors", output_name="anchors")}
    if with_continuity:
        inputs["continuity_evidence"] = SimpleNamespace(source_node_id="segments", output_name="continuity_evidence")
    return SimpleNamespace(node_id="window", inputs=inputs)


def run_window(
    anchors: list[dict[str, object]],
    *,
    continuity: list[dict[str, object]] | None = None,
    window_mode: str = "after",
    before_seconds: float = 0.0,
    after_seconds: float = 1.0,
    truncation_policy: str = "emit_with_flag",
    continuity_policy: str = "fixed_duration",
    continuity_overlap_policy: str = "latest_start",
    frame_ids: list[int] | None = None,
) -> dict[str, object]:
    state = SimpleNamespace(
        match_id="TST",
        period="firstHalf",
        frame_ids=list(range(100, 151)) if frame_ids is None else frame_ids,
        signals={},
    )
    inputs = {"anchors": runtime_records_value("anchors", anchors)}
    if continuity is not None:
        inputs["continuity_evidence"] = runtime_records_value(
            "segments",
            continuity,
            input_name="continuity_evidence",
        )
    execute_window(
        state=state,
        node=operator_node(with_continuity=continuity is not None),
        inputs=inputs,
        parameters={
            "window_mode": typed_enum(window_mode),
            "anchor_frame_field": typed_enum("anchor_frame_id"),
            "before_duration_seconds": typed_number(before_seconds, "second"),
            "after_duration_seconds": typed_number(after_seconds, "second"),
            "frame_rate_hz": typed_number(25.0, "hertz"),
            "anchor_status_field": typed_enum("anchor_status"),
            "anchor_status_value": typed_enum("PASS"),
            "truncation_policy": typed_enum(truncation_policy),
            "continuity_policy": typed_enum(continuity_policy),
            "continuity_start_frame_field": typed_enum("start_frame_id" if continuity is not None else "none"),
            "continuity_end_frame_field": typed_enum("end_frame_id" if continuity is not None else "none"),
            "continuity_status_field": typed_enum("continuity_status" if continuity is not None else "none"),
            "continuity_status_value": typed_enum("PASS"),
            "anchor_team_role_field": typed_enum("team_role" if continuity is not None else "none"),
            "continuity_team_role_field": typed_enum("team_role" if continuity is not None else "none"),
            "team_binding_policy": typed_enum("equal_team_role" if continuity is not None else "none"),
            "continuity_overlap_policy": typed_enum(continuity_overlap_policy),
            "overlap_policy": typed_enum("preserve_all"),
        },
    )
    return state.signals["window"]


class WindowOperatorTests(unittest.TestCase):
    def test_signature_fields_are_known_to_search(self) -> None:
        from scripts.coverage_map import compiler_search_reachability as search

        signature_fields = {
            field
            for output in WINDOW_SIGNATURE.outputs
            for field in [output.name, *output.evidence_fields]
        }
        self.assertEqual(signature_fields, search.WINDOW_FIELDS)

    def test_truncation_at_period_start_is_recorded_when_policy_emits(self) -> None:
        [record] = run_window(
            [anchor_record("early", 102)],
            window_mode="before",
            before_seconds=1.0,
            after_seconds=0.0,
            frame_ids=list(range(100, 151)),
        )["window_records"]

        self.assertEqual("PASS", record["window_status"])
        self.assertEqual(77, record["requested_start_frame_id"])
        self.assertEqual(100, record["window_start_frame_id"])
        self.assertTrue(record["truncated_start"])
        self.assertFalse(record["truncated_end"])

    def test_truncation_policy_unknown_blocks_claim(self) -> None:
        [record] = run_window(
            [anchor_record("late", 148)],
            window_mode="after",
            before_seconds=0.0,
            after_seconds=1.0,
            truncation_policy="unknown",
            frame_ids=list(range(100, 151)),
        )["window_records"]

        self.assertEqual("UNKNOWN", record["window_status"])
        self.assertEqual("window_truncated_by_boundary", record["window_reason"])
        self.assertTrue(record["truncated_end"])

    def test_trace_back_bounds_to_same_possession_break(self) -> None:
        [record] = run_window(
            [anchor_record("outcome", 140)],
            continuity=[continuity_record("segment", 126, 145)],
            window_mode="trace_back_from_outcome",
            before_seconds=1.0,
            after_seconds=0.0,
            continuity_policy="same_possession",
            frame_ids=list(range(100, 151)),
        )["window_records"]

        self.assertEqual("PASS", record["window_status"])
        self.assertEqual(115, record["requested_start_frame_id"])
        self.assertEqual(126, record["window_start_frame_id"])
        self.assertEqual("trace_back_bounded_by_continuity", record["continuity_reason"])
        self.assertEqual("same_possession", record["continuity_policy"])

    def test_missing_possession_coverage_is_unknown(self) -> None:
        [record] = run_window(
            [anchor_record("outcome", 140)],
            continuity=[continuity_record("other", 100, 120)],
            window_mode="trace_back_from_outcome",
            before_seconds=1.0,
            after_seconds=0.0,
            continuity_policy="same_possession",
            frame_ids=list(range(100, 151)),
        )["window_records"]

        self.assertEqual("UNKNOWN", record["window_status"])
        self.assertEqual("continuity_evidence_not_covering_anchor", record["window_reason"])

    def test_opponent_possession_covering_anchor_is_fail_not_same_team_pass(self) -> None:
        [record] = run_window(
            [anchor_record("away-reception", 120, team_role="away")],
            continuity=[continuity_record("home-possession", 100, 140, team_role="home")],
            window_mode="after",
            after_seconds=0.4,
            continuity_policy="same_possession",
            frame_ids=list(range(100, 151)),
        )["window_records"]

        self.assertEqual("FAIL", record["window_status"])
        self.assertEqual("continuity_team_mismatch", record["window_reason"])
        self.assertEqual("away", record["anchor_team_role"])
        self.assertEqual("home", record["continuity_team_role"])

    def test_observed_same_team_break_mid_window_is_fail(self) -> None:
        [record] = run_window(
            [anchor_record("home-reception", 120, team_role="home")],
            continuity=[continuity_record("short-home-possession", 100, 125, team_role="home")],
            window_mode="after",
            after_seconds=1.0,
            continuity_policy="same_possession",
            frame_ids=list(range(100, 151)),
        )["window_records"]

        self.assertEqual("FAIL", record["window_status"])
        self.assertEqual("continuity_break_inside_window", record["window_reason"])

    def test_overlapping_continuity_can_be_declared_ambiguous(self) -> None:
        [record] = run_window(
            [anchor_record("home-reception", 120, team_role="home")],
            continuity=[
                continuity_record("home-possession-a", 100, 140, team_role="home"),
                continuity_record("home-possession-b", 110, 145, team_role="home"),
            ],
            window_mode="after",
            after_seconds=0.4,
            continuity_policy="same_possession",
            continuity_overlap_policy="unknown_on_ambiguous",
            frame_ids=list(range(100, 151)),
        )["window_records"]

        self.assertEqual("UNKNOWN", record["window_status"])
        self.assertEqual("ambiguous_overlapping_continuity_evidence", record["window_reason"])

    def test_trace_back_truncation_is_judged_after_continuity_bounding(self) -> None:
        [record] = run_window(
            [anchor_record("outcome", 105, team_role="home")],
            continuity=[continuity_record("home-possession", 100, 110, team_role="home")],
            window_mode="trace_back_from_outcome",
            before_seconds=1.0,
            after_seconds=0.0,
            truncation_policy="unknown",
            continuity_policy="same_possession",
            frame_ids=list(range(100, 151)),
        )["window_records"]

        self.assertEqual("PASS", record["window_status"])
        self.assertEqual(100, record["window_start_frame_id"])
        self.assertFalse(record["truncated_start"])
        self.assertEqual("trace_back_bounded_by_continuity", record["continuity_reason"])

    def test_anchor_outside_observed_bounds_is_unknown_not_phantom_pass(self) -> None:
        [record] = run_window(
            [anchor_record("outside", 90, team_role="home")],
            window_mode="after",
            after_seconds=0.2,
            frame_ids=list(range(100, 151)),
        )["window_records"]

        self.assertEqual("UNKNOWN", record["window_status"])
        self.assertEqual("anchor_outside_observed_bounds", record["window_reason"])

    def test_fixed_duration_period_fallback_ignores_continuity_records(self) -> None:
        [record] = run_window(
            [anchor_record("home-reception", 120, team_role="home")],
            continuity=[continuity_record("long-home-possession", 100, 150, team_role="home")],
            window_mode="before",
            before_seconds=1.0,
            continuity_policy="fixed_duration",
            frame_ids=[],
        )["window_records"]

        self.assertEqual("PASS", record["window_status"])
        self.assertEqual(120, record["window_start_frame_id"])
        self.assertEqual(120, record["period_start_frame_id"])
        self.assertTrue(record["truncated_start"])

    def test_zero_duration_boundary_anchor_is_allowed(self) -> None:
        [record] = run_window(
            [anchor_record("zero", 100)],
            window_mode="around",
            before_seconds=0.0,
            after_seconds=0.0,
            frame_ids=list(range(100, 151)),
        )["window_records"]

        self.assertEqual("PASS", record["window_status"])
        self.assertEqual(100, record["window_start_frame_id"])
        self.assertEqual(100, record["window_end_frame_id"])
        self.assertEqual(1, record["window_duration_frames"])

    def test_overlap_policy_preserves_all_and_shuffle_is_deterministic(self) -> None:
        anchors = [anchor_record("b", 120), anchor_record("a", 120)]
        first = run_window(anchors, window_mode="after", after_seconds=0.4)["window_records"]
        second = run_window(list(reversed(anchors)), window_mode="after", after_seconds=0.4)["window_records"]

        self.assertEqual(2, len(first))
        self.assertEqual([record["anchor_id"] for record in first], [record["anchor_id"] for record in second])
        self.assertEqual(["preserve_all", "preserve_all"], [record["overlap_policy"] for record in first])

    def test_both_team_anchors_keep_witness_identity(self) -> None:
        records = run_window(
            [
                anchor_record("home-pass", 120, team_role="home"),
                anchor_record("away-pass", 130, team_role="away"),
            ],
            window_mode="after",
            after_seconds=0.2,
        )["window_records"]

        by_source = {record["source_anchor_id"]: record for record in records}
        self.assertEqual({"home", "home-pass"}, set(by_source[anchor_record("home-pass", 120, team_role="home")["anchor_id"]]["entity_refs"]))
        self.assertEqual({"away", "away-pass"}, set(by_source[anchor_record("away-pass", 130, team_role="away")["anchor_id"]]["entity_refs"]))

    def test_binder_rejects_unbound_window_field_parameter(self) -> None:
        payload = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        payload["recipe"]["output_classifications"] = ["R1_4_WINDOW"]
        source_node_id = payload["draft_plan"]["nodes"][0]["node_id"]
        payload["draft_plan"]["nodes"].append(
            {
                "kind": "operator",
                "node_id": "window",
                "operator": {"name": "window", "version": "0.1.0"},
                "inputs": {"anchors": {"source_node_id": source_node_id, "output_name": "anchors"}},
                "parameters": {
                    "window_mode": {"payload_type": "enum", "value": "after"},
                    "anchor_frame_field": {"payload_type": "enum", "value": "not_declared"},
                    "before_duration_seconds": {"payload_type": "number", "unit": "second", "value": 0.0},
                    "after_duration_seconds": {"payload_type": "number", "unit": "second", "value": 1.0},
                    "frame_rate_hz": {"payload_type": "number", "unit": "hertz", "value": 25.0},
                },
                "outputs": [output.model_dump(mode="json") for output in WINDOW_SIGNATURE.outputs],
            }
        )

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn("operator_field_parameter_not_in_input", bind_error_codes(raised.exception))

    def test_executor_path_through_real_bind_execute(self) -> None:
        payload = {
            "schema_version": "1.0",
            "recipe": {
                "schema_version": "1.0",
                "recipe_id": "r1_4_window_probe",
                "recipe_version": "0.1.0",
                "display_name": "R1-4 window probe",
                "description": "Generic window operator execution probe.",
                "parameters": [],
                "default_unknown_evidence_policy": "exclude_candidate",
                "allowed_claims": ["Observed bounded window around a controlled-pass anchor."],
                "disallowed_claims": ["The system inferred possession value, intent, or causation."],
                "limitations": ["Operator acceptance probe."],
                "output_classifications": ["R1_4_WINDOW"],
            },
            "default_invocation": {
                "schema_version": "1.0",
                "invocation_id": "r1_4_window_probe",
                "match_ids": ["J03WOY"],
                "periods": ["firstHalf"],
                "perspective_team_role": "home",
                "parameters": {},
                "max_results": 5,
                "execution_mode": "execute",
            },
            "draft_plan": {
                "schema_version": "1.0",
                "plan_id": "r1_4_window_probe",
                "plan_version": "0.1.0",
                "recipe_id": "r1_4_window_probe",
                "recipe_version": "0.1.0",
                "status": "experimental",
                "unknown_evidence_policy": "exclude_candidate",
                "classification_mode": "partial_declared",
                "nodes": [
                    {
                        "kind": "primitive",
                        "node_id": "controlled_pass",
                        "catalog_ref": "controlled_pass_episode",
                        "version": "0.1.0",
                    },
                    {
                        "kind": "operator",
                        "node_id": "window",
                        "operator": {"name": "window", "version": "0.1.0"},
                        "inputs": {"anchors": {"source_node_id": "controlled_pass", "output_name": "anchors"}},
                        "parameters": {
                            "window_mode": {"payload_type": "enum", "value": "after"},
                            "anchor_frame_field": {"payload_type": "enum", "value": "controlled_reception_frame_id"},
                            "before_duration_seconds": {"payload_type": "number", "unit": "second", "value": 0.0},
                            "after_duration_seconds": {"payload_type": "number", "unit": "second", "value": 0.2},
                            "frame_rate_hz": {"payload_type": "number", "unit": "hertz", "value": 25.0},
                            "anchor_status_field": {"payload_type": "enum", "value": "controlled_pass_status"},
                            "anchor_status_value": {"payload_type": "enum", "value": "PASS"},
                        },
                        "outputs": [output.model_dump(mode="json") for output in WINDOW_SIGNATURE.outputs],
                    },
                    {
                        "kind": "predicate",
                        "node_id": "window_observed",
                        "input": {"source_node_id": "window", "output_name": "window_status"},
                        "operator": {"name": "eq", "version": "1.0.0"},
                        "compare": {"payload_type": "enum", "value": "PASS"},
                    },
                ],
                "classification_rules": [
                    {
                        "label": "R1_4_WINDOW",
                        "predicate_ids": ["window_observed"],
                        "description": "Window operator emitted a PASS window.",
                    }
                ],
                "anchor_source": {"source_node_id": "window", "output_name": "window_records"},
                "requested_evidence": [
                    {
                        "source": {"source_node_id": "window", "output_name": "window_records"},
                        "field": "window_status",
                        "alias": "window_status",
                        "required": True,
                    }
                ],
            },
        }
        document = TacticalQueryDocument.model_validate(payload)
        bound = bind_document(document)

        execution = TacticalQueryExecutor().execute(bound)
        rows = execution_result_rows(execution)

        self.assertTrue(rows)
        self.assertTrue(any(row.get("requested_evidence", {}).get("window_status") in {"PASS", "FAIL"} for row in rows))

    def test_provider_name_hint_guard_catches_window_constraint_value_channel(self) -> None:
        from scripts.coverage_map import compiler_search_reachability as search

        target = {
            "target_id": "probe",
            "concept": "same_team_control_after",
            "target_contract": {
                "required_evidence": ["window_status"],
                "composition_constraints": [
                    {
                        "kind": "window",
                        "source_provider": "controlled_pass_episode",
                    }
                ],
            },
        }

        self.assertTrue(search.provider_name_used_as_hint(target))

    def test_search_synthesis_fails_on_unapplied_window_constraint_key(self) -> None:
        from scripts.coverage_map import compiler_search_reachability as search

        target_payload = json.loads(Path("config/compiler-reachability/r1-4-window-targets.v0.json").read_text(encoding="utf-8"))
        target = copy.deepcopy(target_payload["targets"][0])
        target["target_contract"]["composition_constraints"][0]["source_provider"] = "controlled_pass_episode"
        context = search.SearchContext(
            catalog=search.CatalogIndex(),
            target_contract=target["target_contract"],
        )

        with self.assertRaises(search.SynthesisError) as raised:
            search.build_operator_composition(context, search.required_target_fields(target["target_contract"]), depth=0)

        self.assertEqual("missing_constraint", raised.exception.taxonomy)
        self.assertIn("unapplied_window_constraint_keys", json.dumps(raised.exception.details, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
