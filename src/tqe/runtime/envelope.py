"""Typed capability envelopes and shadow conformance checks.

F2-0 introduces the shape of the future capability contract without changing
runtime behavior.  The helpers here can view today's legacy ``state.signals``
payloads as envelopes, validate them against catalog declarations, and report
findings in shadow mode only.

Auxiliary payloads preserve legacy runtime metadata values such as ``summary``,
``source_results``, and ``anchor_source`` without promoting them to declared
outputs.  Aux is non-evidentiary, never product-visible, and never consulted by
trace or evidence projection.  Each extraction packet must explicitly promote
family-specific aux data to a declared channel or leave it aux.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from tqe.runtime.ir import BoundCatalogNode, CatalogEntry, NodeKind, TemporalContainer
from tqe.runtime.values import FrameSignal, RuntimeValue

LOGGER = logging.getLogger(__name__)
CONFORMANCE_ENV_VAR = "TQE_ENVELOPE_CONFORMANCE"


class ChannelKind(StrEnum):
    """Envelope channel roles observed in legacy runtime signals."""

    EPISODE_SET = "episode_set"
    RELATION_EPISODE_SET = "relation_episode_set"
    FRAME_SIGNAL = "frame_signal"
    ANCHOR_EVALUATIONS = "anchor_evaluations"
    SCALAR = "scalar"


@dataclass(frozen=True)
class WitnessRef:
    """Reference to a record/frame/entity used as evidence for a channel."""

    source_channel: str
    record_index: int | None = None
    record_id: str | None = None
    frame_id: int | None = None
    entity_id: str | None = None


@dataclass(frozen=True)
class EvidenceRecord:
    """Evidence attached to a declared output channel."""

    output_name: str
    fields: dict[str, Any]
    witness_refs: tuple[WitnessRef, ...] = ()


@dataclass(frozen=True)
class CoverageChannel:
    """Optional coverage/status channel slot for later F2 packets."""

    output_name: str
    status_field: str | None = None
    reason_field: str | None = None
    value: Any = None


@dataclass(frozen=True)
class CapabilityChannel:
    """One named output channel emitted by a capability."""

    name: str
    kind: ChannelKind
    value: Any
    evidence: tuple[EvidenceRecord, ...] = ()
    coverage: CoverageChannel | None = None

    @property
    def declared_temporal_type(self) -> TemporalContainer:
        if self.kind == ChannelKind.ANCHOR_EVALUATIONS:
            return TemporalContainer.EPISODE_SET
        return TemporalContainer(self.kind.value)


@dataclass(frozen=True)
class CapabilityEnvelope:
    """Lossless envelope view over one capability execution."""

    capability_name: str
    node_id: str
    channels: dict[str, CapabilityChannel]
    aux: dict[str, Any] = field(default_factory=dict)
    evidence_records: tuple[EvidenceRecord, ...] = ()
    witness_refs: tuple[WitnessRef, ...] = ()
    raw_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConformanceFinding:
    capability_name: str
    node_id: str
    code: str
    message: str
    output_name: str | None = None


@dataclass(frozen=True)
class ConformanceReport:
    capability_name: str
    node_id: str
    findings: tuple[ConformanceFinding, ...]

    @property
    def finding_count(self) -> int:
        return len(self.findings)


def envelope_conformance_mode() -> str:
    mode = os.environ.get(CONFORMANCE_ENV_VAR, "off").strip().lower()
    if mode not in {"off", "warn"}:
        return "off"
    return mode


def conformance_enabled() -> bool:
    return envelope_conformance_mode() == "warn"


def legacy_envelope_from_runtime_values(
    *,
    capability_name: str,
    node_id: str,
    raw_outputs: dict[str, Any],
    runtime_values: dict[str, RuntimeValue],
) -> CapabilityEnvelope:
    """Build an envelope from today's raw signal dict and RuntimeValue objects."""

    channels: dict[str, CapabilityChannel] = {}
    evidence_records: list[EvidenceRecord] = []
    witness_refs: list[WitnessRef] = []
    for output_name, runtime_value in runtime_values.items():
        records = _records_for_output(output_name, raw_outputs, runtime_value)
        channel_evidence = tuple(
            EvidenceRecord(
                output_name=output_name,
                fields=dict(record),
                witness_refs=tuple(_witness_refs_for_record(output_name, index, record)),
            )
            for index, record in enumerate(records)
            if isinstance(record, dict)
        )
        evidence_records.extend(channel_evidence)
        for evidence in channel_evidence:
            witness_refs.extend(evidence.witness_refs)
        channels[output_name] = CapabilityChannel(
            name=output_name,
            kind=_channel_kind(output_name, runtime_value),
            value=runtime_value.value,
            evidence=channel_evidence,
        )

    declared_like = set(channels)
    aux: dict[str, Any] = {}
    for key, value in raw_outputs.items():
        if key in declared_like:
            continue
        if _is_aux_key(key):
            aux[key] = value
            continue
        if _is_record_key(key):
            continue
        channels[key] = CapabilityChannel(name=key, kind=_infer_channel_kind(value), value=value)

    return CapabilityEnvelope(
        capability_name=capability_name,
        node_id=node_id,
        channels=channels,
        aux=aux,
        evidence_records=tuple(evidence_records),
        witness_refs=tuple(witness_refs),
        raw_keys=tuple(sorted(str(key) for key in raw_outputs)),
    )


