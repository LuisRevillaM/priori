from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from tqe.runtime.binder import BindError, bind_document, bind_error_codes
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows
from tqe.runtime.ir import CatalogOutput, MissingDataSemantics, TacticalQueryDocument, TypedValue
from tqe.runtime.operators.typed_join import TYPED_JOIN_SIGNATURE, execute_typed_join
from tqe.runtime.values import RuntimeValue, canonical_anchor_record_id, runtime_value_from_raw

from tests.support.canonical_data import CANONICAL_DATA_ROOT, requires_canonical_data


PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")
CAR_BUNDLE_PATH = Path("tests/fixtures/r1_5_fragile_possession_state_j03woh_bundle.json")


def typed_enum(value: str) -> TypedValue:
    return TypedValue(payload_type="enum", value=value)


def typed_bool(value: bool) -> TypedValue:
    return TypedValue(payload_type="boolean", value=value)


def typed_number(value: float, unit: str = "none") -> TypedValue:
    return TypedValue(payload_type="number", unit=unit, value=value)


def anchor_record(
    name: str,
    frame_id: int,
    *,
    team_role: str = "home",
    entity_id: str = "p1",
    status: str = "PASS",
    start: int | None = None,
    end: int | None = None,
) -> dict[str, object]:
    item: dict[str, object] = {
        "match_id": "TST",
        "period": "firstHalf",
        "anchor_frame_id": frame_id,
        "start_frame_id": frame_id if start is None else start,
        "end_frame_id": frame_id if end is None else end,
        "entity_refs": [team_role, entity_id],
        "team_role": team_role,
        "player_id": entity_id,
        "join_status": status,
        "name": name,
    }
    item["anchor_id"] = canonical_anchor_record_id(item)
    return item


def runtime_records_value(name: str, records: list[dict[str, object]], *, input_name: str) -> RuntimeValue:
    input_def = {item.name: item for item in TYPED_JOIN_SIGNATURE.inputs}[input_name]
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
                "player_id",
                "join_status",
            ],
        ),
        raw_value=records,
        frame_ids=[int(record["anchor_frame_id"]) for record in records],
        records=records,
    )


def operator_node() -> SimpleNamespace:
    return SimpleNamespace(
        node_id="join",
        inputs={
            "left": SimpleNamespace(source_node_id="left", output_name="left"),
            "right": SimpleNamespace(source_node_id="right", output_name="right"),
        },
    )


def run_join(
    left: list[dict[str, object]],
    right: list[dict[str, object]],
    *,
    join_key: str = "same_anchor",
    no_match_policy: str = "UNKNOWN",
    same_team: bool = True,
    entity: bool = False,
    frame: bool = False,
    unconstrained: bool = False,
    rationale: str = "none",
    max_frame_delta: int = 0,
    required_status: str = "PASS",
    left_required_status: str | None = None,
    right_required_status: str | None = None,
) -> dict[str, object]:
    state = SimpleNamespace(match_id="TST", period="firstHalf", signals={})
    execute_typed_join(
        state=state,
        node=operator_node(),
        inputs={
            "left": runtime_records_value("left", left, input_name="left"),
            "right": runtime_records_value("right", right, input_name="right"),
        },
        parameters={
            "join_key": typed_enum(join_key),
            "no_match_policy": typed_enum(no_match_policy),
            "same_team_perspective_required": typed_bool(same_team),
            "entity_identity_preserved_required": typed_bool(entity),
            "frame_alignment_required": typed_bool(frame),
            "unconstrained": typed_bool(unconstrained),
            "unconstrained_rationale": typed_enum(rationale),
            "left_anchor_id_field": typed_enum("anchor_id"),
            "right_anchor_id_field": typed_enum("anchor_id"),
            "left_frame_field": typed_enum("anchor_frame_id"),
            "right_frame_field": typed_enum("anchor_frame_id"),
            "left_entity_id_field": typed_enum("player_id"),
            "right_entity_id_field": typed_enum("player_id"),
            "left_start_frame_field": typed_enum("start_frame_id"),
            "left_end_frame_field": typed_enum("end_frame_id"),
            "right_start_frame_field": typed_enum("start_frame_id"),
            "right_end_frame_field": typed_enum("end_frame_id"),
            "left_team_role_field": typed_enum("team_role"),
            "right_team_role_field": typed_enum("team_role"),
            "left_status_field": typed_enum("join_status"),
            "right_status_field": typed_enum("join_status"),
            "required_status_value": typed_enum(required_status),
            "left_required_status_value": typed_enum(left_required_status or required_status),
            "right_required_status_value": typed_enum(right_required_status or required_status),
            "maximum_frame_delta": typed_number(max_frame_delta, "frame"),
        },
    )
    return state.signals["join"]


