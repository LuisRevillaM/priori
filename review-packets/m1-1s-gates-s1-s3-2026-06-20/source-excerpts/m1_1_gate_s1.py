"""Verify M1.1S Gate S1: runtime value and result type hardening."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from tqe.runtime.binder import bind_document_from_path
from tqe.runtime.catalog import output
from tqe.runtime.executor import TacticalQueryExecutor, runtime_parameters
from tqe.runtime.ir import (
    Cardinality,
    EntityScope,
    PayloadType,
    TemporalContainer,
    Unit,
)
from tqe.runtime.values import FrameSignal, runtime_value_from_raw

REPORT_PATH = Path("artifacts/m1.1/gate-s1-verification-report.json")
APPROVED_PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pass_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "pass", "message": message, "details": details or {}}


def fail_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "fail", "message": message, "details": details or {}}


def build_report() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.extend(validate_frame_signal_alignment())
    checks.extend(validate_no_m1_dict_laundering())
    checks.extend(validate_episode_schema_checks())
    checks.extend(validate_runtime_execution_outputs())
    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.1S",
        "gate": "Gate_S1_runtime_value_result_type_hardening",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    return report


def validate_frame_signal_alignment() -> list[dict[str, Any]]:
    value = runtime_value_from_raw(
        node_id="alignment_probe",
        output=number_frame_output("centroid_y"),
        raw_value=pd.Series({10: 1.5, 12: 3.5}),
        frame_ids=[10, 11, 12],
    )
    signal = value.value
    return [
        pass_check(
            "runtime.frame_signal_preserves_alignment_and_unknown_mask",
            "frame signal preserves supplied frame IDs and missing values as UNKNOWN",
            {
                "frame_ids": signal.frame_ids,
                "values": signal.values,
                "unknown_mask": signal.unknown_mask,
            },
        )
        if isinstance(signal, FrameSignal)
        and signal.frame_ids == [10, 11, 12]
        and signal.values == [1.5, None, 3.5]
        and signal.unknown_mask == [False, True, False]
        else fail_check(
            "runtime.frame_signal_preserves_alignment_and_unknown_mask",
            "frame signal dropped alignment or failed to preserve UNKNOWN",
            {"value": repr(signal)},
        )
    ]


def validate_no_m1_dict_laundering() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    probes = [
        (
            "runtime.rejects_result_dict_as_number_frame_signal",
            number_frame_output("signed_shift"),
            [{"signed_shift_metres": 3.2}],
        ),
        (
            "runtime.rejects_result_dict_as_enum_frame_signal",
            enum_frame_output("classification"),
            [{"classification": "SWITCHED"}],
        ),
    ]
    for check_id, probe_output, raw_value in probes:
        try:
            runtime_value_from_raw(
                node_id="m1_laundering_probe",
                output=probe_output,
                raw_value=raw_value,
            )
        except RuntimeError as error:
            checks.append(
                pass_check(
                    check_id,
                    "runtime rejects structured M1 result dictionaries as frame-signal payloads",
                    {"error": str(error)},
                )
            )
        else:
            checks.append(
                fail_check(
                    check_id,
                    "runtime accepted an M1-shaped result dictionary as a frame signal",
                )
            )
    return checks


def validate_episode_schema_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    episode_output = output(
        name="episodes",
        temporal_type=TemporalContainer.EPISODE_SET,
        payload_type=PayloadType.BOOLEAN,
        cardinality=Cardinality.COLLECTION,
        entity_scope=EntityScope.POSSESSION,
    )
    relation_output = output(
        name="episodes",
        temporal_type=TemporalContainer.RELATION_EPISODE_SET,
        payload_type=PayloadType.RELATION_REF,
        cardinality=Cardinality.COLLECTION,
        entity_scope=EntityScope.RELATION,
    )
    checks.append(expect_runtime_error(
        check_id="runtime.rejects_episode_without_frame_identity",
        probe=lambda: runtime_value_from_raw(
            node_id="episode_probe",
            output=episode_output,
            raw_value=[{"duration_seconds": 2.0}],
        ),
    ))
    checks.append(expect_runtime_error(
        check_id="runtime.rejects_relation_without_frame_window",
        probe=lambda: runtime_value_from_raw(
            node_id="relation_probe",
            output=relation_output,
            raw_value=[{"relation_id": "r1"}],
        ),
    ))
    valid_relation = runtime_value_from_raw(
        node_id="relation_probe",
        output=relation_output,
        raw_value=[{"relation_id": "r1", "open_frame_id": 10, "close_frame_id": 20}],
    )
    checks.append(
        pass_check(
            "runtime.accepts_relation_with_id_and_window",
            "relation episode set accepts declared relation ID plus frame window",
            {"count": len(valid_relation.value)},
        )
    )
    return checks


def validate_runtime_execution_outputs() -> list[dict[str, Any]]:
    bound = bind_document_from_path(APPROVED_PLAN_PATH)
    executor = TacticalQueryExecutor()
    state = executor._execute_period(  # noqa: SLF001 - verifier inspects runtime contract directly.
        bound_plan=bound,
        match_id="J03WOY",
        period="firstHalf",
        params=runtime_parameters(bound),
    )
    checks: list[dict[str, Any]] = []
    missing_provenance: list[str] = []
    frame_signal_failures: list[str] = []
    for node_id, outputs in state.runtime_values.items():
        for output_name, runtime_value in outputs.items():
            if runtime_value.provenance.get("node_id") != node_id or runtime_value.provenance.get("output_name") != output_name:
                missing_provenance.append(f"{node_id}.{output_name}")
            if runtime_value.temporal_type == TemporalContainer.FRAME_SIGNAL:
                if not isinstance(runtime_value.value, FrameSignal):
                    frame_signal_failures.append(f"{node_id}.{output_name}")
                elif any(isinstance(item, dict) for item in runtime_value.value.values):
                    frame_signal_failures.append(f"{node_id}.{output_name}:structured_payload")
    checks.append(
        pass_check(
            "runtime.actual_outputs_carry_declared_provenance",
            "every actual runtime output carries node/output provenance and declared type metadata",
            {"runtime_value_count": sum(len(outputs) for outputs in state.runtime_values.values())},
        )
        if not missing_provenance
        else fail_check(
            "runtime.actual_outputs_carry_declared_provenance",
            "one or more runtime outputs lack declared provenance",
            {"missing": missing_provenance},
        )
    )
    checks.append(
        pass_check(
            "runtime.actual_frame_signals_are_typed_containers",
            "actual frame-signal outputs are FrameSignal containers without structured M1 dict payloads",
            {"frame_signal_count": sum(
                1
                for outputs in state.runtime_values.values()
                for runtime_value in outputs.values()
                if runtime_value.temporal_type == TemporalContainer.FRAME_SIGNAL
            )},
        )
        if not frame_signal_failures
        else fail_check(
            "runtime.actual_frame_signals_are_typed_containers",
            "one or more runtime frame signals are not hardened containers",
            {"failures": frame_signal_failures},
        )
    )
    return checks


def expect_runtime_error(*, check_id: str, probe: Any) -> dict[str, Any]:
    try:
        probe()
    except RuntimeError as error:
        return pass_check(check_id, "runtime rejected invalid output shape", {"error": str(error)})
    return fail_check(check_id, "runtime accepted invalid output shape")


def number_frame_output(name: str) -> Any:
    return output(
        name=name,
        temporal_type=TemporalContainer.FRAME_SIGNAL,
        payload_type=PayloadType.NUMBER,
        cardinality=Cardinality.SINGLE,
        unit=Unit.METRE,
        entity_scope=EntityScope.TEAM,
    )


def enum_frame_output(name: str) -> Any:
    return output(
        name=name,
        temporal_type=TemporalContainer.FRAME_SIGNAL,
        payload_type=PayloadType.ENUM,
        cardinality=Cardinality.SINGLE,
        entity_scope=EntityScope.POSSESSION,
    )


def main() -> int:
    report = build_report()
    print(f"Wrote {REPORT_PATH}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
