from __future__ import annotations

import unittest
from types import SimpleNamespace

from tqe.evidence.observation_manifest import (
    ObservationCoverage,
    ObservationCoverageRow,
    ObservationManifestDocument,
    ObservationModality,
    ObservationWindow,
)
from tqe.runtime.ir import CatalogOutput, MissingDataSemantics, TypedValue
from tqe.runtime.operators.aggregate_over import execute_aggregate_over
from tqe.runtime.operators.sequence_pattern import SEQUENCE_PATTERN_SIGNATURE, execute_sequence_pattern
from tqe.runtime.values import canonical_anchor_record_id, runtime_value_from_raw


def typed_enum(value: str) -> TypedValue:
    return TypedValue(payload_type="enum", value=value)


def typed_number(value: float, unit: str = "none") -> TypedValue:
    return TypedValue(payload_type="number", value=value, unit=unit)


def typed_bool(value: bool) -> TypedValue:
    return TypedValue(payload_type="boolean", value=value)


def typed_entity_set(values: list[str]) -> TypedValue:
    return TypedValue(payload_type="entity_set", value=values)


def certified_observation_coverage() -> ObservationCoverage:
    return ObservationCoverage(
        ObservationManifestDocument(
            schema_version="tqe.observation_manifest.v1",
            manifest_id="sequence-pattern-test-certified",
            producer="test",
            rows=tuple(
                ObservationCoverageRow(
                    row_id=f"TST:firstHalf:{modality.value}",
                    modality=modality,
                    match_id="TST",
                    period="firstHalf",
                    window=ObservationWindow(start_frame_id=0, end_frame_id=1_000_000),
                    status="CERTIFIED",
                    reason="synthetic fixture declares complete observation",
                    provenance_token="test:TST:firstHalf",
                )
                for modality in ObservationModality
            ),
        ),
        manifest_path=None,
    )


def stage_output(name: str) -> CatalogOutput:
    input_def = {item.name: item for item in SEQUENCE_PATTERN_SIGNATURE.inputs}[name]
    return CatalogOutput(
        name="anchor_evaluations",
        temporal_type=input_def.temporal_type,
        payload_type=input_def.payload_type,
        cardinality=input_def.cardinality,
        unit=input_def.unit,
        entity_scope=input_def.entity_scope,
        missing_data_semantics=MissingDataSemantics.UNKNOWN,
        evidence_fields=[
            "anchor_id",
            "anchor_frame_id",
            "transition_frame_id",
            "transition_status",
            "new_team_role",
            "carry_start_frame_id",
            "carry_end_frame_id",
            "carry_status",
            "carry_forward_progression_m",
            "controlled_reception_frame_id",
            "controlled_pass_status",
            "team_role",
            "possession_id",
            "player_id",
            "match_id",
            "period",
            "perspective_team_role",
        ],
    )


def runtime_stage(name: str, records: list[dict[str, object]]):
    return runtime_value_from_raw(
        node_id=name,
        output=stage_output(name),
        raw_value=records,
        frame_ids=[int(record["anchor_frame_id"]) for record in records] or [0],
        records=records,
    )


def regain(frame: int, *, status: str = "PASS", team: str = "home", possession: str = "p1") -> dict[str, object]:
    record = {
        "anchor_frame_id": frame,
        "start_frame_id": frame,
        "end_frame_id": frame,
        "transition_frame_id": frame,
        "transition_status": status,
        "new_team_role": team,
        "team_role": team,
        "possession_id": possession,
        "player_id": "carrier-1",
        "match_id": "TST",
        "period": "firstHalf",
        "perspective_team_role": team,
    }
    record["anchor_id"] = canonical_anchor_record_id(record)
    return record


def carry(
    start: int,
    end: int,
    *,
    status: str = "PASS",
    team: str = "home",
    possession: str = "p1",
    progression: float = 4.0,
) -> dict[str, object]:
    record = {
        "anchor_frame_id": start,
        "start_frame_id": start,
        "end_frame_id": end,
        "carry_start_frame_id": start,
        "carry_end_frame_id": end,
        "carry_status": status,
        "carry_forward_progression_m": progression,
        "team_role": team,
        "possession_id": possession,
        "player_id": "carrier-1",
        "match_id": "TST",
        "period": "firstHalf",
        "perspective_team_role": team,
    }
    record["anchor_id"] = canonical_anchor_record_id(record)
    return record