class TypedJoinOperatorTests(unittest.TestCase):
    def test_same_anchor_join_preserves_both_team_anchors(self) -> None:
        home_left = anchor_record("home-left", 100, team_role="home")
        away_left = anchor_record("away-left", 110, team_role="away", entity_id="p2")
        home_right = dict(home_left)
        away_right = dict(away_left)

        records = run_join([home_left, away_left], [home_right, away_right])["typed_join_records"]

        self.assertEqual(["PASS", "PASS"], [record["typed_join_status"] for record in records])
        self.assertEqual(["home", "away"], [record["left_team_role"] for record in records])
        self.assertEqual(["home", "away"], [record["right_team_role"] for record in records])

    def test_same_frame_window_key_allows_declared_delta(self) -> None:
        records = run_join(
            [anchor_record("left", 100)],
            [anchor_record("right", 102)],
            join_key="same_frame_window",
            frame=True,
            max_frame_delta=2,
        )["typed_join_records"]

        self.assertEqual("PASS", records[0]["typed_join_status"])
        self.assertEqual(100, records[0]["left_frame_id"])
        self.assertEqual(102, records[0]["right_frame_id"])

    def test_same_entity_key_requires_entity_identity(self) -> None:
        records = run_join(
            [anchor_record("left", 100, entity_id="carrier")],
            [anchor_record("right", 120, entity_id="carrier")],
            join_key="same_entity",
            entity=True,
        )["typed_join_records"]

        self.assertEqual("PASS", records[0]["typed_join_status"])
        self.assertEqual("carrier", records[0]["left_entity_id"])

    def test_episode_overlap_key_matches_overlapping_windows(self) -> None:
        records = run_join(
            [anchor_record("left", 100, start=90, end=110)],
            [anchor_record("right", 105, start=105, end=115)],
            join_key="episode_overlap",
        )["typed_join_records"]

        self.assertEqual("PASS", records[0]["typed_join_status"])
        self.assertEqual(90, records[0]["left_start_frame_id"])
        self.assertEqual(115, records[0]["right_end_frame_id"])

    def test_constraint_mismatch_uses_declared_no_match_policy(self) -> None:
        records = run_join(
            [anchor_record("left", 100, team_role="home")],
            [anchor_record("right", 100, team_role="away")],
            no_match_policy="FAIL",
        )["typed_join_records"]

        self.assertEqual("FAIL", records[0]["typed_join_status"])
        self.assertEqual("join_counterpart_missing_fail", records[0]["typed_join_reason"])

    def test_no_match_drop_policy_records_drop_count(self) -> None:
        records = run_join(
            [anchor_record("left", 100, team_role="home"), anchor_record("kept", 110, team_role="home")],
            [anchor_record("kept", 110, team_role="home")],
            no_match_policy="drop_with_count",
        )["typed_join_records"]

        self.assertEqual(1, len(records))
        self.assertEqual(1, records[0]["typed_join_dropped_no_match_count"])

    def test_unknown_side_status_propagates_to_join_unknown(self) -> None:
        left = anchor_record("left", 100)
        right = dict(left)
        right["join_status"] = "UNKNOWN"

        records = run_join([left], [right])["typed_join_records"]

        self.assertEqual("UNKNOWN", records[0]["typed_join_status"])
        self.assertEqual("join_side_status_unknown", records[0]["typed_join_reason"])

    def test_side_specific_required_status_values_allow_asymmetric_join(self) -> None:
        left = anchor_record("left", 100, status="PASS")
        right = dict(left)
        right["join_status"] = "FAIL"

        records = run_join(
            [left],
            [right],
            left_required_status="PASS",
            right_required_status="FAIL",
        )["typed_join_records"]

        self.assertEqual("PASS", records[0]["typed_join_status"])
        self.assertEqual("PASS", records[0]["left_required_status_value"])
        self.assertEqual("FAIL", records[0]["right_required_status_value"])
        self.assertEqual("FAIL", records[0]["right_status"])

    def test_bind_rejects_join_without_constraint_or_rationale(self) -> None:
        payload = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        source_node_id = payload["draft_plan"]["nodes"][0]["node_id"]
        payload["draft_plan"]["nodes"].append(
            {
                "kind": "operator",
                "node_id": "joinprobe",
                "operator": {"name": "typed_join", "version": "0.1.0"},
                "inputs": {
                    "left": {"source_node_id": source_node_id, "output_name": "anchors"},
                    "right": {"source_node_id": source_node_id, "output_name": "anchors"},
                },
                "parameters": {
                    "join_key": {"payload_type": "enum", "value": "same_anchor"},
                },
                "outputs": [output.model_dump(mode="json") for output in TYPED_JOIN_SIGNATURE.outputs],
            }
        )

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn("operator_join_constraints_missing", bind_error_codes(raised.exception))

    def test_bind_accepts_unconstrained_join_only_with_rationale(self) -> None:
        payload = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        source_node_id = payload["draft_plan"]["nodes"][0]["node_id"]
        node = {
            "kind": "operator",
            "node_id": "joinprobe",
            "operator": {"name": "typed_join", "version": "0.1.0"},
            "inputs": {
                "left": {"source_node_id": source_node_id, "output_name": "anchors"},
                "right": {"source_node_id": source_node_id, "output_name": "anchors"},
            },
            "parameters": {
                "join_key": {"payload_type": "enum", "value": "same_anchor"},
                "unconstrained": {"payload_type": "boolean", "value": True},
            },
            "outputs": [output.model_dump(mode="json") for output in TYPED_JOIN_SIGNATURE.outputs],
        }
        payload["draft_plan"]["nodes"].append(node)
        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))
        self.assertIn("operator_join_unconstrained_rationale_missing", bind_error_codes(raised.exception))

        node["parameters"]["unconstrained_rationale"] = {
            "payload_type": "enum",
            "value": "diagnostic_join_for_audit",
        }
        bound = bind_document(TacticalQueryDocument.model_validate(payload))
        self.assertTrue(bound.bound_plan_hash)


