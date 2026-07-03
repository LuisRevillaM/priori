from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from scripts.runtime.envelope_conformance_report import main as conformance_report_main
from tqe.runtime.catalog import output, primitive
from tqe.runtime.envelope import (
    CapabilityChannel,
    CapabilityEnvelope,
    ChannelKind,
    CONFORMANCE_ENV_VAR,
    check_envelope_conformance,
    conformance_enabled,
    legacy_envelope_from_runtime_values,
)
from tqe.runtime.ir import Cardinality, EntityScope, PayloadType, TemporalContainer, Unit
from tqe.runtime.values import FrameSignal, runtime_value_from_raw


class EnvelopeConformanceTests(unittest.TestCase):
    def test_valid_envelope_has_no_findings(self) -> None:
        entry = sample_entry()
        envelope = CapabilityEnvelope(
            capability_name="sample_status",
            node_id="n1",
            channels={
                "status": CapabilityChannel(
                    name="status",
                    kind=ChannelKind.FRAME_SIGNAL,
                    value=runtime_value("status", ["PASS"]).value,
                )
            },
        )

        report = check_envelope_conformance(catalog_entry=entry, envelope=envelope)

        self.assertEqual(0, report.finding_count)

    def test_undeclared_channel_is_reported(self) -> None:
        entry = sample_entry()
        envelope = CapabilityEnvelope(
            capability_name="sample_status",
            node_id="n1",
            channels={
                "status": CapabilityChannel(
                    name="status",
                    kind=ChannelKind.FRAME_SIGNAL,
                    value=runtime_value("status", ["PASS"]).value,
                ),
                "extra": CapabilityChannel(name="extra", kind=ChannelKind.SCALAR, value=True),
            },
        )

        report = check_envelope_conformance(catalog_entry=entry, envelope=envelope)

        self.assertEqual({"undeclared_channel"}, {finding.code for finding in report.findings})

    def test_missing_declared_channel_is_reported(self) -> None:
        report = check_envelope_conformance(
            catalog_entry=sample_entry(),
            envelope=CapabilityEnvelope(capability_name="sample_status", node_id="n1", channels={}),
        )

        self.assertEqual({"missing_declared_channel"}, {finding.code for finding in report.findings})

    def test_wrong_temporal_type_is_reported(self) -> None:
        entry = sample_entry()
        envelope = CapabilityEnvelope(
            capability_name="sample_status",
            node_id="n1",
            channels={
                "status": CapabilityChannel(name="status", kind=ChannelKind.SCALAR, value="PASS")
            },
        )

        report = check_envelope_conformance(catalog_entry=entry, envelope=envelope)

        self.assertEqual({"wrong_temporal_type"}, {finding.code for finding in report.findings})

    def test_enum_out_of_domain_is_reported(self) -> None:
        entry = sample_entry()
        envelope = CapabilityEnvelope(
            capability_name="sample_status",
            node_id="n1",
            channels={
                "status": CapabilityChannel(
                    name="status",
                    kind=ChannelKind.FRAME_SIGNAL,
                    value=FrameSignal(
                        frame_ids=[0],
                        values=["MAYBE"],
                        unknown_mask=[False],
                        unit=Unit.NONE,
                        entity_scope=EntityScope.ANCHOR,
                    ),
                )
            },
        )

        report = check_envelope_conformance(catalog_entry=entry, envelope=envelope)

        self.assertEqual({"enum_value_out_of_domain"}, {finding.code for finding in report.findings})

    def test_legacy_envelope_preserves_records_and_witness_refs(self) -> None:
        value = runtime_value("status", ["PASS"])
        raw_outputs = {
            "status": value.value,
            "status_records": [
                {
                    "anchor_id": "a1",
                    "anchor_frame_id": 10,
                    "status": "PASS",
                    "status_reason": "observed",
                }
            ],
        }

        envelope = legacy_envelope_from_runtime_values(
            capability_name="sample_status",
            node_id="n1",
            raw_outputs=raw_outputs,
            runtime_values={"status": value},
        )

        self.assertEqual(["status"], sorted(envelope.channels))
        self.assertEqual(1, len(envelope.evidence_records))
        self.assertEqual(10, envelope.witness_refs[0].frame_id)

    def test_legacy_envelope_preserves_aux_values_outside_channels(self) -> None:
        value = runtime_value("status", ["PASS"])
        raw_outputs = {
            "status": value.value,
            "summary": {"episode_count": 2},
            "source_results": [{"result_id": "r1"}],
            "anchor_source": "anchors",
            "predicate_facts": [{"predicate_id": "p1"}],
            "candidate_evaluations_records": [{"anchor_id": "a1"}],
        }

        envelope = legacy_envelope_from_runtime_values(
            capability_name="sample_status",
            node_id="n1",
            raw_outputs=raw_outputs,
            runtime_values={"status": value},
        )

        self.assertEqual(["status"], sorted(envelope.channels))
        self.assertEqual(
            {
                "summary",
                "source_results",
                "anchor_source",
                "predicate_facts",
                "candidate_evaluations_records",
            },
            set(envelope.aux),
        )
        self.assertEqual({"episode_count": 2}, envelope.aux["summary"])

    def test_conformance_report_script_smoke_writes_json(self) -> None:
        with patch.dict(os.environ, {CONFORMANCE_ENV_VAR: "off"}):
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "envelope-report.json"
                with redirect_stdout(StringIO()):
                    exit_code = conformance_report_main(
                        [
                            "--plan",
                            "config/query-plans/q6_throw_in_first_action_under_pressure.experimental.v1.json",
                            "--match-id",
                            "J03WOH",
                            "--period",
                            "firstHalf",
                            "--output",
                            str(output_path),
                        ]
                    )

                payload = json.loads(output_path.read_text(encoding="utf-8"))

            self.assertFalse(conformance_enabled())
            self.assertEqual("off", os.environ[CONFORMANCE_ENV_VAR])

        self.assertEqual(0, exit_code)
        self.assertEqual("f2_0.envelope_conformance_report.v1", payload["schema_version"])
        self.assertGreaterEqual(payload["finding_count"], 0)


def sample_entry():
    return primitive(
        name="sample_status",
        version="0.1.0",
        purpose="test",
        outputs=[
            output(
                name="status",
                temporal_type=TemporalContainer.FRAME_SIGNAL,
                payload_type=PayloadType.ENUM,
                cardinality=Cardinality.SINGLE,
                unit=Unit.NONE,
                entity_scope=EntityScope.ANCHOR,
                evidence_fields=["status", "status_reason"],
                allowed_values=["PASS", "FAIL", "UNKNOWN"],
            )
        ],
        evidence_fields=["status", "status_reason"],
    )


def runtime_value(name: str, values: list[str]):
    return runtime_value_from_raw(
        node_id="n1",
        output=output(
            name=name,
            temporal_type=TemporalContainer.FRAME_SIGNAL,
            payload_type=PayloadType.ENUM,
            cardinality=Cardinality.SINGLE,
            allowed_values=["PASS", "FAIL", "UNKNOWN"],
        ),
        raw_value=values,
        frame_ids=list(range(len(values))),
    )