def controlled_pass(frame: int, *, status: str = "PASS", team: str = "home", possession: str = "p1") -> dict[str, object]:
    record = {
        "anchor_frame_id": frame,
        "start_frame_id": frame,
        "end_frame_id": frame,
        "controlled_reception_frame_id": frame,
        "controlled_pass_status": status,
        "team_role": team,
        "possession_id": possession,
        "player_id": "carrier-1",
        "match_id": "TST",
        "period": "firstHalf",
        "perspective_team_role": team,
    }
    record["anchor_id"] = canonical_anchor_record_id(record)
    return record


def sequence_params(*, match_policy: str = "first", same_possession: bool = True) -> dict[str, TypedValue]:
    return {
        "stage_count": typed_number(3, "count"),
        "match_policy": typed_enum(match_policy),
        "overlap_policy": typed_enum("allow_overlaps"),
        "window_boundary_policy": typed_enum("exclusive_start_inclusive_end"),
        "frame_rate_hz": typed_number(25.0, "hertz"),
        "stage_2_window_seconds": typed_number(5.0, "second"),
        "stage_3_window_seconds": typed_number(4.0, "second"),
        "stage_1_status_field": typed_enum("transition_status"),
        "stage_2_status_field": typed_enum("carry_status"),
        "stage_3_status_field": typed_enum("controlled_pass_status"),
        "stage_1_frame_field": typed_enum("transition_frame_id"),
        "stage_2_frame_field": typed_enum("carry_start_frame_id"),
        "stage_3_frame_field": typed_enum("controlled_reception_frame_id"),
        "stage_1_end_frame_field": typed_enum("none"),
        "stage_2_end_frame_field": typed_enum("carry_end_frame_id"),
        "stage_3_end_frame_field": typed_enum("controlled_reception_frame_id"),
        "stage_1_team_role_field": typed_enum("new_team_role"),
        "stage_2_team_role_field": typed_enum("team_role"),
        "stage_3_team_role_field": typed_enum("team_role"),
        "stage_1_possession_id_field": typed_enum("possession_id"),
        "stage_2_possession_id_field": typed_enum("possession_id"),
        "stage_3_possession_id_field": typed_enum("possession_id"),
        "stage_1_player_id_field": typed_enum("player_id"),
        "stage_2_player_id_field": typed_enum("player_id"),
        "stage_3_player_id_field": typed_enum("player_id"),
        "stage_2_minimum_numeric_field": typed_enum("carry_forward_progression_m"),
        "stage_2_minimum_numeric_value": typed_number(3.0),
        "same_team_perspective_required": typed_bool(True),
        "same_possession_required": typed_bool(same_possession),
        "possession_continuity_source": typed_enum("stage_fields"),
        "same_player_required": typed_bool(False),
        "constraint_opt_out_reason": typed_enum("entity identity is not part of the counterattack initiation chain"),
        "team_role_field": typed_enum("team_role"),
    }


def run_sequence(
    stage_1: list[dict[str, object]],
    stage_2: list[dict[str, object]],
    stage_3: list[dict[str, object]],
    *,
    frame_ids: list[int] | None = None,
    match_policy: str = "first",
    overlap_policy: str = "allow_overlaps",
    same_possession: bool = True,
    parameter_overrides: dict[str, TypedValue] | None = None,
    possession_role: list[str] | None = None,
    ball_alive: list[bool] | None = None,
    observation_coverage: ObservationCoverage | None = None,
) -> list[dict[str, object]]:
    state = SimpleNamespace(
        match_id="TST",
        period="firstHalf",
        perspective_team_role="home",
        frame_ids=frame_ids or list(range(0, 401)),
        possession_role=possession_role,
        ball_alive=ball_alive,
        signals={},
        observation_coverage=observation_coverage or certified_observation_coverage(),
    )
    node = SimpleNamespace(
        node_id="sequence",
        inputs={
            "stage_1": SimpleNamespace(source_node_id="regains", output_name="anchor_evaluations"),
            "stage_2": SimpleNamespace(source_node_id="carries", output_name="anchor_evaluations"),
            "stage_3": SimpleNamespace(source_node_id="passes", output_name="anchor_evaluations"),
        },
    )
    parameters = sequence_params(match_policy=match_policy, same_possession=same_possession)
    parameters["overlap_policy"] = typed_enum(overlap_policy)
    if parameter_overrides:
        parameters.update(parameter_overrides)
    execute_sequence_pattern(
        state=state,
        node=node,
        inputs={
            "stage_1": runtime_stage("stage_1", stage_1),
            "stage_2": runtime_stage("stage_2", stage_2),
            "stage_3": runtime_stage("stage_3", stage_3),
        },
        parameters=parameters,
    )
    return state.signals["sequence"]["chain_records"]