@requires_canonical_data
class TypedJoinCompositionSuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = json.loads(CAR_BUNDLE_PATH.read_text(encoding="utf-8"))

    def test_car0_composition_executes_for_both_team_perspectives(self) -> None:
        executor = TacticalQueryExecutor(canonical_root=CANONICAL_DATA_ROOT)
        role_counts: dict[str, int] = {}

        for role, document_payload in sorted(self.bundle["documents"].items()):
            bound = bind_document(TacticalQueryDocument.model_validate(document_payload))
            execution = executor.execute(bound)
            rows = execution_result_rows(execution)
            role_counts[role] = len(rows)

            self.assertEqual("pass", execution.status.value)
            self.assertEqual(0, execution.provenance["requested_evidence_failure_count"])
            self.assertGreater(len(rows), 0)
            for row in rows:
                requested = row["requested_evidence"]
                self.assertEqual("PASS", requested["typed_join_status"])
                self.assertEqual("PASS", requested["window_status"])
                self.assertEqual("PASS", requested["pressure_status"])
                self.assertEqual("FAIL", requested["support_arrival_status"])
                self.assertEqual(role, requested["left_team_role"])
                self.assertEqual(role, requested["right_team_role"])

        self.assertEqual({"away", "home"}, set(role_counts))
        self.assertGreater(role_counts["away"], 0)
        self.assertGreater(role_counts["home"], 0)

    def test_car0_executor_path_chains_window_into_typed_join(self) -> None:
        document_payload = self.bundle["documents"]["home"]
        nodes = document_payload["draft_plan"]["nodes"]
        operator_nodes = {
            node["node_id"]: node
            for node in nodes
            if node.get("kind") == "operator"
        }
        terminal_join = operator_nodes["typed_join_2"]

        self.assertEqual("typed_join", terminal_join["operator"]["name"])
        self.assertEqual("window", operator_nodes[terminal_join["inputs"]["left"]["source_node_id"]]["operator"]["name"])
        self.assertEqual(
            "typed_join",
            operator_nodes[terminal_join["inputs"]["right"]["source_node_id"]]["operator"]["name"],
        )

        bound = bind_document(TacticalQueryDocument.model_validate(document_payload))
        execution = TacticalQueryExecutor(canonical_root=CANONICAL_DATA_ROOT).execute(bound)
        rows = execution_result_rows(execution)

        self.assertEqual("pass", execution.status.value)
        self.assertGreater(len(rows), 0)
        self.assertTrue(
            all(row["requested_evidence"]["typed_join_reason"] == "typed_join_matched" for row in rows)
        )


if __name__ == "__main__":
    unittest.main()