def check_envelope_conformance(
    *,
    catalog_entry: CatalogEntry,
    envelope: CapabilityEnvelope,
) -> ConformanceReport:
    findings: list[ConformanceFinding] = []
    declared_outputs = {output.name: output for output in catalog_entry.outputs}

    for output_name, output in declared_outputs.items():
        channel = envelope.channels.get(output_name)
        if channel is None:
            findings.append(
                _finding(envelope, "missing_declared_channel", f"missing declared output {output_name}", output_name)
            )
            continue
        if channel.declared_temporal_type != output.temporal_type:
            findings.append(
                _finding(
                    envelope,
                    "wrong_temporal_type",
                    (
                        f"{output_name} emitted {channel.declared_temporal_type.value}; "
                        f"catalog declares {output.temporal_type.value}"
                    ),
                    output_name,
                )
            )
        if output.allowed_values:
            observed = _observed_enum_values(channel.value)
            invalid = sorted(value for value in observed if value not in set(output.allowed_values))
            if invalid:
                findings.append(
                    _finding(
                        envelope,
                        "enum_value_out_of_domain",
                        f"{output_name} emitted undeclared enum values {invalid}",
                        output_name,
                    )
                )

    for channel_name in sorted(set(envelope.channels) - set(declared_outputs)):
        findings.append(
            _finding(
                envelope,
                "undeclared_channel",
                f"emitted undeclared channel {channel_name}",
                channel_name,
            )
        )

    declared_evidence_fields = set(catalog_entry.evidence_fields)
    for output in catalog_entry.outputs:
        declared_evidence_fields.update(output.evidence_fields)
    for evidence in envelope.evidence_records:
        extra = sorted(set(evidence.fields) - declared_evidence_fields)
        if extra:
            findings.append(
                _finding(
                    envelope,
                    "undeclared_evidence_field",
                    f"{evidence.output_name} evidence has undeclared fields {extra}",
                    evidence.output_name,
                )
            )

    return ConformanceReport(
        capability_name=envelope.capability_name,
        node_id=envelope.node_id,
        findings=tuple(findings),
    )


def warn_on_envelope_conformance(
    *,
    catalog_entry: CatalogEntry,
    envelope: CapabilityEnvelope,
) -> ConformanceReport:
    report = check_envelope_conformance(catalog_entry=catalog_entry, envelope=envelope)
    if conformance_enabled() and report.findings:
        for finding in report.findings:
            LOGGER.warning(
                "capability envelope conformance: %s.%s %s %s",
                finding.capability_name,
                finding.output_name or "*",
                finding.code,
                finding.message,
            )
    return report


def shadow_check_legacy_outputs(
    *,
    node: BoundCatalogNode,
    raw_outputs: dict[str, Any],
    runtime_values: dict[str, RuntimeValue],
) -> ConformanceReport:
    """Shadow-check one legacy node emission when the env flag is enabled."""

    catalog_entry = catalog_entry_for_bound_node(node)
    envelope = legacy_envelope_from_runtime_values(
        capability_name=node.catalog_ref,
        node_id=node.node_id,
        raw_outputs=raw_outputs,
        runtime_values=runtime_values,
    )
    return warn_on_envelope_conformance(catalog_entry=catalog_entry, envelope=envelope)