class SequencePatternOperatorTests(unittest.TestCase):
    def test_full_pass_chain(self) -> None:
        [result] = run_sequence([regain(100)], [carry(150, 175)], [controlled_pass(250)])

        self.assertEqual("PASS", result["chain_status"])
        self.assertEqual("all_stages_pass", result["chain_reason"])
        self.assertEqual(100, result["stage_1_frame_id"])
        self.assertEqual(150, result["stage_2_frame_id"])
        self.assertEqual(250, result["stage_3_frame_id"])
        self.assertEqual(3, result["witness_stage_count"])

    def test_fail_only_when_window_fully_observed_and_empty(self) -> None:
        [result] = run_sequence([regain(100)], [], [], frame_ids=list(range(0, 401)))

        self.assertEqual("FAIL", result["chain_status"])
        self.assertEqual("stage_2_fully_observed_empty_window", result["chain_reason"])

    def test_empty_window_is_unknown_when_observation_manifest_is_absent(self) -> None:
        result = run_sequence(
            [regain(100)],
            [],
            [],
            observation_coverage=ObservationCoverage.from_path(None),
        )[0]

        self.assertEqual("UNKNOWN", result["chain_status"])
        self.assertIn("uncertified_observation_coverage[", result["chain_reason"])
        self.assertFalse(result["stage_2_window_truncated"])

    def test_truncated_window_is_unknown_not_fail(self) -> None:
        [result] = run_sequence([regain(950)], [], [], frame_ids=list(range(0, 1001)))

        self.assertEqual("UNKNOWN", result["chain_status"])
        self.assertEqual("stage_2_window_truncated", result["chain_reason"])
        self.assertTrue(result["stage_2_window_truncated"])

    def test_coverage_gap_window_is_unknown_not_fail(self) -> None:
        observed_frames = [*range(0, 121), *range(126, 401)]
        results = run_sequence([regain(100)], [], [], frame_ids=observed_frames)
        [result] = results

        self.assertEqual(1, len(results))
        self.assertEqual("UNKNOWN", result["chain_status"])
        self.assertEqual("stage_2_window_truncated", result["chain_reason"])
        self.assertTrue(result["stage_2_window_truncated"])

    def test_unknown_status_candidate_is_unknown_not_fail(self) -> None:
        [result] = run_sequence([regain(100)], [carry(150, 175, status="UNKNOWN")], [])

        self.assertEqual("UNKNOWN", result["chain_status"])
        self.assertEqual("stage_2_unknown_candidate", result["chain_reason"])
        self.assertEqual("UNKNOWN", result["stage_2_status"])

    def test_missing_numeric_threshold_candidate_is_unknown_not_fail(self) -> None:
        unmeasured_carry = carry(150, 175)
        del unmeasured_carry["carry_forward_progression_m"]

        [result] = run_sequence([regain(100)], [unmeasured_carry], [])

        self.assertEqual("UNKNOWN", result["chain_status"])
        self.assertEqual("stage_2_unknown_candidate", result["chain_reason"])
        self.assertEqual(1, result["stage_2_candidate_count"])
        self.assertEqual(1, result["stage_2_unknown_candidate_count"])

    def test_continuity_violation_is_excluded(self) -> None:
        [result] = run_sequence([regain(100, team="home")], [carry(150, 175, team="away")], [])

        self.assertEqual("FAIL", result["chain_status"])
        self.assertEqual("stage_2_fully_observed_empty_window", result["chain_reason"])
        self.assertEqual(0, result["stage_2_candidate_count"])

    def test_both_team_patterns_are_preserved(self) -> None:
        results = run_sequence(
            [regain(100, team="home", possession="h1"), regain(300, team="away", possession="a1")],
            [carry(150, 175, team="home", possession="h1"), carry(325, 340, team="away", possession="a1")],
            [controlled_pass(250, team="home", possession="h1"), controlled_pass(420, team="away", possession="a1")],
            frame_ids=list(range(0, 501)),
        )

        self.assertEqual(2, len(results))
        self.assertEqual({"home", "away"}, {str(record["team_role"]) for record in results})
        self.assertTrue(all(record["chain_status"] == "PASS" for record in results))

    def test_match_policy_first_vs_all(self) -> None:
        first = run_sequence(
            [regain(100)],
            [carry(140, 160), carry(150, 175)],
            [controlled_pass(220)],
            match_policy="first",
        )
        all_matches = run_sequence(
            [regain(100)],
            [carry(140, 160), carry(150, 175)],
            [controlled_pass(220), controlled_pass(230)],
            match_policy="all",
        )

        self.assertEqual(1, len(first))
        self.assertGreater(len(all_matches), len(first))
        self.assertTrue(all(record["chain_status"] == "PASS" for record in all_matches))

    def test_non_overlapping_policy_excludes_reused_successors_with_policy_reason(self) -> None:
        results = run_sequence(
            [regain(100), regain(101)],
            [carry(150, 175)],
            [controlled_pass(250)],
            overlap_policy="non_overlapping",
        )

        self.assertEqual(2, len(results))
        self.assertEqual(["PASS", "FAIL"], [record["chain_status"] for record in results])
        self.assertEqual("stage_2_policy_excluded", results[1]["chain_reason"])
        self.assertEqual(0, results[1]["stage_2_candidate_count"])

    def test_successor_at_window_edge_is_included(self) -> None:
        [result] = run_sequence([regain(100)], [carry(225, 250)], [controlled_pass(350)])

        self.assertEqual("PASS", result["chain_status"])
        self.assertEqual(225, result["stage_2_frame_id"])
        self.assertEqual(350, result["stage_3_frame_id"])

    def test_successor_at_window_edge_plus_one_is_excluded(self) -> None:
        [result] = run_sequence([regain(100)], [carry(226, 250)], [], frame_ids=list(range(0, 401)))

        self.assertEqual("FAIL", result["chain_status"])
        self.assertEqual("stage_2_fully_observed_empty_window", result["chain_reason"])
        self.assertEqual(0, result["stage_2_candidate_count"])

    def test_observed_possession_stream_supplies_continuity_identity(self) -> None:
        frame_ids = list(range(0, 401))
        [result] = run_sequence(
            [regain(100)],
            [carry(150, 175)],
            [controlled_pass(250)],
            frame_ids=frame_ids,
            parameter_overrides={
                "stage_1_possession_id_field": typed_enum("none"),
                "stage_2_possession_id_field": typed_enum("none"),
                "stage_3_possession_id_field": typed_enum("none"),
                "possession_continuity_source": typed_enum("observed_possession_stream"),
            },
            possession_role=["home" for _ in frame_ids],
            ball_alive=[True for _ in frame_ids],
        )

        self.assertEqual("PASS", result["chain_status"])
        self.assertEqual("all_stages_pass", result["chain_reason"])

    def test_chain_records_compose_under_aggregate_over(self) -> None:
        records = []
        records.extend(run_sequence([regain(100)], [carry(150, 175)], [controlled_pass(250)]))
        records.extend(run_sequence([regain(200)], [], []))
        records.extend(run_sequence([regain(950)], [], [], frame_ids=list(range(0, 1001))))
        state = SimpleNamespace(match_id="TST", period="firstHalf", perspective_team_role="home", signals={})
        aggregate_node = SimpleNamespace(
            node_id="aggregate",
            inputs={"population": SimpleNamespace(source_node_id="sequence", output_name="chain_records")},
        )
        execute_aggregate_over(
            state=state,
            node=aggregate_node,
            inputs={"population": runtime_stage("stage_1", records)},
            parameters={
                "aggregation_kind": typed_enum("count"),
                "population_expression": typed_enum("counterattack initiation chains"),
                "group_by_fields": typed_entity_set(["team_role"]),
                "status_field": typed_enum("chain_status"),
                "same_team_perspective_required": typed_bool(True),
                "entity_identity_preserved_required": typed_bool(False),
                "frame_alignment_required": typed_bool(True),
                "constraint_opt_out_reason": typed_enum("entity identity is not part of the chain count"),
                "team_role_field": typed_enum("team_role"),
            },
        )

        [aggregate] = state.signals["aggregate"]["aggregate_records"]
        self.assertEqual(1, aggregate["pass_count"])
        self.assertEqual(1, aggregate["fail_count"])
        self.assertEqual(1, aggregate["unknown_count"])
        self.assertEqual(2, aggregate["upper_bound"])


if __name__ == "__main__":
    unittest.main()