def catalog_entry_for_bound_node(node: BoundCatalogNode) -> CatalogEntry:
    from tqe.runtime.catalog import default_catalog

    catalog = default_catalog()
    entries = catalog.relations if node.kind == NodeKind.RELATION else catalog.primitives
    for entry in entries:
        if entry.name == node.catalog_ref and entry.version == node.version:
            return entry
    raise RuntimeError(f"No catalog entry for {node.kind.value} {node.catalog_ref}@{node.version}")


def _finding(
    envelope: CapabilityEnvelope,
    code: str,
    message: str,
    output_name: str | None,
) -> ConformanceFinding:
    return ConformanceFinding(
        capability_name=envelope.capability_name,
        node_id=envelope.node_id,
        code=code,
        message=message,
        output_name=output_name,
    )


def _channel_kind(output_name: str, runtime_value: RuntimeValue) -> ChannelKind:
    if output_name == "anchor_evaluations":
        return ChannelKind.ANCHOR_EVALUATIONS
    if runtime_value.temporal_type == TemporalContainer.RELATION_EPISODE_SET:
        return ChannelKind.RELATION_EPISODE_SET
    if runtime_value.temporal_type == TemporalContainer.EPISODE_SET:
        return ChannelKind.EPISODE_SET
    if runtime_value.temporal_type == TemporalContainer.FRAME_SIGNAL:
        return ChannelKind.FRAME_SIGNAL
    if runtime_value.temporal_type == TemporalContainer.SCALAR:
        return ChannelKind.SCALAR
    raise RuntimeError(f"Unsupported temporal type {runtime_value.temporal_type.value}")


def _infer_channel_kind(value: Any) -> ChannelKind:
    if isinstance(value, FrameSignal):
        return ChannelKind.FRAME_SIGNAL
    if isinstance(value, list):
        return ChannelKind.EPISODE_SET
    return ChannelKind.SCALAR


def _records_for_output(
    output_name: str,
    raw_outputs: dict[str, Any],
    runtime_value: RuntimeValue,
) -> list[dict[str, Any]]:
    records = raw_outputs.get(f"{output_name}_records")
    if records is None and output_name == "anchor_evaluations":
        records = raw_outputs.get("anchor_evaluations_records")
    if records is None:
        records = runtime_value.records
    if isinstance(records, list):
        return [record for record in records if isinstance(record, dict)]
    return []


def _witness_refs_for_record(
    output_name: str,
    record_index: int,
    record: dict[str, Any],
) -> list[WitnessRef]:
    frame_id = _first_int(record, ("anchor_frame_id", "frame_id", "start_frame_id"))
    entity_id = _first_text(record, ("entity_id", "player_id", "receiver_id", "passer_id", "carrier_id"))
    record_id = _first_text(record, ("anchor_id", "episode_id", "relation_id", "result_id"))
    return [
        WitnessRef(
            source_channel=output_name,
            record_index=record_index,
            record_id=record_id,
            frame_id=frame_id,
            entity_id=entity_id,
        )
    ]


def _first_int(record: dict[str, Any], names: tuple[str, ...]) -> int | None:
    for name in names:
        value = record.get(name)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return int(value)
    return None


def _first_text(record: dict[str, Any], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = record.get(name)
        if isinstance(value, str) and value:
            return value
    return None


def _is_record_key(key: str) -> bool:
    return key.endswith("_records")


def _is_aux_key(key: str) -> bool:
    return key.endswith("_facts") or key in {
        "anchor_source",
        "summary",
        "source_results",
        "candidate_evaluations_records",
        "predicate_facts",
    }


def _observed_enum_values(value: Any) -> set[str]:
    if isinstance(value, FrameSignal):
        return {str(item) for item in value.values if item is not None}
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        observed: set[str] = set()
        for item in value:
            if isinstance(item, str):
                observed.add(item)
            elif isinstance(item, dict):
                for candidate_key in ("status", "evaluation_status", "temporal_status", "classification"):
                    candidate = item.get(candidate_key)
                    if isinstance(candidate, str):
                        observed.add(candidate)
        return observed
    return set()
