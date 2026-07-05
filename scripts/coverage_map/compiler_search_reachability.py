#!/usr/bin/env python3
"""Search-based compiler reachability v0.

This is the first non-pattern measurement path. Targets provide typed evidence
and predicate requirements only. The synthesizer performs bounded backward
search over reusable catalog entries and generic composition rules, then checks
whether the discovered plan binds and executes with complete requested evidence.
Coverage-map labels are used only after synthesis for audit/comparison.
"""

from __future__ import annotations

import collections
import concurrent.futures
import copy
import csv
import gzip
import json
import os
import pickle
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tqe.runtime.binder import BindError, bind_document  # noqa: E402
from tqe.runtime.catalog import default_catalog  # noqa: E402
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows  # noqa: E402
from tqe.runtime.ir import (  # noqa: E402
    CatalogEntry,
    CatalogInput,
    CatalogOutput,
    ExecutionStatus,
    NodeKind,
    TacticalQueryDocument,
    Unit,
    stable_hash,
)
from tqe.runtime.operators.delta_across_anchor import DELTA_ACROSS_ANCHOR_SIGNATURE  # noqa: E402
from tqe.runtime.operators.extremum_over_set import EXTREMUM_OVER_SET_SIGNATURE  # noqa: E402
from tqe.runtime.operators.project_onto_axis import PROJECT_ONTO_AXIS_SIGNATURE  # noqa: E402
from tqe.runtime.operators.typed_join import TYPED_JOIN_SIGNATURE  # noqa: E402
from tqe.runtime.operators.window import WINDOW_SIGNATURE  # noqa: E402


def repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


TARGETS = repo_path(os.environ.get("TQE_SEARCH_TARGETS", ROOT / "config" / "compiler-reachability" / "search-targets.v0.json"))
LEDGER = repo_path(os.environ.get("TQE_SEARCH_LEDGER", ROOT / "generated" / "coverage-map.json"))
OUT_DIR = repo_path(os.environ.get("TQE_SEARCH_OUT_DIR", ROOT / "generated" / "compiler-search-v0"))
PLAN_DIR = OUT_DIR / "plans"
ROW_LEDGER = OUT_DIR / "row-ledger.json"
ROW_CSV = OUT_DIR / "row-ledger.csv"
REPORT = repo_path(os.environ.get("TQE_SEARCH_REPORT", ROOT / "artifacts" / "autonomous" / "compiler-search-v0-report.json"))
UPDATE_LEDGER = os.environ.get("TQE_SEARCH_UPDATE_LEDGER", "1") != "0"
SHARED_NODE_CACHE_ENABLED = os.environ.get("TQE_SEARCH_SHARED_NODE_CACHE", "1") != "0"
PERSISTENT_NODE_CACHE_ENABLED = os.environ.get("TQE_SEARCH_PERSISTENT_NODE_CACHE", "0") == "1"
NODE_CACHE_ROOT = repo_path(
    os.environ.get("TQE_SEARCH_NODE_CACHE_ROOT", ROOT / "artifacts" / "autonomous" / "compiler-search-node-cache")
)

SYNTHESIZER_VERSION = "search_synthesizer.v0.1"
MAX_DEPTH = int(os.environ.get("TQE_SEARCH_MAX_DEPTH", "4"))
MAX_BRANCHING = int(os.environ.get("TQE_SEARCH_MAX_BRANCHING", "6"))
WORKERS = max(1, int(os.environ.get("TQE_SEARCH_WORKERS", "1")))
SEARCH_BUDGET_LABEL = f"max_depth={MAX_DEPTH}.max_branching={MAX_BRANCHING}"
SYNTHESIZER_STRATEGY = f"bounded_backward_search.v0.1.{SEARCH_BUDGET_LABEL}"
DEFAULT_MATCH_IDS = ["J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9", "J03WMX", "J03WN1"]
MATCH_IDS = [
    match_id.strip()
    for match_id in os.environ.get("TQE_SEARCH_MATCH_IDS", ",".join(DEFAULT_MATCH_IDS)).split(",")
    if match_id.strip()
]
PERSPECTIVE_TEAM_ROLES = [
    role.strip()
    for role in os.environ.get("TQE_SEARCH_PERSPECTIVE_TEAM_ROLES", "home").split(",")
    if role.strip()
]
if any(role not in {"home", "away"} for role in PERSPECTIVE_TEAM_ROLES):
    raise ValueError("TQE_SEARCH_PERSPECTIVE_TEAM_ROLES must contain only home and/or away")
if not PERSPECTIVE_TEAM_ROLES:
    raise ValueError("TQE_SEARCH_PERSPECTIVE_TEAM_ROLES cannot be empty")

SUPPORTED_MODALITIES = {"tracking", "events", "tracking_event_synchronized"}
SUPPORTED_COMPOSITION_CONSTRAINT_KINDS = {
    "before_after_same_anchor",
    "distinct_entity_fields",
    "frame_alignment",
    "relation_on_anchor",
    "same_anchor_identity",
    "same_player_return",
    "temporal_order",
    "delta_across_anchor",
    "extremum_over_set",
    "typed_join",
    "window",
    "vector_projection",
}
EXCLUDED_CATALOG_REFS = {
    "controlled_line_break_episode",
    "relation_destination_entry_classification",
    "outcome_classification",
}
CONCEPT_SHAPED_MACROS = sorted(EXCLUDED_CATALOG_REFS)


def main() -> int:
    targets_payload = load_json(TARGETS)
    coverage_rows = load_json(LEDGER)
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    for previous_plan in PLAN_DIR.glob("*.json"):
        previous_plan.unlink()

    results, cache_backend_summary = run_targets(
        targets=targets_payload["targets"],
        coverage_rows=coverage_rows,
    )

    if UPDATE_LEDGER:
        update_coverage_rows(coverage_rows, results)
        LEDGER.write_text(json.dumps(coverage_rows, indent=1) + "\n", encoding="utf-8")
    write_rows(results)
    report = build_report(
        targets_payload=targets_payload,
        coverage_rows=coverage_rows,
        results=results,
        cache_backend_summary=cache_backend_summary,
    )
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


def run_targets(*, targets: list[dict[str, Any]], coverage_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    worker_count = min(WORKERS, max(len(targets), 1))
    if worker_count <= 1:
        worker_result = evaluate_target_chunk(
            {
                "chunk_index": 0,
                "targets": targets,
                "coverage_rows": coverage_rows,
            }
        )
        indexed_results = sorted(worker_result["results"], key=lambda item: item[0])
        return [result for _index, result in indexed_results], worker_result["cache_backend_summary"]

    chunks = [
        {
            "chunk_index": index,
            "targets": chunk,
            "coverage_rows": coverage_rows,
        }
        for index, chunk in enumerate(chunk_targets(targets, worker_count))
        if chunk
    ]
    indexed_results: list[tuple[int, dict[str, Any]]] = []
    cache_summaries: list[dict[str, Any]] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=worker_count) as pool:
        futures = [pool.submit(evaluate_target_chunk, chunk) for chunk in chunks]
        for future in concurrent.futures.as_completed(futures):
            payload = future.result()
            cache_summaries.append(payload["cache_backend_summary"])
            indexed_results.extend(payload["results"])
            print(
                f"[compiler-search] chunk {payload['chunk_index']} complete "
                f"({len(payload['results'])} targets)",
                flush=True,
            )
    indexed_results.sort(key=lambda item: item[0])
    return [result for _index, result in indexed_results], aggregate_cache_backend_summaries(cache_summaries)


def evaluate_target_chunk(payload: dict[str, Any]) -> dict[str, Any]:
    catalog = CatalogIndex()
    shared_node_cache = build_shared_node_cache()
    executor = TacticalQueryExecutor(shared_node_output_cache=shared_node_cache)
    coverage_rows = payload["coverage_rows"]
    results: list[tuple[int, dict[str, Any]]] = []
    for index, target in enumerate(payload["targets"]):
        absolute_index = int(target.get("_target_index", index))
        print(f"[compiler-search] {target['target_id']}", flush=True)
        row = coverage_row(coverage_rows, target["concept"])
        result = evaluate_target(target=target, row=row, catalog=catalog, executor=executor)
        results.append((absolute_index, result))
        print(
            f"[compiler-search] {target['target_id']} -> {result['result']} "
            f"({result['failure_taxonomy'] or 'ok'})",
            flush=True,
        )
    return {
        "chunk_index": payload["chunk_index"],
        "results": results,
        "cache_backend_summary": shared_cache_summary(shared_node_cache),
    }


def chunk_targets(targets: list[dict[str, Any]], worker_count: int) -> list[list[dict[str, Any]]]:
    indexed = [{**target, "_target_index": index} for index, target in enumerate(targets)]
    chunks: list[list[dict[str, Any]]] = [[] for _ in range(worker_count)]
    for index, target in enumerate(indexed):
        chunks[index % worker_count].append(target)
    return chunks


class SynthesisError(Exception):
    def __init__(self, taxonomy: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.taxonomy = taxonomy
        self.message = message
        self.details = details or {}


class CatalogIndex:
    def __init__(self, *, excluded_refs: set[str] | None = None) -> None:
        catalog = default_catalog()
        excluded = EXCLUDED_CATALOG_REFS if excluded_refs is None else excluded_refs
        self.entries: dict[str, CatalogEntry] = {
            entry.name: entry
            for entry in [*catalog.primitives, *catalog.relations]
            if entry.name not in excluded
        }
        self.outputs: dict[tuple[str, str], CatalogOutput] = {
            (entry.name, output.name): output
            for entry in self.entries.values()
            for output in entry.outputs
        }

    def field_set(self, entry: CatalogEntry) -> set[str]:
        fields = set(entry.evidence_fields)
        for output in entry.outputs:
            fields.add(output.name)
            fields.update(output.evidence_fields)
        return fields

    def output_field_set(self, entry: CatalogEntry, output_name: str) -> set[str]:
        for output in entry.outputs:
            if output.name == output_name:
                return {output.name, *output.evidence_fields}
        return set()

    def anchor_output(self, entry: CatalogEntry) -> CatalogOutput:
        for preferred in ("anchor_evaluations", "anchors", "episodes"):
            for output in entry.outputs:
                if output.name == preferred:
                    return output
        return entry.outputs[0]

    def providers_for_fields(self, fields: set[str]) -> list[CatalogEntry]:
        providers = [
            entry
            for entry in self.entries.values()
            if fields and fields.issubset(self.field_set(entry))
        ]
        return sorted(providers, key=lambda entry: (len(entry.inputs), len(self.field_set(entry)), entry.name))

    def providers_covering_any(self, fields: set[str]) -> list[CatalogEntry]:
        providers = [
            entry
            for entry in self.entries.values()
            if fields & self.field_set(entry)
        ]
        return sorted(
            providers,
            key=lambda entry: (-(len(fields & self.field_set(entry))), len(entry.inputs), len(self.field_set(entry)), entry.name),
        )

    def compatible_outputs(self, input_def: CatalogInput) -> list[tuple[CatalogEntry, CatalogOutput]]:
        candidates: list[tuple[CatalogEntry, CatalogOutput]] = []
        for entry in self.entries.values():
            for output in entry.outputs:
                if output_matches_input(output, input_def):
                    candidates.append((entry, output))
        return candidates

    def output_for_field(self, entry: CatalogEntry, field_name: str) -> CatalogOutput | None:
        for output in entry.outputs:
            if output.name == field_name:
                return output
        for output in entry.outputs:
            if field_name in output.evidence_fields and output.name not in {"anchor_evaluations", "anchors", "episodes"}:
                return output
        for output in entry.outputs:
            if field_name in output.evidence_fields:
                return output
        return None


class PersistentNodeOutputCache(collections.abc.MutableMapping):
    """Small disk-backed mapping for deterministic compiler-search node outputs."""

    def __init__(self, root: Path, *, namespace: str) -> None:
        self.root = root / namespace
        self.root.mkdir(parents=True, exist_ok=True)
        self.memory: dict[str, dict[str, Any]] = {}
        self.counters: collections.Counter[str] = collections.Counter()
        self.namespace = namespace

    def __getitem__(self, key: str) -> dict[str, Any]:
        if key in self.memory:
            self.counters["memory_loads"] += 1
            return self.memory[key]
        path = self.path_for(key)
        if not path.exists():
            raise KeyError(key)
        with gzip.open(path, "rb") as handle:
            value = pickle.load(handle)
        self.memory[key] = value
        self.counters["disk_loads"] += 1
        return value

    def __setitem__(self, key: str, value: dict[str, Any]) -> None:
        self.memory[key] = value
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        with gzip.open(tmp_path, "wb") as handle:
            pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)
        tmp_path.replace(path)
        self.counters["stores"] += 1

    def __delitem__(self, key: str) -> None:
        self.memory.pop(key, None)
        path = self.path_for(key)
        if not path.exists():
            raise KeyError(key)
        path.unlink()

    def __iter__(self):
        yielded: set[str] = set()
        for key in self.memory:
            yielded.add(key)
            yield key
        for path in self.root.glob("*/*.pkl.gz"):
            key = path.name.removesuffix(".pkl.gz")
            if key not in yielded:
                yield key

    def __len__(self) -> int:
        return len(set(iter(self)))

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return key in self.memory or self.path_for(key).exists()

    def path_for(self, key: str) -> Path:
        safe = "".join(char for char in key if char.isalnum()) or stable_hash(key)
        return self.root / safe[:2] / f"{safe}.pkl.gz"

    def summary(self) -> dict[str, Any]:
        return {
            "backend": "persistent_pickle_gzip",
            "enabled": True,
            "root": relative_path(self.root),
            "namespace": self.namespace,
            "entry_count": len(self),
            "memory_entries": len(self.memory),
            "disk_loads": int(self.counters.get("disk_loads", 0)),
            "memory_loads": int(self.counters.get("memory_loads", 0)),
            "stores": int(self.counters.get("stores", 0)),
        }


def build_shared_node_cache() -> collections.abc.MutableMapping[str, dict[str, Any]] | None:
    if not SHARED_NODE_CACHE_ENABLED:
        return None
    if PERSISTENT_NODE_CACHE_ENABLED:
        return PersistentNodeOutputCache(NODE_CACHE_ROOT, namespace=persistent_cache_namespace())
    return {}


def shared_cache_summary(cache: Any) -> dict[str, Any]:
    if cache is None:
        return {"enabled": False, "backend": "disabled"}
    if isinstance(cache, PersistentNodeOutputCache):
        return cache.summary()
    return {"enabled": True, "backend": "memory", "entry_count": len(cache)}


def aggregate_cache_backend_summaries(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    if not summaries:
        return {"enabled": False, "backend": "none", "worker_count": 0}
    backends = sorted({str(summary.get("backend")) for summary in summaries})
    totals: collections.Counter[str] = collections.Counter()
    for summary in summaries:
        for key in ("memory_entries", "disk_loads", "memory_loads", "stores"):
            totals[key] += int(summary.get(key) or 0)
    first = summaries[0]
    persistent_root = first.get("root")
    persistent_namespace = first.get("namespace")
    persistent_shared_root = (
        first.get("backend") == "persistent_pickle_gzip"
        and persistent_root
        and all(summary.get("root") == persistent_root for summary in summaries)
        and all(summary.get("namespace") == persistent_namespace for summary in summaries)
    )
    if persistent_shared_root:
        entry_count = len(list(repo_path(str(persistent_root)).glob("*/*.pkl.gz")))
    else:
        entry_count = sum(int(summary.get("entry_count") or 0) for summary in summaries)
    payload: dict[str, Any] = {
        "enabled": any(bool(summary.get("enabled")) for summary in summaries),
        "backend": first.get("backend") if len(backends) == 1 else "mixed",
        "worker_count": len(summaries),
        "backends": backends,
        "entry_count": entry_count,
        "memory_entries": int(totals.get("memory_entries", 0)),
        "disk_loads": int(totals.get("disk_loads", 0)),
        "memory_loads": int(totals.get("memory_loads", 0)),
        "stores": int(totals.get("stores", 0)),
    }
    if first.get("namespace") is not None:
        payload["namespace"] = first["namespace"]
    if first.get("root") is not None:
        payload["root"] = first["root"]
    return payload


def persistent_cache_namespace() -> str:
    override = os.environ.get("TQE_SEARCH_NODE_CACHE_NAMESPACE")
    if override:
        return sanitize_namespace(override)
    commit = git_output(["rev-parse", "HEAD"]) or "unknown"
    dirty = git_output(["diff", "--binary", "--", "src/tqe/runtime", "scripts/coverage_map"]) or ""
    namespace_payload = {
        "commit": commit,
        "dirty_diff_hash": stable_hash(dirty) if dirty else None,
        "synthesizer_version": SYNTHESIZER_VERSION,
        "search_budget_label": SEARCH_BUDGET_LABEL,
    }
    suffix = stable_hash(namespace_payload)[:12]
    return sanitize_namespace(f"{commit[:12]}-{suffix}")


def git_output(args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip()


def sanitize_namespace(value: str) -> str:
    sanitized = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value).strip("._-")
    return sanitized or stable_hash(value)[:16]


VALUE_FAMILY_FIELDS = {
    "pressure_distance": ["nearest_defender_distance_m"],
    "team_shape_width_or_depth": ["team_width_m", "team_depth_m", "team_area_m2"],
}
def declared_operator_fields(signature: Any) -> set[str]:
    fields: set[str] = set()
    for output in signature.outputs:
        fields.add(output.name)
        fields.update(output.evidence_fields)
    return fields


PROJECT_ONTO_AXIS_FIELDS = declared_operator_fields(PROJECT_ONTO_AXIS_SIGNATURE)
DELTA_ACROSS_ANCHOR_FIELDS = declared_operator_fields(DELTA_ACROSS_ANCHOR_SIGNATURE)
EXTREMUM_OVER_SET_FIELDS = declared_operator_fields(EXTREMUM_OVER_SET_SIGNATURE)
WINDOW_FIELDS = declared_operator_fields(WINDOW_SIGNATURE)
TYPED_JOIN_FIELDS = declared_operator_fields(TYPED_JOIN_SIGNATURE)
TYPED_JOIN_CORE_FIELDS = {
    "typed_join_records",
    "typed_join_status",
    "typed_join_reason",
    "join_key",
    "no_match_policy",
    "unconstrained",
    "unconstrained_rationale",
    "same_team_perspective_required",
    "entity_identity_preserved_required",
    "frame_alignment_required",
    "left_anchor_id_field",
    "right_anchor_id_field",
    "left_frame_field",
    "right_frame_field",
    "left_entity_id_field",
    "right_entity_id_field",
    "left_start_frame_field",
    "left_end_frame_field",
    "right_start_frame_field",
    "right_end_frame_field",
    "left_team_role_field",
    "right_team_role_field",
    "left_status_field",
    "right_status_field",
    "required_status_value",
    "left_required_status_value",
    "right_required_status_value",
    "maximum_frame_delta",
    "left_anchor_id",
    "right_anchor_id",
    "left_frame_id",
    "right_frame_id",
    "left_entity_id",
    "right_entity_id",
    "left_start_frame_id",
    "left_end_frame_id",
    "right_start_frame_id",
    "right_end_frame_id",
    "left_team_role",
    "right_team_role",
    "left_status",
    "right_status",
    "typed_join_match_count",
    "typed_join_dropped_no_match_count",
    "typed_join_constraint_failures",
    "left_record_hash",
    "right_record_hash",
    "left_record_index",
    "right_record_index",
    "witness_left_node_id",
    "witness_left_output_name",
    "witness_right_node_id",
    "witness_right_output_name",
}
OPERATOR_SIGNATURES_BY_CONSTRAINT_KIND = {
    "delta_across_anchor": DELTA_ACROSS_ANCHOR_SIGNATURE,
    "extremum_over_set": EXTREMUM_OVER_SET_SIGNATURE,
    "typed_join": TYPED_JOIN_SIGNATURE,
    "window": WINDOW_SIGNATURE,
    "vector_projection": PROJECT_ONTO_AXIS_SIGNATURE,
}
OPERATOR_FIELDS_BY_CONSTRAINT_KIND = {
    kind: declared_operator_fields(signature)
    for kind, signature in OPERATOR_SIGNATURES_BY_CONSTRAINT_KIND.items()
}


@dataclass
class BuildResult:
    nodes: list[dict[str, Any]]
    terminal_node_id: str
    terminal_entry: str
    terminal_output: str
    field_sources: dict[str, tuple[str, str]]
    rules_used: list[str] = field(default_factory=list)
    providers_used: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchContext:
    catalog: CatalogIndex
    target_contract: dict[str, Any]
    counter: collections.Counter[str] = field(default_factory=collections.Counter)
    max_depth: int = MAX_DEPTH
    max_branching: int = MAX_BRANCHING

    def node_id(self, base: str) -> str:
        sanitized = "".join(char if char.isalnum() else "_" for char in base.lower()).strip("_")
        if not sanitized or not sanitized[0].isalpha():
            sanitized = f"node_{sanitized}"
        self.counter[sanitized] += 1
        suffix = self.counter[sanitized]
        return sanitized if suffix == 1 else f"{sanitized}_{suffix}"


def evaluate_target(
    *,
    target: dict[str, Any],
    row: dict[str, Any],
    catalog: CatalogIndex,
    executor: TacticalQueryExecutor,
) -> dict[str, Any]:
    contract = target["target_contract"]
    target_hash = stable_hash(contract)
    if concept_name_used_as_hint(target):
        return row_result(
            target=target,
            row=row,
            result="not_compiler_reachable",
            failure_taxonomy="answer_key_error",
            message="Target contract contains the reporting concept name; refusing hinted target.",
            target_contract_hash=target_hash,
        )
    unsupported_modalities = [
        modality for modality in contract.get("required_modalities", []) if modality not in SUPPORTED_MODALITIES
    ]
    if unsupported_modalities:
        return row_result(
            target=target,
            row=row,
            result="not_compiler_reachable",
            failure_taxonomy="unsupported_modality",
            message="Target requires unavailable data/model modalities.",
            target_contract_hash=target_hash,
            failure_details={"unsupported_modalities": unsupported_modalities},
        )
    unsupported_constraints = unsupported_composition_constraints(contract)
    if unsupported_constraints:
        return row_result(
            target=target,
            row=row,
            result="not_compiler_reachable",
            failure_taxonomy="missing_constraint",
            message="Target requires composition constraints the search cannot yet enforce.",
            target_contract_hash=target_hash,
            failure_details={"unsupported_composition_constraints": unsupported_constraints},
        )

    context = SearchContext(catalog=catalog, target_contract=contract)
    try:
        build = synthesize_by_search(target=target, row=row, context=context)
    except SynthesisError as error:
        return row_result(
            target=target,
            row=row,
            result="not_compiler_reachable",
            failure_taxonomy=classify_failure(error.taxonomy, row),
            message=error.message,
            target_contract_hash=target_hash,
            failure_details=error.details,
        )

    try:
        execution, rows, document_payload = execute_build_for_perspectives(
            build=build,
            executor=executor,
            target_id=target["target_id"],
        )
    except (BindError, ValueError) as error:
        return row_result(
            target=target,
            row=row,
            result="not_compiler_reachable",
            failure_taxonomy="runtime_gap",
            message=f"{type(error).__name__}: {error}",
            target_contract_hash=target_hash,
            document_payload=build["document"],
            build=build,
        )
    except Exception as error:  # pragma: no cover - exact failure is serialized.
        return row_result(
            target=target,
            row=row,
            result="not_compiler_reachable",
            failure_taxonomy="runtime_gap",
            message=f"{type(error).__name__}: {error}",
            target_contract_hash=target_hash,
            document_payload=build["document"],
            build=build,
        )

    evidence_failures = int(execution.provenance.get("requested_evidence_failure_count") or 0)
    if execution.status != ExecutionStatus.PASS or evidence_failures != 0:
        return row_result(
            target=target,
            row=row,
            result="not_compiler_reachable",
            failure_taxonomy="runtime_gap",
            message="Discovered plan did not execute with complete requested evidence.",
            target_contract_hash=target_hash,
            document_payload=document_payload,
            build=build,
            execution=execution,
            rows=rows,
        )

    return row_result(
        target=target,
        row=row,
        result="compiler_reachable",
        failure_taxonomy=None,
        message="Bounded backward search discovered a reusable executable plan from the typed target contract.",
        target_contract_hash=target_hash,
        document_payload=document_payload,
        build=build,
        execution=execution,
        rows=rows,
    )


@dataclass
class CombinedExecution:
    status: ExecutionStatus
    provenance: dict[str, Any]


def execute_build_for_perspectives(
    *,
    build: dict[str, Any],
    executor: TacticalQueryExecutor,
    target_id: str,
) -> tuple[CombinedExecution, list[dict[str, Any]], dict[str, Any]]:
    role_documents: dict[str, dict[str, Any]] = {}
    role_traces: dict[str, str | None] = {}
    role_statuses: dict[str, str] = {}
    role_counts: dict[str, int] = {}
    node_cache: collections.Counter[str] = collections.Counter()
    rows: list[dict[str, Any]] = []
    evidence_failures = 0
    runtime_value_count = 0
    for role in PERSPECTIVE_TEAM_ROLES:
        document_payload = copy.deepcopy(build["document"])
        document_payload["default_invocation"]["perspective_team_role"] = role
        if len(PERSPECTIVE_TEAM_ROLES) > 1:
            document_payload["default_invocation"]["invocation_id"] = f"{target_id}_{role}_probe"
        role_documents[role] = document_payload
        document = TacticalQueryDocument.model_validate(document_payload)
        bound = bind_document(document)
        execution = executor.execute(bound)
        role_rows = execution_result_rows(execution)
        for item in role_rows:
            row = dict(item)
            requested = dict(row.get("requested_evidence") or {})
            requested["execution_perspective_team_role"] = role
            row["requested_evidence"] = requested
            row["execution_perspective_team_role"] = role
            rows.append(row)
        evidence_failures += int(execution.provenance.get("requested_evidence_failure_count") or 0)
        runtime_value_count += int(execution.provenance.get("runtime_value_count") or 0)
        role_traces[role] = execution.provenance.get("runtime_trace_hash")
        role_statuses[role] = execution.status.value
        role_counts[role] = len(role_rows)
        cache = execution.provenance.get("node_cache")
        if isinstance(cache, dict):
            for key in ("hits", "local_hits", "shared_hits", "misses", "disabled", "bypassed"):
                node_cache[key] += int(cache.get(key) or 0)
    combined_status = (
        ExecutionStatus.PASS
        if all(status == ExecutionStatus.PASS.value for status in role_statuses.values())
        else ExecutionStatus.FAIL
    )
    document_payload: dict[str, Any]
    if len(role_documents) == 1:
        document_payload = next(iter(role_documents.values()))
    else:
        document_payload = {
            "schema_version": "compiler_search_perspective_bundle.v1",
            "target_id": target_id,
            "perspective_team_roles": PERSPECTIVE_TEAM_ROLES,
            "documents": role_documents,
        }
    (PLAN_DIR / f"{target_id}.json").write_text(
        json.dumps(document_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rows.sort(
        key=lambda item: (
            str(item.get("execution_perspective_team_role") or ""),
            str(item.get("result_id") or ""),
        )
    )
    return (
        CombinedExecution(
            status=combined_status,
            provenance={
                "requested_evidence_failure_count": evidence_failures,
                "runtime_trace_hash": stable_hash(
                    {
                        "perspective_team_roles": PERSPECTIVE_TEAM_ROLES,
                        "role_traces": role_traces,
                    }
                ),
                "runtime_value_count": runtime_value_count,
                "node_cache": dict(sorted(node_cache.items())),
                "perspective_team_roles": PERSPECTIVE_TEAM_ROLES,
                "perspective_statuses": role_statuses,
                "perspective_result_counts": role_counts,
            },
        ),
        rows,
        document_payload,
    )


def synthesize_by_search(*, target: dict[str, Any], row: dict[str, Any], context: SearchContext) -> dict[str, Any]:
    contract = target["target_contract"]
    required_fields = required_target_fields(contract)
    operator_fields = operator_composition_fields(contract, required_fields)
    uncovered_fields = sorted(
        field
        for field in required_fields - operator_fields
        if not context.catalog.providers_covering_any({field})
    )
    if uncovered_fields:
        raise SynthesisError(
            "missing_primitive",
            "No catalog provider exposes one or more required target fields.",
            {"fields": uncovered_fields},
        )
    if operator_composition_constraints(context):
        build = build_operator_composition(context, required_fields, depth=0)
        document_payload = assemble_document(target=target, build=build)
        missing_fields = sorted(field for field in required_fields if field not in build.field_sources)
        if missing_fields:
            raise SynthesisError(
                "missing_constraint",
                "Operator composition did not cover every required evidence/predicate field.",
                {
                    "missing_fields": missing_fields,
                    "providers_used": build.providers_used,
                },
            )
        return {
            "document": document_payload,
            "providers_used": build.providers_used,
            "rules_used": sorted(set(build.rules_used)),
            "terminal_provider": build.terminal_entry,
            "build_metadata": build.metadata,
            "field_sources": {
                field: {"source_node_id": source[0], "output_name": source[1]}
                for field, source in sorted(build.field_sources.items())
            },
        }
    providers = context.catalog.providers_covering_any(required_fields)
    if target_constraints(context, "same_player_return"):
        providers = [entry for entry in providers if entry.name == "join_episode_sets"]
    elif target_constraints(context, "same_anchor_identity") or {"join_status", "join_reason"} & required_fields:
        providers = sorted(providers, key=lambda entry: (entry.name != "join_episode_sets", entry.name))
    if not providers:
        raise SynthesisError(
            "missing_primitive",
            "No allowed catalog provider exposes any required target field.",
            {"required_fields": sorted(required_fields)},
        )

    errors: list[dict[str, Any]] = []
    for terminal in providers[: context.max_branching]:
        try:
            build = build_entry(context, terminal, required_fields, depth=0, input_context={})
            document_payload = assemble_document(target=target, build=build)
            missing_fields = sorted(field for field in required_fields if field not in build.field_sources)
            if missing_fields:
                raise SynthesisError(
                    "missing_constraint",
                    "Search produced a provider chain but did not cover every required evidence/predicate field.",
                    {
                        "terminal_provider": terminal.name,
                        "missing_fields": missing_fields,
                        "providers_used": build.providers_used,
                    },
                )
            return {
                "document": document_payload,
                "providers_used": build.providers_used,
                "rules_used": sorted(set(build.rules_used)),
                "terminal_provider": terminal.name,
                "field_sources": {
                    field: {"source_node_id": source[0], "output_name": source[1]}
                    for field, source in sorted(build.field_sources.items())
                },
            }
        except SynthesisError as error:
            errors.append({"provider": terminal.name, "taxonomy": error.taxonomy, "message": error.message, **error.details})
            continue
    if any(error["taxonomy"] == "search_budget_exceeded" for error in errors):
        raise SynthesisError(
            "search_budget_exceeded",
            "At least one provider path reached the bounded-search limit before proving reachability.",
            {"attempted": errors[: context.max_branching]},
        )
    if any(error["taxonomy"] == "missing_constraint" for error in errors):
        raise SynthesisError(
            "missing_constraint",
            "Providers exist, but bounded search could not satisfy the required reusable composition.",
            {"attempted": errors[: context.max_branching]},
        )
    raise SynthesisError(
        "missing_primitive",
        "No bounded provider chain could cover the typed target.",
        {"attempted": errors[: context.max_branching], "required_fields": sorted(required_fields)},
    )


def operator_composition_fields(contract: dict[str, Any], required_fields: set[str]) -> set[str]:
    fields: set[str] = set()
    for constraint in contract.get("composition_constraints", []):
        if not isinstance(constraint, dict):
            continue
        fields.update(operator_constraint_fields(constraint, required_fields))
    return fields


def operator_constraint_fields(constraint: dict[str, Any], required_fields: set[str]) -> set[str]:
    kind = str(constraint.get("kind", ""))
    fields = set(required_fields & OPERATOR_FIELDS_BY_CONSTRAINT_KIND.get(kind, set()))
    if kind == "typed_join":
        for side in ("left", "right"):
            fields.update(required_fields & {str(item) for item in constraint.get(f"{side}_required_fields", [])})
            for nested in constraint.get(f"{side}_composition_constraints", []):
                if isinstance(nested, dict):
                    fields.update(operator_constraint_fields(nested, required_fields))
    return fields


def operator_composition_constraints(context: SearchContext) -> list[dict[str, Any]]:
    return [
        constraint
        for constraint in target_constraints(context)
        if str(constraint.get("kind", "")) in OPERATOR_COMPOSITION_BUILDERS
    ]


def build_operator_composition(
    context: SearchContext,
    required_fields: set[str],
    *,
    depth: int,
) -> BuildResult:
    attempts: list[dict[str, Any]] = []
    for constraint in operator_composition_constraints(context):
        kind = str(constraint.get("kind"))
        builder = OPERATOR_COMPOSITION_BUILDERS[kind]
        try:
            return builder(context, required_fields, depth=depth)
        except SynthesisError as error:
            attempts.append(
                {
                    "constraint_kind": kind,
                    "taxonomy": error.taxonomy,
                    "message": error.message,
                    **error.details,
                }
            )
    raise SynthesisError(
        "missing_constraint",
        "No registered operator composition satisfied the target contract.",
        {"attempted_operator_compositions": attempts[: context.max_branching]},
    )


def build_project_onto_axis(
    context: SearchContext,
    required_fields: set[str],
    *,
    depth: int,
) -> BuildResult:
    constraint = first_target_constraint(context, "vector_projection")
    axis = str(constraint.get("axis", "goalward"))
    start_point_field = required_vector_projection_constraint(constraint, "start_point_field")
    end_point_field = required_vector_projection_constraint(constraint, "end_point_field")
    reference_point_field = str(constraint.get("reference_point_field", "none"))
    lane_start_point_field = str(constraint.get("lane_start_point_field", "none"))
    lane_end_point_field = str(constraint.get("lane_end_point_field", "none"))
    acting_team_field = (
        required_vector_projection_constraint(constraint, "acting_team_field")
        if axis == "goalward"
        else str(constraint.get("acting_team_field", "none"))
    )
    orientation_basis = str(constraint.get("orientation_basis", "acting_team"))
    required_source_status_field = str(constraint.get("required_source_status_field", "none"))
    required_source_status_value = str(constraint.get("required_source_status_value", "PASS"))
    zero_length_policy = str(constraint.get("zero_length_policy", "unknown"))
    source_required_fields = {
        start_point_field,
        end_point_field,
    }
    source_required_fields.update(
        field
        for field in (reference_point_field, lane_start_point_field, lane_end_point_field, acting_team_field)
        if field != "none"
    )
    if required_source_status_field != "none":
        source_required_fields.add(required_source_status_field)
    source_required_fields.discard("none")
    attempts: list[dict[str, Any]] = []
    candidates = vector_projection_candidates(context, source_required_fields)
    candidate_summaries = [
        {
            "provider": candidate["entry"].name,
            "output": candidate["output"].name,
            "fields": sorted({candidate["output"].name, *candidate["output"].evidence_fields} & source_required_fields),
        }
        for candidate in candidates
    ]
    for candidate in candidates[: context.max_branching]:
        entry = candidate["entry"]
        output = candidate["output"]
        try:
            source = build_entry(
                context,
                entry,
                source_required_fields,
                depth=depth + 1,
                input_context={},
            )
            missing_source_fields = sorted(
                field for field in source_required_fields if field not in source.field_sources
            )
            if missing_source_fields:
                raise SynthesisError(
                    "missing_constraint",
                    "Candidate vector source did not expose all declared point/status fields.",
                    {
                        "source_provider": entry.name,
                        "source_output": output.name,
                        "missing_source_fields": missing_source_fields,
                    },
                )
            node_id = context.node_id("project_onto_axis")
            nodes = [*source.nodes]
            nodes.append(
                operator_node(
                    node_id=node_id,
                    operator_name="project_onto_axis",
                    version="0.1.0",
                    inputs={"source": ref(source.terminal_node_id, output.name)},
                    parameters={
                        "axis": enum(axis),
                        "start_point_field": enum(start_point_field),
                        "end_point_field": enum(end_point_field),
                        "reference_point_field": enum(reference_point_field),
                        "lane_start_point_field": enum(lane_start_point_field),
                        "lane_end_point_field": enum(lane_end_point_field),
                        "acting_team_field": enum(acting_team_field),
                        "orientation_basis": enum(orientation_basis),
                        "required_source_status_field": enum(required_source_status_field),
                        "required_source_status_value": enum(required_source_status_value),
                        "zero_length_policy": enum(zero_length_policy),
                    },
                )
            )
            field_sources = {**source.field_sources}
            for field in PROJECT_ONTO_AXIS_FIELDS:
                field_sources.setdefault(field, (node_id, project_onto_axis_output_for_field(field)))
            return BuildResult(
                nodes=dedupe_nodes(nodes),
                terminal_node_id=node_id,
                terminal_entry="operator:project_onto_axis",
                terminal_output="axis_projection_records",
                field_sources=field_sources,
                rules_used=[*source.rules_used, "generic_vector_projection_operator"],
                providers_used=[*source.providers_used, "operator:project_onto_axis"],
                metadata={
                    "vector_projection_discovery_space_count": len(candidates),
                    "vector_projection_candidate_outputs": candidate_summaries,
                    "vector_projection_selected_output": {
                        "provider": entry.name,
                        "output": output.name,
                    },
                    "vector_projection_constraint": {
                        "axis": axis,
                        "start_point_field": start_point_field,
                        "end_point_field": end_point_field,
                        "reference_point_field": reference_point_field,
                        "lane_start_point_field": lane_start_point_field,
                        "lane_end_point_field": lane_end_point_field,
                        "acting_team_field": acting_team_field,
                        "orientation_basis": orientation_basis,
                        "required_source_status_field": required_source_status_field,
                        "required_source_status_value": required_source_status_value,
                        "zero_length_policy": zero_length_policy,
                    },
                    "source_build_metadata": source.metadata,
                },
            )
        except SynthesisError as error:
            attempts.append(
                {
                    "source_provider": entry.name,
                    "source_output": output.name,
                    "taxonomy": error.taxonomy,
                    "message": error.message,
                    **error.details,
                }
            )
    raise SynthesisError(
        "missing_constraint",
        "No typed point-pair source satisfied vector_projection.",
        {"attempted": attempts[: context.max_branching], "required_fields": sorted(required_fields)},
    )


def required_vector_projection_constraint(constraint: dict[str, Any], key: str) -> str:
    value = constraint.get(key)
    if value is None or str(value) == "" or str(value) == "none":
        raise SynthesisError(
            "missing_constraint",
            f"vector_projection requires declared {key}; no provider-field default is allowed.",
            {"missing_vector_projection_constraint_key": key},
        )
    return str(value)


def vector_projection_candidates(
    context: SearchContext,
    source_required_fields: set[str],
) -> list[dict[str, Any]]:
    candidates: list[tuple[int, str, str, CatalogEntry, CatalogOutput]] = []
    operator_input = PROJECT_ONTO_AXIS_SIGNATURE.inputs[0]
    for entry in context.catalog.entries.values():
        fields = context.catalog.field_set(entry)
        if not source_required_fields.issubset(fields):
            continue
        for output in entry.outputs:
            if not composition_output_matches_operator_input(output, operator_input):
                continue
            output_fields = {output.name, *output.evidence_fields}
            if not source_required_fields.issubset(output_fields):
                continue
            score = 0
            score += 25 * len(source_required_fields & output_fields)
            score += 8 if output.name in {"episodes", "anchor_evaluations"} else 0
            candidates.append((-score, entry.name, output.name, entry, output))
    return [
        {"entry": entry, "output": output}
        for _score, _entry_name, _output_name, entry, output in sorted(candidates)
    ]


def composition_output_matches_operator_input(output: CatalogOutput, input_def: Any) -> bool:
    return (
        output.temporal_type == input_def.temporal_type
        and output.payload_type == input_def.payload_type
        and output.cardinality == input_def.cardinality
        and output.unit == input_def.unit
        and output.entity_scope == input_def.entity_scope
    )


def project_onto_axis_output_for_field(field: str) -> str:
    return operator_output_for_field(PROJECT_ONTO_AXIS_SIGNATURE, field)


def delta_across_anchor_output_for_field(field: str) -> str:
    return operator_output_for_field(DELTA_ACROSS_ANCHOR_SIGNATURE, field)


def extremum_over_set_output_for_field(field: str) -> str:
    return operator_output_for_field(EXTREMUM_OVER_SET_SIGNATURE, field)


def window_output_for_field(field: str) -> str:
    return operator_output_for_field(WINDOW_SIGNATURE, field)


def operator_output_for_field(signature: Any, field: str) -> str:
    for output in signature.outputs:
        if output.name == field:
            return output.name
    for output in signature.outputs:
        if field in output.evidence_fields:
            return output.name
    return signature.outputs[0].name


def build_delta_across_anchor_operator(
    context: SearchContext,
    required_fields: set[str],
    *,
    depth: int,
) -> BuildResult:
    constraint = first_target_constraint(context, "delta_across_anchor")
    delta_constraint = delta_across_anchor_constraint(constraint)
    attempts: list[dict[str, Any]] = []
    candidates = delta_across_anchor_candidates(context, delta_constraint)
    candidate_summaries = [
        {
            "anchor_provider": candidate["anchor_entry"].name,
            "evaluator_provider": candidate["evaluator_entry"].name,
            "before_frame_field": candidate["before_frame_field"],
            "after_frame_field": candidate["after_frame_field"],
            "before_value_field": candidate["before_value_field"],
            "after_value_field": candidate["after_value_field"],
        }
        for candidate in candidates
    ]
    for candidate in candidates[: context.max_branching]:
        try:
            anchor = build_entry(
                context,
                candidate["anchor_entry"],
                set(candidate["anchor_required_fields"]),
                depth=depth + 1,
                input_context={},
            )
            before = build_entry(
                context,
                candidate["evaluator_entry"],
                set(candidate["before_required_fields"]),
                depth=depth + 1,
                input_context=evaluator_input_context(anchor=anchor, context=candidate["before_input_context"]),
            )
            after = build_entry(
                context,
                candidate["evaluator_entry"],
                set(candidate["after_required_fields"]),
                depth=depth + 1,
                input_context=evaluator_input_context(anchor=anchor, context=candidate["after_input_context"]),
            )
            missing_anchor_fields = sorted(
                field for field in candidate["anchor_required_fields"] if field not in anchor.field_sources
            )
            missing_before_fields = sorted(
                field for field in candidate["before_required_fields"] if field not in before.field_sources
            )
            missing_after_fields = sorted(
                field for field in candidate["after_required_fields"] if field not in after.field_sources
            )
            if missing_anchor_fields or missing_before_fields or missing_after_fields:
                raise SynthesisError(
                    "missing_constraint",
                    "Delta source composition did not cover declared anchor/evaluator fields.",
                    {
                        "missing_anchor_fields": missing_anchor_fields,
                        "missing_before_fields": missing_before_fields,
                        "missing_after_fields": missing_after_fields,
                    },
                )
            node_id = context.node_id("delta_across_anchor")
            nodes = [*anchor.nodes, *before.nodes, *after.nodes]
            nodes.append(
                operator_node(
                    node_id=node_id,
                    operator_name="delta_across_anchor",
                    version="0.1.0",
                    inputs={
                        "anchors": ref(anchor.terminal_node_id, anchor.terminal_output),
                        "before_evaluations": ref(before.terminal_node_id, before.terminal_output),
                        "after_evaluations": ref(after.terminal_node_id, after.terminal_output),
                    },
                    parameters={
                        "before_value_field": enum(candidate["before_value_field"]),
                        "after_value_field": enum(candidate["after_value_field"]),
                        "anchor_status_field": enum(delta_constraint["anchor_status_field"]),
                        "anchor_status_value": enum(delta_constraint["anchor_status_value"]),
                        "before_subject_field": enum(candidate["before_input_context"].get("carrier_id_field", "none")),
                        "after_subject_field": enum(candidate["after_input_context"].get("carrier_id_field", "none")),
                        "before_frame_field": enum(delta_constraint["before_record_frame_field"]),
                        "after_frame_field": enum(delta_constraint["after_record_frame_field"]),
                        "before_status_field": enum(candidate["before_status_field"]),
                        "after_status_field": enum(candidate["after_status_field"]),
                        "required_status_value": enum(delta_constraint["required_status_value"]),
                        "edge_threshold": number(float(delta_constraint["edge_threshold"]), "none"),
                        "hysteresis_margin": number(float(delta_constraint["hysteresis_margin"]), "none"),
                        "value_unit": enum(delta_constraint["value_unit"]),
                        "missing_evidence_policy": enum(delta_constraint["missing_evidence_policy"]),
                    },
                )
            )
            field_sources = {**anchor.field_sources, **before.field_sources, **after.field_sources}
            for field in DELTA_ACROSS_ANCHOR_FIELDS:
                field_sources.setdefault(field, (node_id, delta_across_anchor_output_for_field(field)))
            return BuildResult(
                nodes=dedupe_nodes(nodes),
                terminal_node_id=node_id,
                terminal_entry="operator:delta_across_anchor",
                terminal_output="delta_records",
                field_sources=field_sources,
                rules_used=[
                    *anchor.rules_used,
                    *before.rules_used,
                    *after.rules_used,
                    "generic_delta_across_anchor_operator",
                ],
                providers_used=[
                    *anchor.providers_used,
                    *before.providers_used,
                    *after.providers_used,
                    "operator:delta_across_anchor",
                ],
                metadata={
                    "delta_across_anchor_discovery_space_count": len(candidates),
                    "delta_across_anchor_candidate_outputs": candidate_summaries,
                    "delta_across_anchor_selected_output": {
                        "anchor_provider": candidate["anchor_entry"].name,
                        "evaluator_provider": candidate["evaluator_entry"].name,
                    },
                    "delta_across_anchor_constraint": delta_constraint,
                    "anchor_build_metadata": anchor.metadata,
                    "before_build_metadata": before.metadata,
                    "after_build_metadata": after.metadata,
                },
            )
        except SynthesisError as error:
            attempts.append(
                {
                    "anchor_provider": candidate["anchor_entry"].name,
                    "evaluator_provider": candidate["evaluator_entry"].name,
                    "taxonomy": error.taxonomy,
                    "message": error.message,
                    **error.details,
                }
            )
    raise SynthesisError(
        "missing_constraint",
        "No typed before/after scalar source satisfied delta_across_anchor.",
        {"attempted": attempts[: context.max_branching], "candidate_count": len(candidates)},
    )


def delta_across_anchor_constraint(constraint: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "kind",
        "before_value_field",
        "after_value_field",
        "before_status_field",
        "after_status_field",
        "required_status_value",
        "edge_threshold",
        "hysteresis_margin",
        "value_unit",
        "missing_evidence_policy",
        "anchor_status_field",
        "anchor_status_value",
        "before_frame_field",
        "after_frame_field",
        "before_record_frame_field",
        "after_record_frame_field",
        "carrier_id_field",
        "before_input_context",
        "after_input_context",
    }
    unapplied = sorted(key for key in constraint if key not in allowed_keys)
    if unapplied:
        raise SynthesisError(
            "missing_constraint",
            "delta_across_anchor supplied unsupported keys that synthesis cannot apply.",
            {"unapplied_delta_constraint_keys": unapplied},
        )
    payload = {
        "before_value_field": required_delta_constraint(constraint, "before_value_field"),
        "after_value_field": required_delta_constraint(constraint, "after_value_field"),
        "before_status_field": str(constraint.get("before_status_field", "none")),
        "after_status_field": str(constraint.get("after_status_field", "none")),
        "required_status_value": str(constraint.get("required_status_value", "PASS")),
        "edge_threshold": float(constraint.get("edge_threshold", 0.0)),
        "hysteresis_margin": float(constraint.get("hysteresis_margin", 0.0)),
        "value_unit": str(constraint.get("value_unit", "none")),
        "missing_evidence_policy": str(constraint.get("missing_evidence_policy", "unknown")),
        "anchor_status_field": str(constraint.get("anchor_status_field", "none")),
        "anchor_status_value": str(constraint.get("anchor_status_value", "PASS")),
        "before_frame_field": required_delta_constraint(constraint, "before_frame_field"),
        "after_frame_field": required_delta_constraint(constraint, "after_frame_field"),
        "before_record_frame_field": required_delta_constraint(constraint, "before_record_frame_field"),
        "after_record_frame_field": required_delta_constraint(constraint, "after_record_frame_field"),
        "carrier_id_field": str(constraint.get("carrier_id_field", "none")),
    }
    for context_key in ("before_input_context", "after_input_context"):
        raw_context = constraint.get(context_key, {})
        if raw_context is None:
            raw_context = {}
        if not isinstance(raw_context, dict):
            raise SynthesisError(
                "missing_constraint",
                f"delta_across_anchor {context_key} must be an object.",
                {f"invalid_{context_key}": raw_context},
            )
        payload[context_key] = dict(raw_context)
    for context_key, frame_key in (
        ("before_input_context", "before_frame_field"),
        ("after_input_context", "after_frame_field"),
    ):
        context_payload = payload[context_key]
        declared_frame = payload[frame_key]
        if "frame_field" in context_payload and str(context_payload["frame_field"]) != declared_frame:
            raise SynthesisError(
                "missing_constraint",
                f"delta_across_anchor {context_key}.frame_field conflicts with declared {frame_key}.",
                {
                    "context_key": context_key,
                    "declared_frame_field": declared_frame,
                    "context_frame_field": context_payload["frame_field"],
                },
            )
        context_payload.setdefault("frame_field", declared_frame)
        legacy_carrier = str(payload.get("carrier_id_field", "none"))
        if legacy_carrier != "none":
            context_payload.setdefault("carrier_id_field", legacy_carrier)
    return payload


def required_delta_constraint(constraint: dict[str, Any], key: str) -> str:
    value = constraint.get(key)
    if value is None or str(value) == "" or str(value) == "none":
        raise SynthesisError(
            "missing_constraint",
            f"delta_across_anchor requires declared {key}; no provider-field default is allowed.",
            {"missing_delta_constraint_key": key},
        )
    return str(value)


def build_extremum_over_set_operator(
    context: SearchContext,
    required_fields: set[str],
    *,
    depth: int,
) -> BuildResult:
    constraint = first_target_constraint(context, "extremum_over_set")
    extremum_constraint = extremum_over_set_constraint(constraint)
    attempts: list[dict[str, Any]] = []
    candidates = extremum_over_set_candidates(context, extremum_constraint)
    candidate_summaries = [
        {
            "source_provider": candidate["entry"].name,
            "source_output": candidate["output"].name,
            "source_required_fields": candidate["source_required_fields"],
        }
        for candidate in candidates
    ]
    for candidate in candidates[: context.max_branching]:
        try:
            source = build_entry(
                context,
                candidate["entry"],
                set(candidate["source_required_fields"]),
                depth=depth + 1,
                input_context={},
            )
            missing_source_fields = sorted(
                field for field in candidate["source_required_fields"] if field not in source.field_sources
            )
            if missing_source_fields:
                raise SynthesisError(
                    "missing_constraint",
                    "Candidate set source did not expose all declared extremum fields.",
                    {
                        "source_provider": candidate["entry"].name,
                        "source_output": candidate["output"].name,
                        "missing_source_fields": missing_source_fields,
                    },
                )
            node_id = context.node_id("extremum_over_set")
            nodes = [*source.nodes]
            nodes.append(
                operator_node(
                    node_id=node_id,
                    operator_name="extremum_over_set",
                    version="0.1.0",
                    inputs={"candidates": ref(source.terminal_node_id, candidate["output"].name)},
                    parameters={
                        "selection_mode": enum(extremum_constraint["selection_mode"]),
                        "top_k": number(float(extremum_constraint["top_k"]), "count"),
                        "value_field": enum(extremum_constraint["value_field"]),
                        "value_unit": enum(extremum_constraint["value_unit"]),
                        "record_id_field": enum(extremum_constraint["record_id_field"]),
                        "entity_id_field": enum(extremum_constraint["entity_id_field"]),
                        "frame_field": enum(extremum_constraint["frame_field"]),
                        "anchor_id_field": enum(extremum_constraint["anchor_id_field"]),
                        "subject_id_field": enum(extremum_constraint["subject_id_field"]),
                        "status_field": enum(extremum_constraint["status_field"]),
                        "required_status_value": enum(extremum_constraint["required_status_value"]),
                        "coverage_status_field": enum(extremum_constraint["coverage_status_field"]),
                        "coverage_policy": enum(extremum_constraint["coverage_policy"]),
                        "value_bound_kind": enum(extremum_constraint["value_bound_kind"]),
                        "value_bound": number(float(extremum_constraint["value_bound"]), "none"),
                        "tie_breaker_field": enum(extremum_constraint["tie_breaker_field"]),
                        "secondary_tie_breaker_field": enum(extremum_constraint["secondary_tie_breaker_field"]),
                        "missing_evidence_policy": enum(extremum_constraint["missing_evidence_policy"]),
                    },
                )
            )
            field_sources = {**source.field_sources}
            for field in EXTREMUM_OVER_SET_FIELDS:
                field_sources.setdefault(field, (node_id, extremum_over_set_output_for_field(field)))
            return BuildResult(
                nodes=dedupe_nodes(nodes),
                terminal_node_id=node_id,
                terminal_entry="operator:extremum_over_set",
                terminal_output="extremum_selection_records",
                field_sources=field_sources,
                rules_used=[*source.rules_used, "generic_extremum_over_set_operator"],
                providers_used=[*source.providers_used, "operator:extremum_over_set"],
                metadata={
                    "extremum_over_set_discovery_space_count": len(candidates),
                    "extremum_over_set_candidate_outputs": candidate_summaries,
                    "extremum_over_set_selected_output": {
                        "source_provider": candidate["entry"].name,
                        "source_output": candidate["output"].name,
                    },
                    "extremum_over_set_constraint": extremum_constraint,
                    "source_build_metadata": source.metadata,
                },
            )
        except SynthesisError as error:
            attempts.append(
                {
                    "source_provider": candidate["entry"].name,
                    "source_output": candidate["output"].name,
                    "taxonomy": error.taxonomy,
                    "message": error.message,
                    **error.details,
                }
            )
    raise SynthesisError(
        "missing_constraint",
        "No typed candidate-record source satisfied extremum_over_set.",
        {"attempted": attempts[: context.max_branching], "candidate_count": len(candidates)},
    )


def extremum_over_set_constraint(constraint: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "kind",
        "selection_mode",
        "top_k",
        "value_field",
        "value_unit",
        "record_id_field",
        "entity_id_field",
        "frame_field",
        "anchor_id_field",
        "subject_id_field",
        "status_field",
        "required_status_value",
        "coverage_status_field",
        "coverage_policy",
        "value_bound_kind",
        "value_bound",
        "tie_breaker_field",
        "secondary_tie_breaker_field",
        "missing_evidence_policy",
    }
    unapplied = sorted(key for key in constraint if key not in allowed_keys)
    if unapplied:
        raise SynthesisError(
            "missing_constraint",
            "extremum_over_set supplied unsupported keys that synthesis cannot apply.",
            {"unapplied_extremum_constraint_keys": unapplied},
        )
    return {
        "selection_mode": str(constraint.get("selection_mode", "argmin")),
        "top_k": int(constraint.get("top_k", 1)),
        "value_field": required_extremum_constraint(constraint, "value_field"),
        "value_unit": str(constraint.get("value_unit", "none")),
        "record_id_field": required_extremum_constraint(constraint, "record_id_field"),
        "entity_id_field": required_extremum_constraint(constraint, "entity_id_field"),
        "frame_field": required_extremum_constraint(constraint, "frame_field"),
        "anchor_id_field": str(constraint.get("anchor_id_field", "anchor_id")),
        "subject_id_field": str(constraint.get("subject_id_field", "none")),
        "status_field": str(constraint.get("status_field", "none")),
        "required_status_value": str(constraint.get("required_status_value", "PASS")),
        "coverage_status_field": str(constraint.get("coverage_status_field", "none")),
        "coverage_policy": str(constraint.get("coverage_policy", "unknown_if_incomplete_could_change_answer")),
        "value_bound_kind": str(constraint.get("value_bound_kind", "none")),
        "value_bound": float(constraint.get("value_bound", 0.0)),
        "tie_breaker_field": required_extremum_constraint(constraint, "tie_breaker_field"),
        "secondary_tie_breaker_field": str(constraint.get("secondary_tie_breaker_field", "none")),
        "missing_evidence_policy": str(constraint.get("missing_evidence_policy", "unknown")),
    }


def required_extremum_constraint(constraint: dict[str, Any], key: str) -> str:
    value = constraint.get(key)
    if value is None or str(value) == "" or str(value) == "none":
        raise SynthesisError(
            "missing_constraint",
            f"extremum_over_set requires declared {key}; no provider-field default is allowed.",
            {"missing_extremum_constraint_key": key},
        )
    return str(value)


def extremum_over_set_candidates(
    context: SearchContext,
    constraint: dict[str, Any],
) -> list[dict[str, Any]]:
    operator_input = EXTREMUM_OVER_SET_SIGNATURE.inputs[0]
    source_required_fields = {
        str(constraint["value_field"]),
        str(constraint["record_id_field"]),
        str(constraint["entity_id_field"]),
        str(constraint["frame_field"]),
        str(constraint["anchor_id_field"]),
        str(constraint["tie_breaker_field"]),
    }
    for optional_key in (
        "subject_id_field",
        "status_field",
        "coverage_status_field",
        "secondary_tie_breaker_field",
    ):
        field_name = str(constraint[optional_key])
        if field_name != "none":
            source_required_fields.add(field_name)
    scored: list[tuple[int, str, str, CatalogEntry, CatalogOutput]] = []
    for entry in context.catalog.entries.values():
        fields = context.catalog.field_set(entry)
        if not source_required_fields.issubset(fields):
            continue
        for output in entry.outputs:
            if not composition_output_matches_operator_input(output, operator_input):
                continue
            output_fields = {output.name, *output.evidence_fields}
            if not source_required_fields.issubset(output_fields):
                continue
            score = 0
            score += 25 * len(source_required_fields & output_fields)
            scored.append((-score, entry.name, output.name, entry, output))
    return [
        {
            "entry": entry,
            "output": output,
            "source_required_fields": sorted(source_required_fields),
        }
        for _score, _entry_name, _output_name, entry, output in sorted(scored)
    ]


def build_typed_join_operator(
    context: SearchContext,
    required_fields: set[str],
    *,
    depth: int,
) -> BuildResult:
    constraint = first_target_constraint(context, "typed_join")
    join_constraint = typed_join_constraint_payload(constraint)
    attempts: list[dict[str, Any]] = []
    left_required = typed_join_side_required_fields(join_constraint, "left")
    right_required = typed_join_side_required_fields(join_constraint, "right")
    left_candidates = typed_join_side_candidates(
        context,
        required_fields=left_required,
        input_name="left",
        input_context=join_constraint["left_input_context"],
        nested_constraints=join_constraint["left_composition_constraints"],
    )
    right_candidates = typed_join_side_candidates(
        context,
        required_fields=right_required,
        input_name="right",
        input_context=join_constraint["right_input_context"],
        nested_constraints=join_constraint["right_composition_constraints"],
    )
    candidate_summaries = {
        "left": [
            {
                "source": candidate["source_name"],
                "output": candidate["output_name"],
                "required_fields": sorted(left_required),
                "source_kind": candidate["source_kind"],
            }
            for candidate in left_candidates[: context.max_branching]
        ],
        "right": [
            {
                "source": candidate["source_name"],
                "output": candidate["output_name"],
                "required_fields": sorted(right_required),
                "source_kind": candidate["source_kind"],
            }
            for candidate in right_candidates[: context.max_branching]
        ],
    }
    for left_candidate in left_candidates[: context.max_branching]:
        for right_candidate in right_candidates[: context.max_branching]:
            try:
                left = build_typed_join_side(context, left_candidate, depth=depth + 1)
                right = build_typed_join_side(context, right_candidate, depth=depth + 1)
                missing_left = sorted(field for field in left_required if field not in left.field_sources)
                missing_right = sorted(field for field in right_required if field not in right.field_sources)
                if missing_left or missing_right:
                    raise SynthesisError(
                        "missing_constraint",
                        "typed_join side did not expose all declared fields.",
                        {"missing_left_fields": missing_left, "missing_right_fields": missing_right},
                    )
                node_id = context.node_id("typed_join")
                output_fields = set(TYPED_JOIN_CORE_FIELDS)
                output_fields.update(left.field_sources)
                output_fields.update(right.field_sources)
                output_fields.update(required_fields)
                output_fields.discard("none")
                nodes = [*left.nodes, *right.nodes]
                nodes.append(
                    operator_node(
                        node_id=node_id,
                        operator_name="typed_join",
                        version="0.1.0",
                        inputs={
                            "left": ref(left.terminal_node_id, left.terminal_output),
                            "right": ref(right.terminal_node_id, right.terminal_output),
                        },
                        parameters={
                            "join_key": enum(join_constraint["join_key"]),
                            "no_match_policy": enum(join_constraint["no_match_policy"]),
                            "same_team_perspective_required": boolean(join_constraint["same_team_perspective_required"]),
                            "entity_identity_preserved_required": boolean(join_constraint["entity_identity_preserved_required"]),
                            "frame_alignment_required": boolean(join_constraint["frame_alignment_required"]),
                            "unconstrained": boolean(join_constraint["unconstrained"]),
                            "unconstrained_rationale": enum(join_constraint["unconstrained_rationale"]),
                            "left_anchor_id_field": enum(join_constraint["left_anchor_id_field"]),
                            "right_anchor_id_field": enum(join_constraint["right_anchor_id_field"]),
                            "left_frame_field": enum(join_constraint["left_frame_field"]),
                            "right_frame_field": enum(join_constraint["right_frame_field"]),
                            "left_entity_id_field": enum(join_constraint["left_entity_id_field"]),
                            "right_entity_id_field": enum(join_constraint["right_entity_id_field"]),
                            "left_start_frame_field": enum(join_constraint["left_start_frame_field"]),
                            "left_end_frame_field": enum(join_constraint["left_end_frame_field"]),
                            "right_start_frame_field": enum(join_constraint["right_start_frame_field"]),
                            "right_end_frame_field": enum(join_constraint["right_end_frame_field"]),
                            "left_team_role_field": enum(join_constraint["left_team_role_field"]),
                            "right_team_role_field": enum(join_constraint["right_team_role_field"]),
                            "left_status_field": enum(join_constraint["left_status_field"]),
                            "right_status_field": enum(join_constraint["right_status_field"]),
                            "required_status_value": enum(join_constraint["required_status_value"]),
                            "left_required_status_value": enum(join_constraint["left_required_status_value"]),
                            "right_required_status_value": enum(join_constraint["right_required_status_value"]),
                            "maximum_frame_delta": number(join_constraint["maximum_frame_delta"], "frame"),
                        },
                        output_evidence_fields=output_fields,
                    )
                )
                field_sources: dict[str, tuple[str, str]] = {}
                for field in output_fields:
                    field_sources[field] = (node_id, typed_join_output_for_field(field))
                return BuildResult(
                    nodes=dedupe_nodes(nodes),
                    terminal_node_id=node_id,
                    terminal_entry="operator:typed_join",
                    terminal_output="typed_join_records",
                    field_sources=field_sources,
                    rules_used=[*left.rules_used, *right.rules_used, "generic_typed_join_operator"],
                    providers_used=[*left.providers_used, *right.providers_used, "operator:typed_join"],
                    metadata={
                        "typed_join_candidate_outputs": candidate_summaries,
                        "typed_join_selected_output": {
                            "left": {
                                "source": left_candidate["source_name"],
                                "output": left_candidate["output_name"],
                                "source_kind": left_candidate["source_kind"],
                            },
                            "right": {
                                "source": right_candidate["source_name"],
                                "output": right_candidate["output_name"],
                                "source_kind": right_candidate["source_kind"],
                            },
                        },
                        "typed_join_constraint": join_constraint,
                        "typed_join_output_fields": sorted(output_fields),
                        "left_build_metadata": left.metadata,
                        "right_build_metadata": right.metadata,
                    },
                )
            except SynthesisError as error:
                attempts.append(
                    {
                        "left_source": left_candidate["source_name"],
                        "right_source": right_candidate["source_name"],
                        "taxonomy": error.taxonomy,
                        "message": error.message,
                        **error.details,
                    }
                )
    raise SynthesisError(
        "missing_constraint",
        "No declared typed_join side pairing satisfied the target contract.",
        {"attempted": attempts[: context.max_branching], "candidate_outputs": candidate_summaries},
    )


def typed_join_constraint_payload(constraint: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "kind",
        "join_key",
        "no_match_policy",
        "same_team_perspective_required",
        "entity_identity_preserved_required",
        "frame_alignment_required",
        "unconstrained",
        "unconstrained_rationale",
        "left_anchor_id_field",
        "right_anchor_id_field",
        "left_frame_field",
        "right_frame_field",
        "left_entity_id_field",
        "right_entity_id_field",
        "left_start_frame_field",
        "left_end_frame_field",
        "right_start_frame_field",
        "right_end_frame_field",
        "left_team_role_field",
        "right_team_role_field",
        "left_status_field",
        "right_status_field",
        "required_status_value",
        "left_required_status_value",
        "right_required_status_value",
        "maximum_frame_delta",
        "left_required_fields",
        "right_required_fields",
        "left_input_context",
        "right_input_context",
        "left_composition_constraints",
        "right_composition_constraints",
    }
    unapplied = sorted(key for key in constraint if key not in allowed_keys)
    if unapplied:
        raise SynthesisError(
            "missing_constraint",
            "typed_join supplied unsupported keys that synthesis cannot apply.",
            {"unapplied_typed_join_constraint_keys": unapplied},
        )
    return {
        "join_key": required_typed_join_constraint(constraint, "join_key"),
        "no_match_policy": str(constraint.get("no_match_policy", "UNKNOWN")),
        "same_team_perspective_required": bool(constraint.get("same_team_perspective_required", False)),
        "entity_identity_preserved_required": bool(constraint.get("entity_identity_preserved_required", False)),
        "frame_alignment_required": bool(constraint.get("frame_alignment_required", False)),
        "unconstrained": bool(constraint.get("unconstrained", False)),
        "unconstrained_rationale": str(constraint.get("unconstrained_rationale", "none")),
        "left_anchor_id_field": str(constraint.get("left_anchor_id_field", "anchor_id")),
        "right_anchor_id_field": str(constraint.get("right_anchor_id_field", "anchor_id")),
        "left_frame_field": str(constraint.get("left_frame_field", "anchor_frame_id")),
        "right_frame_field": str(constraint.get("right_frame_field", "anchor_frame_id")),
        "left_entity_id_field": str(constraint.get("left_entity_id_field", "none")),
        "right_entity_id_field": str(constraint.get("right_entity_id_field", "none")),
        "left_start_frame_field": str(constraint.get("left_start_frame_field", "start_frame_id")),
        "left_end_frame_field": str(constraint.get("left_end_frame_field", "end_frame_id")),
        "right_start_frame_field": str(constraint.get("right_start_frame_field", "start_frame_id")),
        "right_end_frame_field": str(constraint.get("right_end_frame_field", "end_frame_id")),
        "left_team_role_field": str(constraint.get("left_team_role_field", "none")),
        "right_team_role_field": str(constraint.get("right_team_role_field", "none")),
        "left_status_field": str(constraint.get("left_status_field", "none")),
        "right_status_field": str(constraint.get("right_status_field", "none")),
        "required_status_value": str(constraint.get("required_status_value", "PASS")),
        "left_required_status_value": str(
            constraint.get("left_required_status_value", constraint.get("required_status_value", "PASS"))
        ),
        "right_required_status_value": str(
            constraint.get("right_required_status_value", constraint.get("required_status_value", "PASS"))
        ),
        "maximum_frame_delta": float(constraint.get("maximum_frame_delta", 0.0)),
        "left_required_fields": [str(item) for item in constraint.get("left_required_fields", [])],
        "right_required_fields": [str(item) for item in constraint.get("right_required_fields", [])],
        "left_input_context": dict(constraint.get("left_input_context", {})),
        "right_input_context": dict(constraint.get("right_input_context", {})),
        "left_composition_constraints": list(constraint.get("left_composition_constraints", [])),
        "right_composition_constraints": list(constraint.get("right_composition_constraints", [])),
    }


def required_typed_join_constraint(constraint: dict[str, Any], key: str) -> str:
    value = constraint.get(key)
    if value is None or str(value) == "" or str(value) == "none":
        raise SynthesisError(
            "missing_constraint",
            f"typed_join requires declared {key}; no provider-field default is allowed.",
            {"missing_typed_join_constraint_key": key},
        )
    return str(value)


def typed_join_side_required_fields(constraint: dict[str, Any], side: str) -> set[str]:
    fields = set(str(item) for item in constraint[f"{side}_required_fields"])
    for key in typed_join_side_field_parameter_names(side, str(constraint["join_key"])):
        fields.add(str(constraint[key]))
    if bool(constraint["same_team_perspective_required"]):
        fields.add(str(constraint[f"{side}_team_role_field"]))
    if bool(constraint["entity_identity_preserved_required"]):
        fields.add(str(constraint[f"{side}_entity_id_field"]))
    if bool(constraint["frame_alignment_required"]):
        fields.add(str(constraint[f"{side}_frame_field"]))
    status_field = str(constraint[f"{side}_status_field"])
    if status_field != "none":
        fields.add(status_field)
    fields.discard("none")
    return fields


def typed_join_side_field_parameter_names(side: str, join_key: str) -> tuple[str, ...]:
    if join_key == "same_anchor":
        return (f"{side}_anchor_id_field",)
    if join_key == "same_frame_window":
        return (f"{side}_frame_field",)
    if join_key == "same_entity":
        return (f"{side}_entity_id_field",)
    if join_key == "episode_overlap":
        return (f"{side}_start_frame_field", f"{side}_end_frame_field")
    return ()


def typed_join_side_candidates(
    context: SearchContext,
    *,
    required_fields: set[str],
    input_name: str,
    input_context: dict[str, Any],
    nested_constraints: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if nested_constraints:
        return [
            {
                "source_kind": "operator_composition",
                "source_name": "nested_operator_composition",
                "output_name": "<terminal>",
                "required_fields": sorted(required_fields),
                "input_context": {},
                "composition_constraints": nested_constraints,
            }
        ]
    input_def = {item.name: item for item in TYPED_JOIN_SIGNATURE.inputs}[input_name]
    scored: list[tuple[int, str, str, CatalogEntry, CatalogOutput]] = []
    for entry in context.catalog.entries.values():
        fields = context.catalog.field_set(entry)
        if not required_fields.issubset(fields):
            continue
        for output in entry.outputs:
            if not composition_output_matches_operator_input(output, input_def):
                continue
            output_fields = {output.name, *output.evidence_fields}
            if not required_fields.issubset(output_fields):
                continue
            score = 20 * len(required_fields & output_fields)
            scored.append((-score, entry.name, output.name, entry, output))
    return [
        {
            "source_kind": "catalog_entry",
            "source_name": entry.name,
            "output_name": output.name,
            "entry": entry,
            "output": output,
            "required_fields": sorted(required_fields),
            "input_context": input_context,
            "composition_constraints": [],
        }
        for _score, _entry_name, _output_name, entry, output in sorted(scored)
    ]


def build_typed_join_side(
    context: SearchContext,
    candidate: dict[str, Any],
    *,
    depth: int,
) -> BuildResult:
    if candidate["source_kind"] == "operator_composition":
        nested_context = SearchContext(
            catalog=context.catalog,
            target_contract={
                **context.target_contract,
                "required_evidence": list(candidate["required_fields"]),
                "composition_constraints": list(candidate["composition_constraints"]),
            },
            counter=context.counter,
            max_depth=context.max_depth,
            max_branching=context.max_branching,
        )
        return build_operator_composition(
            nested_context,
            set(candidate["required_fields"]),
            depth=depth,
        )
    return build_entry(
        context,
        candidate["entry"],
        set(candidate["required_fields"]),
        depth=depth,
        input_context=dict(candidate["input_context"]),
    )


def typed_join_output_for_field(field: str) -> str:
    if field == "typed_join_status":
        return "typed_join_status"
    return "typed_join_records"


def build_window_operator(
    context: SearchContext,
    required_fields: set[str],
    *,
    depth: int,
) -> BuildResult:
    constraint = first_target_constraint(context, "window")
    window_constraint = window_constraint_payload(constraint)
    attempts: list[dict[str, Any]] = []
    candidates = window_candidates(context, window_constraint)
    candidate_summaries = [
        {
            "anchor_provider": candidate["anchor_entry"].name,
            "anchor_output": candidate["anchor_output"].name,
            "continuity_provider": None
            if candidate["continuity_entry"] is None
            else candidate["continuity_entry"].name,
            "continuity_output": None
            if candidate["continuity_output"] is None
            else candidate["continuity_output"].name,
            "anchor_required_fields": candidate["anchor_required_fields"],
            "continuity_required_fields": candidate["continuity_required_fields"],
        }
        for candidate in candidates
    ]
    for candidate in candidates[: context.max_branching]:
        try:
            anchor = build_entry(
                context,
                candidate["anchor_entry"],
                set(candidate["anchor_required_fields"]),
                depth=depth + 1,
                input_context={},
            )
            continuity = None
            if candidate["continuity_entry"] is not None:
                continuity = build_entry(
                    context,
                    candidate["continuity_entry"],
                    set(candidate["continuity_required_fields"]),
                    depth=depth + 1,
                    input_context={},
                )
            missing_anchor_fields = sorted(
                field for field in candidate["anchor_required_fields"] if field not in anchor.field_sources
            )
            missing_continuity_fields = []
            if continuity is not None:
                missing_continuity_fields = sorted(
                    field for field in candidate["continuity_required_fields"] if field not in continuity.field_sources
                )
            if missing_anchor_fields or missing_continuity_fields:
                raise SynthesisError(
                    "missing_constraint",
                    "Window composition did not cover declared anchor/continuity fields.",
                    {
                        "missing_anchor_fields": missing_anchor_fields,
                        "missing_continuity_fields": missing_continuity_fields,
                    },
                )
            node_id = context.node_id("window")
            nodes = [*anchor.nodes]
            node_inputs = {"anchors": ref(anchor.terminal_node_id, candidate["anchor_output"].name)}
            providers_used = [*anchor.providers_used]
            rules_used = [*anchor.rules_used]
            field_sources = {**anchor.field_sources}
            metadata: dict[str, Any] = {
                "window_discovery_space_count": len(candidates),
                "window_candidate_outputs": candidate_summaries,
                "window_selected_output": {
                    "anchor_provider": candidate["anchor_entry"].name,
                    "anchor_output": candidate["anchor_output"].name,
                    "continuity_provider": None
                    if candidate["continuity_entry"] is None
                    else candidate["continuity_entry"].name,
                    "continuity_output": None
                    if candidate["continuity_output"] is None
                    else candidate["continuity_output"].name,
                },
                "window_constraint": window_constraint,
                "anchor_build_metadata": anchor.metadata,
            }
            if continuity is not None:
                nodes.extend(continuity.nodes)
                node_inputs["continuity_evidence"] = ref(
                    continuity.terminal_node_id,
                    candidate["continuity_output"].name,
                )
                providers_used.extend(continuity.providers_used)
                rules_used.extend(continuity.rules_used)
                field_sources.update(continuity.field_sources)
                metadata["continuity_build_metadata"] = continuity.metadata
            nodes.append(
                operator_node(
                    node_id=node_id,
                    operator_name="window",
                    version="0.1.0",
                    inputs=node_inputs,
                    parameters={
                        "window_mode": enum(window_constraint["window_mode"]),
                        "anchor_frame_field": enum(window_constraint["anchor_frame_field"]),
                        "before_duration_seconds": number(
                            float(window_constraint["before_duration_seconds"]),
                            "second",
                        ),
                        "after_duration_seconds": number(
                            float(window_constraint["after_duration_seconds"]),
                            "second",
                        ),
                        "frame_rate_hz": number(float(window_constraint["frame_rate_hz"]), "hertz"),
                        "anchor_status_field": enum(window_constraint["anchor_status_field"]),
                        "anchor_status_value": enum(window_constraint["anchor_status_value"]),
                        "truncation_policy": enum(window_constraint["truncation_policy"]),
                        "continuity_policy": enum(window_constraint["continuity_policy"]),
                        "continuity_start_frame_field": enum(window_constraint["continuity_start_frame_field"]),
                        "continuity_end_frame_field": enum(window_constraint["continuity_end_frame_field"]),
                        "continuity_status_field": enum(window_constraint["continuity_status_field"]),
                        "continuity_status_value": enum(window_constraint["continuity_status_value"]),
                        "anchor_team_role_field": enum(window_constraint["anchor_team_role_field"]),
                        "continuity_team_role_field": enum(window_constraint["continuity_team_role_field"]),
                        "team_binding_policy": enum(window_constraint["team_binding_policy"]),
                        "continuity_overlap_policy": enum(window_constraint["continuity_overlap_policy"]),
                        "overlap_policy": enum(window_constraint["overlap_policy"]),
                    },
                )
            )
            for field in WINDOW_FIELDS:
                field_sources.setdefault(field, (node_id, window_output_for_field(field)))
            return BuildResult(
                nodes=dedupe_nodes(nodes),
                terminal_node_id=node_id,
                terminal_entry="operator:window",
                terminal_output="window_records",
                field_sources=field_sources,
                rules_used=[*rules_used, "generic_window_operator"],
                providers_used=[*providers_used, "operator:window"],
                metadata=metadata,
            )
        except SynthesisError as error:
            attempts.append(
                {
                    "anchor_provider": candidate["anchor_entry"].name,
                    "continuity_provider": None
                    if candidate["continuity_entry"] is None
                    else candidate["continuity_entry"].name,
                    "taxonomy": error.taxonomy,
                    "message": error.message,
                    **error.details,
                }
            )
    raise SynthesisError(
        "missing_constraint",
        "No typed anchor/continuity source satisfied window.",
        {"attempted": attempts[: context.max_branching], "candidate_count": len(candidates)},
    )


def window_constraint_payload(constraint: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "kind",
        "window_mode",
        "anchor_frame_field",
        "before_duration_seconds",
        "after_duration_seconds",
        "frame_rate_hz",
        "anchor_status_field",
        "anchor_status_value",
        "truncation_policy",
        "continuity_policy",
        "continuity_start_frame_field",
        "continuity_end_frame_field",
        "continuity_status_field",
        "continuity_status_value",
        "anchor_team_role_field",
        "continuity_team_role_field",
        "team_binding_policy",
        "continuity_overlap_policy",
        "overlap_policy",
    }
    unapplied = sorted(key for key in constraint if key not in allowed_keys)
    if unapplied:
        raise SynthesisError(
            "missing_constraint",
            "window supplied unsupported keys that synthesis cannot apply.",
            {"unapplied_window_constraint_keys": unapplied},
        )
    return {
        "window_mode": required_window_constraint(constraint, "window_mode"),
        "anchor_frame_field": required_window_constraint(constraint, "anchor_frame_field"),
        "before_duration_seconds": float(required_window_constraint(constraint, "before_duration_seconds")),
        "after_duration_seconds": float(required_window_constraint(constraint, "after_duration_seconds")),
        "frame_rate_hz": float(required_window_constraint(constraint, "frame_rate_hz")),
        "anchor_status_field": str(constraint.get("anchor_status_field", "none")),
        "anchor_status_value": str(constraint.get("anchor_status_value", "PASS")),
        "truncation_policy": str(constraint.get("truncation_policy", "emit_with_flag")),
        "continuity_policy": str(constraint.get("continuity_policy", "fixed_duration")),
        "continuity_start_frame_field": str(constraint.get("continuity_start_frame_field", "none")),
        "continuity_end_frame_field": str(constraint.get("continuity_end_frame_field", "none")),
        "continuity_status_field": str(constraint.get("continuity_status_field", "none")),
        "continuity_status_value": str(constraint.get("continuity_status_value", "PASS")),
        "anchor_team_role_field": str(constraint.get("anchor_team_role_field", "none")),
        "continuity_team_role_field": str(constraint.get("continuity_team_role_field", "none")),
        "team_binding_policy": str(constraint.get("team_binding_policy", "none")),
        "continuity_overlap_policy": str(constraint.get("continuity_overlap_policy", "latest_start_covering_anchor")),
        "overlap_policy": str(constraint.get("overlap_policy", "preserve_all")),
    }


def required_window_constraint(constraint: dict[str, Any], key: str) -> str:
    value = constraint.get(key)
    if value is None or str(value) == "" or str(value) == "none":
        raise SynthesisError(
            "missing_constraint",
            f"window requires declared {key}; no provider-field default is allowed.",
            {"missing_window_constraint_key": key},
        )
    return str(value)


def window_candidates(context: SearchContext, constraint: dict[str, Any]) -> list[dict[str, Any]]:
    operator_inputs = {item.name: item for item in WINDOW_SIGNATURE.inputs}
    anchor_required_fields = {
        str(constraint["anchor_frame_field"]),
    }
    if str(constraint["anchor_status_field"]) != "none":
        anchor_required_fields.add(str(constraint["anchor_status_field"]))
    continuity_policy = str(constraint["continuity_policy"])
    continuity_required_fields: set[str] = set()
    if continuity_policy != "fixed_duration":
        anchor_required_fields.add(str(constraint["anchor_team_role_field"]))
        continuity_required_fields.update(
            {
                str(constraint["continuity_start_frame_field"]),
                str(constraint["continuity_end_frame_field"]),
                str(constraint["continuity_team_role_field"]),
            }
        )
        if str(constraint["team_binding_policy"]) != "equal_team_role":
            raise SynthesisError(
                "missing_constraint",
                "window continuity policies require declared equal-team binding.",
                {"continuity_policy": continuity_policy},
            )
        if "none" in continuity_required_fields or "none" in anchor_required_fields:
            raise SynthesisError(
                "missing_constraint",
                "window continuity policies require declared continuity frame and team fields.",
                {"continuity_policy": continuity_policy},
            )
        if str(constraint["continuity_status_field"]) != "none":
            continuity_required_fields.add(str(constraint["continuity_status_field"]))
    anchors = window_anchor_sources(context, anchor_required_fields, operator_inputs["anchors"])
    continuity_sources = (
        [(None, None)]
        if continuity_policy == "fixed_duration"
        else window_anchor_sources(context, continuity_required_fields, operator_inputs["continuity_evidence"])
    )
    candidates: list[tuple[int, str, str, str, dict[str, Any]]] = []
    for anchor_entry, anchor_output in anchors:
        anchor_fields = {anchor_output.name, *anchor_output.evidence_fields}
        for continuity_entry, continuity_output in continuity_sources:
            score = 20 * len(anchor_required_fields & anchor_fields)
            continuity_name = ""
            continuity_output_name = ""
            if continuity_entry is not None and continuity_output is not None:
                continuity_fields = {continuity_output.name, *continuity_output.evidence_fields}
                score += 20 * len(continuity_required_fields & continuity_fields)
                continuity_name = continuity_entry.name
                continuity_output_name = continuity_output.name
            candidates.append(
                (
                    -score,
                    anchor_entry.name,
                    anchor_output.name,
                    continuity_name,
                    {
                        "anchor_entry": anchor_entry,
                        "anchor_output": anchor_output,
                        "continuity_entry": continuity_entry,
                        "continuity_output": continuity_output,
                        "anchor_required_fields": sorted(anchor_required_fields),
                        "continuity_required_fields": sorted(continuity_required_fields),
                    },
                )
            )
    return [candidate for *_prefix, candidate in sorted(candidates)]


def window_anchor_sources(
    context: SearchContext,
    required_fields: set[str],
    input_def: Any,
) -> list[tuple[CatalogEntry, CatalogOutput]]:
    scored: list[tuple[int, str, str, CatalogEntry, CatalogOutput]] = []
    for entry in context.catalog.entries.values():
        fields = context.catalog.field_set(entry)
        if not required_fields.issubset(fields):
            continue
        for output in entry.outputs:
            if not composition_output_matches_operator_input(output, input_def):
                continue
            output_fields = {output.name, *output.evidence_fields}
            if not required_fields.issubset(output_fields):
                continue
            score = 20 * len(required_fields & output_fields)
            scored.append((-score, entry.name, output.name, entry, output))
    return [(entry, output) for _score, _entry, _output, entry, output in sorted(scored)]


def delta_across_anchor_candidates(
    context: SearchContext,
    constraint: dict[str, Any],
) -> list[dict[str, Any]]:
    operator_inputs = {item.name: item for item in DELTA_ACROSS_ANCHOR_SIGNATURE.inputs}
    before_value_field = str(constraint["before_value_field"])
    after_value_field = str(constraint["after_value_field"])
    before_status_field = str(constraint["before_status_field"])
    after_status_field = str(constraint["after_status_field"])
    before_frame_field = str(constraint["before_frame_field"])
    after_frame_field = str(constraint["after_frame_field"])
    before_input_context = dict(constraint["before_input_context"])
    after_input_context = dict(constraint["after_input_context"])
    before_carrier_id_field = str(before_input_context.get("carrier_id_field", "none"))
    after_carrier_id_field = str(after_input_context.get("carrier_id_field", "none"))
    anchor_status_field = str(constraint["anchor_status_field"])
    anchor_required_fields = {before_frame_field, after_frame_field}
    if before_carrier_id_field != "none":
        anchor_required_fields.add(before_carrier_id_field)
    if after_carrier_id_field != "none":
        anchor_required_fields.add(after_carrier_id_field)
    if anchor_status_field != "none":
        anchor_required_fields.add(anchor_status_field)
    before_required_fields = {before_value_field}
    after_required_fields = {after_value_field}
    if before_status_field != "none":
        before_required_fields.add(before_status_field)
    if after_status_field != "none":
        after_required_fields.add(after_status_field)
    scored: list[tuple[int, str, str, dict[str, Any]]] = []
    for evaluator in context.catalog.entries.values():
        if not has_single_anchor_input(evaluator):
            continue
        evaluator_fields = context.catalog.field_set(evaluator)
        if not before_required_fields.issubset(evaluator_fields):
            continue
        if not after_required_fields.issubset(evaluator_fields):
            continue
        evaluator_input = evaluator.inputs[0]
        if not composition_output_matches_operator_input(
            context.catalog.anchor_output(evaluator),
            operator_inputs["before_evaluations"],
        ):
            continue
        for anchor_entry, anchor_output in context.catalog.compatible_outputs(evaluator_input):
            if anchor_entry.name == evaluator.name:
                continue
            if not composition_output_matches_operator_input(anchor_output, operator_inputs["anchors"]):
                continue
            anchor_fields = context.catalog.field_set(anchor_entry)
            if not runtime_or_catalog_field_compatible(anchor_fields, anchor_required_fields):
                continue
            allowed_frames = set(
                allowed_parameter_values(evaluator, "frame_field")
                or allowed_parameter_values(evaluator, "anchor_frame_field")
            )
            if before_frame_field not in allowed_frames or after_frame_field not in allowed_frames:
                continue
            if validate_input_context_for_evaluator(evaluator, before_input_context, anchor_fields=anchor_fields):
                continue
            if validate_input_context_for_evaluator(evaluator, after_input_context, anchor_fields=anchor_fields):
                continue
            score = 0
            target_fields = required_target_fields(context.target_contract)
            score += 20 * len(({before_value_field, after_value_field} | before_required_fields | after_required_fields) & target_fields)
            score += 12 if anchor_status_field != "none" and anchor_status_field in anchor_fields else 0
            score += 8 if before_frame_field != after_frame_field else 0
            scored.append(
                (
                    -score,
                    anchor_entry.name,
                    evaluator.name,
                    {
                        "anchor_entry": anchor_entry,
                        "evaluator_entry": evaluator,
                        "anchor_required_fields": sorted(anchor_required_fields),
                        "before_required_fields": sorted(before_required_fields),
                        "after_required_fields": sorted(after_required_fields),
                        "before_value_field": before_value_field,
                        "after_value_field": after_value_field,
                        "before_status_field": before_status_field,
                        "after_status_field": after_status_field,
                        "before_frame_field": before_frame_field,
                        "after_frame_field": after_frame_field,
                        "before_input_context": before_input_context,
                        "after_input_context": after_input_context,
                    },
                )
            )
    return [candidate for *_prefix, candidate in sorted(scored)]


OPERATOR_COMPOSITION_BUILDERS = {
    "delta_across_anchor": build_delta_across_anchor_operator,
    "extremum_over_set": build_extremum_over_set_operator,
    "typed_join": build_typed_join_operator,
    "window": build_window_operator,
    "vector_projection": build_project_onto_axis,
}


def build_entry(
    context: SearchContext,
    entry: CatalogEntry,
    required_fields: set[str],
    *,
    depth: int,
    input_context: dict[str, Any],
) -> BuildResult:
    if depth > context.max_depth:
        raise SynthesisError(
            "search_budget_exceeded",
            "Search exceeded max depth before satisfying the target contract.",
            {"entry": entry.name, "max_depth": context.max_depth},
        )
    if entry.name == "join_episode_sets":
        return build_join_episode_sets(context, entry, required_fields, depth=depth)
    # Builder boundary: R1 operators are synthesized through
    # OPERATOR_COMPOSITION_BUILDERS from target constraints. change_across_anchor
    # is a grandfathered catalog-specific composition provider and remains on
    # this branch until a later extraction packet migrates it to the operator
    # registry.
    if entry.name == "change_across_anchor":
        return build_change_across_anchor(context, entry, required_fields, depth=depth, input_context=input_context)
    if entry.name == "controlled_line_break_episode":
        return build_controlled_line_break_episode(context, entry, required_fields, depth=depth)
    if should_build_relation_on_anchor(context, entry, required_fields, input_context):
        return build_relation_on_anchor(context, entry, required_fields, depth=depth)

    nodes: list[dict[str, Any]] = []
    field_sources: dict[str, tuple[str, str]] = {}
    rules_used = ["provider_field_backward_search"]
    providers_used: list[str] = []
    inputs: dict[str, dict[str, str]] = {}
    input_builds: list[BuildResult] = []
    for input_def in entry.inputs:
        child = prebuilt_input(input_context, input_def.name)
        if child is None:
            provider, output = choose_input_provider(context, consumer=entry, input_def=input_def, depth=depth)
            child = build_entry(
                context,
                provider,
                required_fields_for_input(entry, input_def, required_fields),
                depth=depth + 1,
                input_context=child_input_context(entry, input_def),
            )
            output_name = output.name if output.name in {out.name for out in provider.outputs} else child.terminal_output
        else:
            output_name = child.terminal_output
        input_builds.append(child)
        nodes.extend(child.nodes)
        field_sources.update(child.field_sources)
        rules_used.extend(child.rules_used)
        providers_used.extend(child.providers_used)
        inputs[input_def.name] = ref(child.terminal_node_id, output_name)

    node_id = context.node_id(entry.name)
    output_name = context.catalog.anchor_output(entry).name
    params = infer_parameters(entry, input_builds=input_builds, input_context=input_context)
    nodes.append(catalog_node(node_id, entry, inputs=inputs, parameters=params))
    for field in context.catalog.field_set(entry):
        source_output = output_name_for_field(context.catalog, entry, field) or output_name
        field_sources.setdefault(field, (node_id, source_output))
    providers_used.append(entry.name)
    return BuildResult(
        nodes=nodes,
        terminal_node_id=node_id,
        terminal_entry=entry.name,
        terminal_output=output_name,
        field_sources=field_sources,
        rules_used=rules_used,
        providers_used=providers_used,
    )


def build_controlled_line_break_episode(
    context: SearchContext,
    entry: CatalogEntry,
    required_fields: set[str],
    *,
    depth: int,
) -> BuildResult:
    rules = ["provider_input_coherence"]
    controlled_pass = build_entry(
        context,
        require_entry(context, "controlled_pass_episode"),
        {"anchor_id", "controlled_reception_frame_id", "pass_episode_id", "physical_release_frame_id", "receiver_id"},
        depth=depth + 1,
        input_context={},
    )
    line_model = build_entry(
        context,
        require_entry(context, "multi_line_model"),
        {"anchor_id", "line_x_m", "multi_line_status", "observed_line_count", "target_line_rank", "defensive_line_player_ids"},
        depth=depth + 1,
        input_context={"anchors": controlled_pass, "anchor_frame_field": "physical_release_frame_id"},
    )
    release_position = build_entry(
        context,
        require_entry(context, "relative_position_to_line"),
        {"anchor_id", "relative_position_status", "signed_distance_to_line_m"},
        depth=depth + 1,
        input_context={
            "entity_anchors": controlled_pass,
            "line_evaluations": line_model,
            "entity_frame_field": "physical_release_frame_id",
        },
    )
    reception_position = build_entry(
        context,
        require_entry(context, "relative_position_to_line"),
        {"anchor_id", "relative_position_status", "signed_distance_to_line_m"},
        depth=depth + 1,
        input_context={
            "entity_anchors": controlled_pass,
            "line_evaluations": line_model,
            "entity_frame_field": "controlled_reception_frame_id",
        },
    )
    node_id = context.node_id(entry.name)
    nodes = [
        *controlled_pass.nodes,
        *line_model.nodes,
        *release_position.nodes,
        *reception_position.nodes,
    ]
    nodes.append(
        catalog_node(
            node_id,
            entry,
            inputs={
                "controlled_pass_anchors": ref(controlled_pass.terminal_node_id, controlled_pass.terminal_output),
                "line_evaluations": ref(line_model.terminal_node_id, line_model.terminal_output),
                "release_relative_positions": ref(release_position.terminal_node_id, release_position.terminal_output),
                "reception_relative_positions": ref(reception_position.terminal_node_id, reception_position.terminal_output),
            },
            parameters=infer_parameters(entry, input_builds=[controlled_pass, line_model, release_position, reception_position], input_context={}),
        )
    )
    field_sources = {
        **controlled_pass.field_sources,
        **line_model.field_sources,
        **release_position.field_sources,
        **reception_position.field_sources,
    }
    for field in context.catalog.field_set(entry):
        field_sources.setdefault(field, (node_id, output_name_for_field(context.catalog, entry, field) or "anchor_evaluations"))
    return BuildResult(
        nodes=dedupe_nodes(nodes),
        terminal_node_id=node_id,
        terminal_entry=entry.name,
        terminal_output="anchor_evaluations",
        field_sources=field_sources,
        rules_used=[
            *controlled_pass.rules_used,
            *line_model.rules_used,
            *release_position.rules_used,
            *reception_position.rules_used,
            *rules,
        ],
        providers_used=[
            *controlled_pass.providers_used,
            *line_model.providers_used,
            *release_position.providers_used,
            *reception_position.providers_used,
            entry.name,
        ],
    )


def should_build_relation_on_anchor(
    context: SearchContext,
    entry: CatalogEntry,
    required_fields: set[str],
    input_context: dict[str, Any],
) -> bool:
    if input_context:
        return False
    if not has_single_anchor_input(entry):
        return False
    constraints = target_constraints(context, "relation_on_anchor")
    if not constraints:
        return False
    entry_fields = context.catalog.field_set(entry)
    for constraint in constraints:
        relation_status_field = str(constraint.get("relation_status_field", ""))
        if relation_status_field and relation_status_field in entry_fields:
            return True
    return bool(required_fields & entry_fields and required_fields - entry_fields)


def build_relation_on_anchor(
    context: SearchContext,
    entry: CatalogEntry,
    required_fields: set[str],
    *,
    depth: int,
) -> BuildResult:
    rules = ["generic_relation_on_anchor", "typed_anchor_provider_discovery"]
    constraint = first_target_constraint(context, "relation_on_anchor")
    input_def = entry.inputs[0]
    entry_fields = context.catalog.field_set(entry)
    anchor_required_fields = set(required_fields - entry_fields)
    for field_name in (
        constraint.get("anchor_status_field"),
        constraint.get("anchor_frame_field"),
        constraint.get("anchor_identity_field"),
        constraint.get("target_player_id_field"),
    ):
        if field_name:
            anchor_required_fields.add(str(field_name))
    attempts: list[dict[str, Any]] = []
    candidates = context.catalog.compatible_outputs(input_def)
    scored_candidates: list[tuple[int, str, str, CatalogEntry, CatalogOutput]] = []
    for provider, output in candidates:
        if provider.name == entry.name:
            continue
        provider_fields = context.catalog.field_set(provider)
        anchor_status_field = str(constraint.get("anchor_status_field", ""))
        if anchor_status_field and anchor_status_field not in provider_fields:
            continue
        covered = provider_fields & anchor_required_fields
        if not covered:
            continue
        score = 20 * len(covered)
        if str(constraint.get("anchor_status_field", "")) in provider_fields:
            score += 12
        if str(constraint.get("anchor_frame_field", "")) in provider_fields:
            score += 6
        scored_candidates.append((-score, provider.name, output.name, provider, output))

    for _score, _provider_name, _output_name, provider, output in sorted(scored_candidates)[: context.max_branching]:
        try:
            anchor = build_entry(
                context,
                provider,
                anchor_required_fields,
                depth=depth + 1,
                input_context={},
            )
            missing_anchor_fields = sorted(field for field in anchor_required_fields if field not in anchor.field_sources)
            if missing_anchor_fields:
                raise SynthesisError(
                    "missing_constraint",
                    "Candidate anchor provider did not expose required anchor fields.",
                    {
                        "anchor_provider": provider.name,
                        "missing_anchor_fields": missing_anchor_fields,
                    },
                )
            node_id = context.node_id(entry.name)
            nodes = [*anchor.nodes]
            node_input_context = relation_on_anchor_input_context(constraint)
            relation_parameters = infer_parameters(entry, input_builds=[anchor], input_context=node_input_context)
            nodes.append(
                catalog_node(
                    node_id,
                    entry,
                    inputs={"anchors": ref(anchor.terminal_node_id, output.name if output.name in {out.name for out in provider.outputs} else anchor.terminal_output)},
                    parameters=relation_parameters,
                )
            )
            field_sources = {**anchor.field_sources}
            for field in entry_fields:
                field_sources.setdefault(field, (node_id, output_name_for_field(context.catalog, entry, field) or "anchor_evaluations"))
            return BuildResult(
                nodes=dedupe_nodes(nodes),
                terminal_node_id=node_id,
                terminal_entry=entry.name,
                terminal_output="anchor_evaluations",
                field_sources=field_sources,
                rules_used=[*anchor.rules_used, *rules],
                providers_used=[*anchor.providers_used, entry.name],
                metadata={
                    "relation_on_anchor_provider": entry.name,
                    "relation_on_anchor_constraint": node_input_context,
                    "relation_on_anchor_applied_parameters": relation_parameters,
                },
            )
        except SynthesisError as error:
            attempts.append(
                {
                    "anchor_provider": provider.name,
                    "taxonomy": error.taxonomy,
                    "message": error.message,
                    **error.details,
                }
            )
    raise SynthesisError(
        "missing_constraint",
        "No typed anchor-relation composition satisfied the requested evidence fields.",
        {"attempted": attempts[: context.max_branching], "required_fields": sorted(required_fields)},
    )


def relation_on_anchor_input_context(constraint: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "kind",
        "relation_status_field",
        "anchor_status_field",
        "anchor_status_value",
        "anchor_identity_field",
        "anchor_frame_field",
        "candidate_scope",
        "target_player_id_field",
        "minimum_observed_candidates",
        "support_region_mode",
        "maximum_arrival_seconds",
        "minimum_duration_seconds",
        "maximum_support_distance_m",
        "minimum_supporting_players",
        "required_anchor_status_field",
        "required_anchor_status_value",
    }
    unapplied = sorted(key for key in constraint if key not in allowed_keys)
    if unapplied:
        raise SynthesisError(
            "missing_constraint",
            "relation_on_anchor supplied unsupported keys that synthesis cannot apply.",
            {"unapplied_relation_constraint_keys": unapplied},
        )
    payload: dict[str, Any] = {}
    for key in (
        "anchor_frame_field",
        "candidate_scope",
        "target_player_id_field",
        "minimum_observed_candidates",
        "support_region_mode",
        "maximum_arrival_seconds",
        "minimum_duration_seconds",
        "maximum_support_distance_m",
        "minimum_supporting_players",
        "required_anchor_status_field",
        "required_anchor_status_value",
    ):
        if key in constraint:
            payload[key] = constraint[key]
    anchor_status_field = constraint.get("anchor_status_field")
    if anchor_status_field and "required_anchor_status_field" not in payload:
        payload["required_anchor_status_field"] = anchor_status_field
    anchor_status_value = constraint.get("anchor_status_value")
    if anchor_status_value and "required_anchor_status_value" not in payload:
        payload["required_anchor_status_value"] = anchor_status_value
    return payload


def build_change_across_anchor(
    context: SearchContext,
    entry: CatalogEntry,
    required_fields: set[str],
    *,
    depth: int,
    input_context: dict[str, Any],
) -> BuildResult:
    rules = ["generic_before_after_change", "typed_value_field_provider_discovery"]
    attempts: list[dict[str, Any]] = []
    for candidate in change_composition_candidates(context, entry)[: context.max_branching]:
        try:
            anchor = build_entry(
                context,
                candidate["anchor_entry"],
                set(candidate["anchor_required_fields"]),
                depth=depth + 1,
                input_context={},
            )
            before = build_entry(
                context,
                candidate["evaluator_entry"],
                {candidate["status_field"], candidate["value_field"]},
                depth=depth + 1,
                input_context=evaluator_input_context(
                    anchor=anchor,
                    context={
                        "frame_field": candidate["before_frame_field"],
                        **(
                            {}
                            if candidate.get("carrier_id_field") is None
                            else {"carrier_id_field": candidate["carrier_id_field"]}
                        ),
                    },
                ),
            )
            after = build_entry(
                context,
                candidate["evaluator_entry"],
                {candidate["status_field"], candidate["value_field"]},
                depth=depth + 1,
                input_context=evaluator_input_context(
                    anchor=anchor,
                    context={
                        "frame_field": candidate["after_frame_field"],
                        **(
                            {}
                            if candidate.get("carrier_id_field") is None
                            else {"carrier_id_field": candidate["carrier_id_field"]}
                        ),
                    },
                ),
            )
            node_id = context.node_id(entry.name)
            nodes = [*anchor.nodes, *before.nodes, *after.nodes]
            nodes.append(
                catalog_node(
                    node_id,
                    entry,
                    inputs={
                        "anchors": ref(anchor.terminal_node_id, anchor.terminal_output),
                        "before_evaluations": ref(before.terminal_node_id, before.terminal_output),
                        "after_evaluations": ref(after.terminal_node_id, after.terminal_output),
                    },
                    parameters={
                        "before_value_field": enum(candidate["value_field"]),
                        "after_value_field": enum(candidate["value_field"]),
                        "before_status_field": enum(candidate["status_field"]),
                        "after_status_field": enum(candidate["after_status_field"]),
                        "required_status_value": enum("PASS"),
                        "change_mode": enum(candidate["change_mode"]),
                        "minimum_change_m": number(float(candidate["minimum_change_m"]), "metre"),
                        "maximum_before_value_m": number(float(candidate["maximum_before_value_m"]), "metre"),
                    },
                )
            )
            field_sources = {**anchor.field_sources, **before.field_sources, **after.field_sources}
            for field in context.catalog.field_set(entry):
                field_sources.setdefault(field, (node_id, output_name_for_field(context.catalog, entry, field) or "anchor_evaluations"))
            return BuildResult(
                nodes=dedupe_nodes(nodes),
                terminal_node_id=node_id,
                terminal_entry=entry.name,
                terminal_output="anchor_evaluations",
                field_sources=field_sources,
                rules_used=[*anchor.rules_used, *before.rules_used, *after.rules_used, *rules],
                providers_used=[*anchor.providers_used, *before.providers_used, *after.providers_used, entry.name],
            )
        except SynthesisError as error:
            attempts.append(
                {
                    "anchor_provider": candidate["anchor_entry"].name,
                    "evaluator_provider": candidate["evaluator_entry"].name,
                    "value_field": candidate["value_field"],
                    "taxonomy": error.taxonomy,
                    "message": error.message,
                    **error.details,
                }
            )
    raise SynthesisError(
        "missing_constraint",
        "No typed before/after evaluator composition satisfied change_across_anchor.",
        {"attempted": attempts[: context.max_branching], "required_fields": sorted(required_fields)},
    )


def build_join_episode_sets(
    context: SearchContext,
    entry: CatalogEntry,
    required_fields: set[str],
    *,
    depth: int,
) -> BuildResult:
    rules = ["generic_binary_episode_join", "typed_join_key_discovery"]
    if target_constraints(context, "same_player_return"):
        rules.append("generic_same_entity_join")
    attempts: list[dict[str, Any]] = []
    for candidate in join_composition_candidates(context, entry, required_fields)[: context.max_branching]:
        try:
            left = build_entry(context, candidate["left_entry"], set(candidate["left_fields"]), depth=depth + 1, input_context={})
            right = build_entry(context, candidate["right_entry"], set(candidate["right_fields"]), depth=depth + 1, input_context={})
            node_id = context.node_id(entry.name)
            nodes = [*left.nodes, *right.nodes]
            nodes.append(
                catalog_node(
                    node_id,
                    entry,
                    inputs={
                        "left_episodes": ref(left.terminal_node_id, left.terminal_output),
                        "right_episodes": ref(right.terminal_node_id, right.terminal_output),
                    },
                    parameters={
                        "left_key_field": enum(candidate["left_key_field"]),
                        "right_key_field": enum(candidate["right_key_field"]),
                        "left_status_field": enum(candidate["left_status_field"]),
                        "right_status_field": enum(candidate["right_status_field"]),
                        "required_status_value": enum("PASS"),
                        "temporal_relation": enum(candidate["temporal_relation"]),
                        "left_time_field": enum(candidate["left_time_field"]),
                        "right_time_field": enum(candidate["right_time_field"]),
                        "maximum_gap_seconds": number(float(candidate["maximum_gap_seconds"]), "second"),
                        "distinct_entity_fields": enum(candidate["distinct_entity_fields"]),
                        "same_entity_fields": enum(candidate["same_entity_fields"]),
                    },
                )
            )
            field_sources = {**left.field_sources, **right.field_sources}
            for field in context.catalog.field_set(entry):
                field_sources.setdefault(field, (node_id, output_name_for_field(context.catalog, entry, field) or "anchor_evaluations"))
            return BuildResult(
                nodes=dedupe_nodes(nodes),
                terminal_node_id=node_id,
                terminal_entry=entry.name,
                terminal_output="anchor_evaluations",
                field_sources=field_sources,
                rules_used=[*left.rules_used, *right.rules_used, *rules],
                providers_used=[*left.providers_used, *right.providers_used, entry.name],
            )
        except SynthesisError as error:
            attempts.append(
                {
                    "left_provider": candidate["left_entry"].name,
                    "right_provider": candidate["right_entry"].name,
                    "left_key_field": candidate["left_key_field"],
                    "right_key_field": candidate["right_key_field"],
                    "taxonomy": error.taxonomy,
                    "message": error.message,
                    **error.details,
                }
            )
    raise SynthesisError(
        "missing_constraint",
        "No typed binary episode join satisfied the requested evidence fields.",
        {"attempted": attempts[: context.max_branching], "required_fields": sorted(required_fields)},
    )


def prebuilt_input(input_context: dict[str, Any], input_name: str) -> BuildResult | None:
    value = input_context.get(input_name)
    if value is None and input_name == "anchors":
        value = input_context.get("anchors")
    return value if isinstance(value, BuildResult) else None


def evaluator_input_context(
    *,
    anchor: BuildResult,
    context: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {"anchors": anchor}
    payload.update(context)
    return payload


def child_input_context(consumer: CatalogEntry, input_def: CatalogInput) -> dict[str, Any]:
    if consumer.name == "controlled_line_break_episode":
        if input_def.name == "line_evaluations":
            return {"anchor_frame_field": "physical_release_frame_id"}
        if input_def.name == "release_relative_positions":
            return {"entity_frame_field": "physical_release_frame_id"}
        if input_def.name == "reception_relative_positions":
            return {"entity_frame_field": "controlled_reception_frame_id"}
    return {}


def target_constraints(context: SearchContext, kind: str | None = None) -> list[dict[str, Any]]:
    constraints = [
        item
        for item in context.target_contract.get("composition_constraints", [])
        if isinstance(item, dict)
    ]
    if kind is None:
        return constraints
    return [item for item in constraints if item.get("kind") == kind]


def first_target_constraint(context: SearchContext, kind: str) -> dict[str, Any]:
    constraints = target_constraints(context, kind)
    return constraints[0] if constraints else {}


def allowed_parameter_values(entry: CatalogEntry, parameter_name: str) -> list[str]:
    for parameter in entry.parameters:
        if parameter.name != parameter_name:
            continue
        values = []
        for allowed in parameter.allowed_values or []:
            value = getattr(allowed, "value", allowed)
            values.append(str(value))
        if values:
            return values
        if parameter.default is not None:
            return [str(getattr(parameter.default.value, "value", parameter.default.value))]
    return []


def validate_input_context_for_evaluator(
    evaluator: CatalogEntry,
    input_context: dict[str, Any],
    *,
    anchor_fields: set[str],
) -> dict[str, Any] | None:
    declared = {parameter.name: parameter for parameter in evaluator.parameters}
    unapplied = sorted(key for key in input_context if key not in declared)
    if unapplied:
        return {
            "evaluator_provider": evaluator.name,
            "unapplied_input_context_keys": unapplied,
            "declared_parameter_names": sorted(declared),
        }
    for key, value in input_context.items():
        string_value = str(value)
        parameter = declared[key]
        allowed = []
        for allowed_value in parameter.allowed_values or []:
            value_text = getattr(allowed_value, "value", allowed_value)
            allowed.append(str(value_text))
        if allowed and string_value not in allowed:
            return {
                "evaluator_provider": evaluator.name,
                "input_context_key": key,
                "input_context_value": string_value,
                "allowed_values": allowed,
            }
        if key in {"frame_field", "anchor_frame_field", "carrier_id_field", "entity_id_field", "target_entity_field"}:
            if string_value not in anchor_fields:
                return {
                    "evaluator_provider": evaluator.name,
                    "input_context_key": key,
                    "input_context_value": string_value,
                    "anchor_fields": sorted(anchor_fields),
                }
    return None


def declared_parameter_context(entry: CatalogEntry, input_context: dict[str, Any]) -> dict[str, Any]:
    declared = {parameter.name for parameter in entry.parameters}
    payload = {key: value for key, value in input_context.items() if key in declared}
    unapplied = sorted(
        key
        for key, value in input_context.items()
        if key not in declared and not isinstance(value, BuildResult)
    )
    if unapplied:
        raise SynthesisError(
            "missing_constraint",
            "Input context supplied keys that are not declared parameters for the provider.",
            {
                "provider": entry.name,
                "unapplied_input_context_keys": unapplied,
                "declared_parameter_names": sorted(declared),
            },
        )
    return payload


def context_enum_value(context: dict[str, Any], name: str, default: str) -> str:
    return str(context.get(name, default))


def context_number_value(context: dict[str, Any], name: str, default: float) -> float:
    return float(context.get(name, default))


def constrained_value_fields(context: SearchContext, entry: CatalogEntry) -> list[str]:
    allowed = allowed_parameter_values(entry, "before_value_field")
    fields: list[str] = []
    for constraint in target_constraints(context, "before_after_same_anchor"):
        for field_name in constraint.get("value_fields", []):
            if str(field_name) in allowed and str(field_name) not in fields:
                fields.append(str(field_name))
        family = constraint.get("value_family")
        for field_name in VALUE_FAMILY_FIELDS.get(str(family), []):
            if field_name in allowed and field_name not in fields:
                fields.append(field_name)
    return fields or allowed


def constrained_status_fields(context: SearchContext, entry: CatalogEntry) -> list[str]:
    allowed = allowed_parameter_values(entry, "before_status_field")
    fields: list[str] = []
    for constraint in target_constraints(context, "before_after_same_anchor"):
        for field_name in constraint.get("status_fields", []):
            if str(field_name) in allowed and str(field_name) not in fields:
                fields.append(str(field_name))
    return fields or allowed


def change_parameter_constraint(context: SearchContext, name: str, default: Any) -> Any:
    for constraint in target_constraints(context, "before_after_same_anchor"):
        if name in constraint:
            return constraint[name]
    return default


def change_composition_candidates(
    context: SearchContext,
    change_entry: CatalogEntry,
) -> list[dict[str, Any]]:
    value_fields = constrained_value_fields(context, change_entry)
    status_fields = constrained_status_fields(context, change_entry)
    before_frame_override = change_parameter_constraint(context, "before_frame_field", None)
    after_frame_override = change_parameter_constraint(context, "after_frame_field", None)
    frame_constraint = first_target_constraint(context, "frame_alignment")
    before_frame_override = before_frame_override or frame_constraint.get("before_frame_field")
    after_frame_override = after_frame_override or frame_constraint.get("after_frame_field")
    change_mode = str(change_parameter_constraint(context, "change_mode", "increase_at_least"))
    minimum_change_m = float(change_parameter_constraint(context, "minimum_change_m", 4.0))
    maximum_before_value_m = float(change_parameter_constraint(context, "maximum_before_value_m", 12.0))
    after_status_override = change_parameter_constraint(context, "after_status_field", None)

    candidates: list[tuple[int, str, str, str, dict[str, Any]]] = []
    for evaluator in context.catalog.entries.values():
        if evaluator.name == change_entry.name or not has_single_anchor_input(evaluator):
            continue
        evaluator_fields = context.catalog.field_set(evaluator)
        matched_values = [field for field in value_fields if field in evaluator_fields]
        matched_status = [field for field in status_fields if field in evaluator_fields]
        if not matched_values or not matched_status:
            continue
        input_def = evaluator.inputs[0]
        for anchor_entry, _ in context.catalog.compatible_outputs(input_def):
            if anchor_entry.name == evaluator.name:
                continue
            before_frame, after_frame = frame_pair_for_anchor(
                anchor_entry,
                evaluator,
                before_override=None if before_frame_override is None else str(before_frame_override),
                after_override=None if after_frame_override is None else str(after_frame_override),
            )
            if before_frame is None or after_frame is None:
                continue
            carrier_id_field = entity_field_for_evaluator(evaluator, anchor_entry)
            if evaluator.name == "pressure_on_carrier" and carrier_id_field is None:
                continue
            anchor_required_fields = {before_frame, after_frame}
            if carrier_id_field is not None:
                anchor_required_fields.add(carrier_id_field)
            anchor_fields = context.catalog.field_set(anchor_entry)
            if not runtime_or_catalog_field_compatible(anchor_fields, anchor_required_fields):
                continue
            after_status_field = str(after_status_override or matched_status[0])
            if after_status_field not in allowed_parameter_values(change_entry, "after_status_field"):
                continue
            score = 0
            score += 20 * len(set(matched_values) & required_target_fields(context.target_contract))
            score += 8 if before_frame != after_frame else 0
            candidate = {
                "anchor_entry": anchor_entry,
                "evaluator_entry": evaluator,
                "anchor_required_fields": sorted(anchor_required_fields),
                "value_field": matched_values[0],
                "status_field": matched_status[0],
                "after_status_field": after_status_field,
                "before_frame_field": before_frame,
                "after_frame_field": after_frame,
                "carrier_id_field": carrier_id_field,
                "change_mode": change_mode,
                "minimum_change_m": minimum_change_m,
                "maximum_before_value_m": maximum_before_value_m,
            }
            candidates.append((-score, anchor_entry.name, evaluator.name, matched_values[0], candidate))
    return [candidate for *_prefix, candidate in sorted(candidates)]


def has_single_anchor_input(entry: CatalogEntry) -> bool:
    return len(entry.inputs) == 1 and entry.inputs[0].name == "anchors"


def frame_pair_for_anchor(
    anchor_entry: CatalogEntry,
    evaluator: CatalogEntry,
    *,
    before_override: str | None,
    after_override: str | None,
) -> tuple[str | None, str | None]:
    allowed_frames = set(allowed_parameter_values(evaluator, "frame_field") or allowed_parameter_values(evaluator, "anchor_frame_field"))
    anchor_fields = contextless_field_names(anchor_entry)
    pairs = []
    if before_override and after_override:
        pairs.append((before_override, after_override))
    pairs.extend(
        [
            ("carry_start_frame_id", "carry_end_frame_id"),
            ("physical_release_frame_id", "controlled_reception_frame_id"),
            ("start_frame_id", "end_frame_id"),
            ("anchor_frame_id", "anchor_frame_id"),
        ]
    )
    for before, after in pairs:
        if before in allowed_frames and after in allowed_frames and before in anchor_fields and after in anchor_fields:
            return before, after
    return None, None


def contextless_field_names(entry: CatalogEntry) -> set[str]:
    fields = set(entry.evidence_fields)
    for output in entry.outputs:
        fields.add(output.name)
        fields.update(output.evidence_fields)
    return fields


def runtime_or_catalog_field_compatible(fields: set[str], required: set[str]) -> bool:
    return required.issubset(fields)


def entity_field_for_evaluator(evaluator: CatalogEntry, anchor_entry: CatalogEntry) -> str | None:
    allowed = allowed_parameter_values(evaluator, "carrier_id_field")
    if not allowed:
        return None
    anchor_fields = contextless_field_names(anchor_entry)
    for field_name in ("carrier_id", "receiver_id", "relay_player_id", "terminal_receiver_id", "passer_id"):
        if field_name in allowed and field_name in anchor_fields:
            return field_name
    return None


def join_composition_candidates(
    context: SearchContext,
    join_entry: CatalogEntry,
    required_fields: set[str],
) -> list[dict[str, Any]]:
    left_key_hint = first_target_constraint(context, "same_anchor_identity").get("left_key_field")
    right_key_hint = first_target_constraint(context, "same_anchor_identity").get("right_key_field")
    left_key_allowed = allowed_parameter_values(join_entry, "left_key_field")
    right_key_allowed = allowed_parameter_values(join_entry, "right_key_field")
    candidate_entries = [
        entry
        for entry in context.catalog.entries.values()
        if entry.name != join_entry.name and context.catalog.field_set(entry) & required_fields
    ]
    candidates: list[tuple[int, str, str, dict[str, Any]]] = []
    for left_entry in candidate_entries:
        for right_entry in candidate_entries:
            if left_entry.name == right_entry.name:
                continue
            left_fields_all = context.catalog.field_set(left_entry)
            right_fields_all = context.catalog.field_set(right_entry)
            left_fields = left_fields_all & required_fields
            right_fields = right_fields_all & required_fields
            if not left_fields or not right_fields:
                continue
            if not (required_fields - context.catalog.field_set(join_entry)).issubset(left_fields_all | right_fields_all):
                continue
            key_pair = compatible_join_key_pair(
                left_fields_all,
                right_fields_all,
                left_key_allowed,
                right_key_allowed,
                left_hint=None if left_key_hint is None else str(left_key_hint),
                right_hint=None if right_key_hint is None else str(right_key_hint),
            )
            if key_pair is None:
                continue
            left_status = status_field_for(left_entry) or "none"
            right_status = status_field_for(right_entry) or "none"
            if left_status not in allowed_parameter_values(join_entry, "left_status_field"):
                left_status = "none"
            if right_status not in allowed_parameter_values(join_entry, "right_status_field"):
                right_status = "none"
            temporal = temporal_join_constraint(context, left_fields_all, right_fields_all, join_entry)
            distinct_fields = distinct_entity_constraint(context, left_fields_all | right_fields_all, join_entry)
            same_entity_fields = same_entity_constraint(context, left_fields_all, right_fields_all, join_entry)
            if target_constraints(context, "same_player_return") and same_entity_fields == "none":
                continue
            score = 0
            score += 20 * len(left_fields | right_fields)
            score += 10 * len(left_fields)
            score += 10 * len(right_fields)
            score += 5 if left_status != "none" and right_status != "none" else 0
            score += 3 if key_pair == ("anchor_id", "anchor_id") else 0
            score += 6 if same_entity_fields != "none" else 0
            candidate = {
                "left_entry": left_entry,
                "right_entry": right_entry,
                "left_fields": sorted(
                    required_fields_for_join_side(
                        left_entry,
                        left_fields | same_entity_left_fields(same_entity_fields),
                        left_status,
                        key_pair[0],
                    )
                ),
                "right_fields": sorted(
                    required_fields_for_join_side(
                        right_entry,
                        right_fields | same_entity_right_fields(same_entity_fields),
                        right_status,
                        key_pair[1],
                    )
                ),
                "left_key_field": key_pair[0],
                "right_key_field": key_pair[1],
                "left_status_field": left_status,
                "right_status_field": right_status,
                "temporal_relation": temporal["temporal_relation"],
                "left_time_field": temporal["left_time_field"],
                "right_time_field": temporal["right_time_field"],
                "maximum_gap_seconds": temporal["maximum_gap_seconds"],
                "distinct_entity_fields": distinct_fields,
                "same_entity_fields": same_entity_fields,
            }
            candidates.append((-score, left_entry.name, right_entry.name, candidate))
    return [candidate for *_prefix, candidate in sorted(candidates)]


def compatible_join_key_pair(
    left_fields: set[str],
    right_fields: set[str],
    left_allowed: list[str],
    right_allowed: list[str],
    *,
    left_hint: str | None,
    right_hint: str | None,
) -> tuple[str, str] | None:
    hinted = (left_hint, right_hint)
    if left_hint and right_hint and left_hint in left_allowed and right_hint in right_allowed and left_hint in left_fields and right_hint in right_fields:
        return hinted  # type: ignore[return-value]
    for left_key, right_key in [
        ("anchor_id", "anchor_id"),
        ("terminal_pass_id", "input_pass_episode_id"),
        ("right_anchor_id", "anchor_id"),
        ("input_pass_episode_id", "input_pass_episode_id"),
        ("relay_pass_episode_id", "relay_pass_episode_id"),
    ]:
        if left_key in left_allowed and right_key in right_allowed and left_key in left_fields and right_key in right_fields:
            return left_key, right_key
    return None


def required_fields_for_join_side(
    entry: CatalogEntry,
    target_side_fields: set[str],
    status_field: str,
    key_field: str,
) -> set[str]:
    fields = set(target_side_fields)
    if status_field != "none":
        fields.add(status_field)
    fields.add(key_field)
    return fields & contextless_field_names(entry)


def temporal_join_constraint(context: SearchContext, left_fields: set[str], right_fields: set[str], join_entry: CatalogEntry) -> dict[str, Any]:
    relation = "none"
    left_time = "anchor_frame_id"
    right_time = "anchor_frame_id"
    maximum_gap = 999.0
    for constraint in target_constraints(context):
        if constraint.get("kind") == "temporal_order":
            relation = str(constraint.get("temporal_relation", relation))
            left_time = str(constraint.get("left_time_field", left_time))
            right_time = str(constraint.get("right_time_field", right_time))
            maximum_gap = float(constraint.get("maximum_gap_seconds", maximum_gap))
    if relation == "left_before_right":
        relation = "left_ends_before_right"
    allowed_relation = allowed_parameter_values(join_entry, "temporal_relation")
    allowed_left_time = allowed_parameter_values(join_entry, "left_time_field")
    allowed_right_time = allowed_parameter_values(join_entry, "right_time_field")
    if relation not in allowed_relation or left_time not in allowed_left_time or right_time not in allowed_right_time:
        relation, left_time, right_time, maximum_gap = "none", "anchor_frame_id", "anchor_frame_id", 999.0
    if relation != "none" and (left_time not in left_fields or right_time not in right_fields):
        relation, left_time, right_time, maximum_gap = "none", "anchor_frame_id", "anchor_frame_id", 999.0
    return {
        "temporal_relation": relation,
        "left_time_field": left_time,
        "right_time_field": right_time,
        "maximum_gap_seconds": maximum_gap,
    }


def distinct_entity_constraint(context: SearchContext, fields: set[str], join_entry: CatalogEntry) -> str:
    allowed = allowed_parameter_values(join_entry, "distinct_entity_fields")
    for constraint in target_constraints(context):
        if constraint.get("kind") != "distinct_entity_fields":
            continue
        value = str(constraint.get("value", "none"))
        required_fields = {field.strip() for field in value.split(",") if field.strip()}
        if value in allowed and required_fields.issubset(fields):
            return value
    return "none"


def same_entity_constraint(
    context: SearchContext,
    left_fields: set[str],
    right_fields: set[str],
    join_entry: CatalogEntry,
) -> str:
    allowed = allowed_parameter_values(join_entry, "same_entity_fields")
    for constraint in target_constraints(context):
        if constraint.get("kind") != "same_player_return":
            continue
        left_field = str(constraint.get("left_field", ""))
        right_field = str(constraint.get("right_field", ""))
        value = f"{left_field}={right_field}"
        if value in allowed and left_field in left_fields and right_field in right_fields:
            return value
    return "none"


def same_entity_left_fields(value: str) -> set[str]:
    if value == "none" or "=" not in value:
        return set()
    return {value.split("=", 1)[0]}


def same_entity_right_fields(value: str) -> set[str]:
    if value == "none" or "=" not in value:
        return set()
    return {value.split("=", 1)[1]}


def choose_input_provider(
    context: SearchContext,
    *,
    consumer: CatalogEntry,
    input_def: CatalogInput,
    depth: int,
) -> tuple[CatalogEntry, CatalogOutput]:
    candidates = context.catalog.compatible_outputs(input_def)
    if not candidates:
        raise SynthesisError(
            "missing_constraint",
            "No compatible provider output for required input.",
            {"consumer": consumer.name, "input": input_def.name},
        )
    dependencies = field_dependencies_for_consumer(consumer)
    input_dependencies = field_dependencies_for_input(consumer, input_def)
    scored: list[tuple[int, int, str, str, CatalogEntry, CatalogOutput]] = []
    for provider, output in candidates:
        if provider.name == consumer.name:
            continue
        fields = set(output.evidence_fields)
        score = 0
        score += 20 * len(input_dependencies & fields)
        score += 10 * len(dependencies & fields)
        if input_def.name in provider.name or provider.name in input_def.name:
            score += 8
        for token in input_def.name.split("_"):
            if token and token in provider.name:
                score += 2
        if not provider.inputs:
            score += 1
        scored.append((-score, len(provider.inputs), provider.name, output.name, provider, output))
    if not scored:
        raise SynthesisError(
            "missing_constraint",
            "Compatible inputs only loop back to the consumer.",
            {"consumer": consumer.name, "input": input_def.name},
        )
    _, _, _, _, provider, output = sorted(scored)[0]
    return provider, output


def field_dependencies_for_input(consumer: CatalogEntry, input_def: CatalogInput) -> set[str]:
    if consumer.name == "controlled_line_break_episode" and input_def.name == "line_evaluations":
        return {"line_x_m", "multi_line_status", "target_line_rank"}
    if consumer.name == "controlled_line_break_episode" and input_def.name == "controlled_pass_anchors":
        return {"anchor_id", "controlled_reception_frame_id", "physical_release_frame_id", "receiver_id"}
    if consumer.name == "controlled_line_break_episode" and input_def.name in {"release_relative_positions", "reception_relative_positions"}:
        return {"relative_position_status", "signed_distance_to_line_m"}
    if consumer.name == "relative_position_to_line" and input_def.name == "line_evaluations":
        return {"line_x_m", "multi_line_status", "target_line_rank"}
    if consumer.name == "relative_position_to_line" and input_def.name == "entity_anchors":
        return {"receiver_id", "controlled_reception_frame_id", "physical_release_frame_id"}
    return set()


def required_fields_for_input(entry: CatalogEntry, input_def: CatalogInput, target_fields: set[str]) -> set[str]:
    if entry.name == "controlled_line_break_episode" and input_def.name == "controlled_pass_anchors":
        return {"anchor_id", "controlled_reception_frame_id", "pass_episode_id", "physical_release_frame_id", "receiver_id"}
    if entry.name == "controlled_line_break_episode" and input_def.name == "line_evaluations":
        return {"anchor_id", "line_x_m", "multi_line_status", "observed_line_count", "target_line_rank"}
    if entry.name == "controlled_line_break_episode" and input_def.name in {"release_relative_positions", "reception_relative_positions"}:
        return {"anchor_id", "relative_position_status", "signed_distance_to_line_m"}
    if entry.name == "carry_episode" and input_def.name == "controlled_pass_anchors":
        return {"controlled_pass_status", "receiver_id", "controlled_reception_frame_id"}
    if entry.name == "off_ball_run_type" and input_def.name == "runs":
        return {
            "candidate_team_role",
            "off_ball_run_status",
            "run_end_frame_id",
            "run_forward_progression_m",
            "run_lateral_displacement_m",
            "run_player_id",
            "run_start_frame_id",
        }
    if entry.name == "space_region_generation" and input_def.name == "anchors":
        return {"anchor_id", "anchor_frame_id"}
    if entry.name == "cover_shadow" and input_def.name == "anchors":
        return {"anchor_id", "anchor_frame_id", "receiver_id", "team_role"}
    if entry.name == "team_press" and input_def.name == "anchors":
        return {"anchor_id", "anchor_frame_id", "receiver_id", "team_role"}
    return field_dependencies_for_consumer(entry) or target_fields


def first_provider(context: SearchContext, fields: set[str]) -> CatalogEntry:
    providers = context.catalog.providers_for_fields(fields)
    if not providers:
        raise SynthesisError("missing_primitive", "No provider covers required field subset.", {"fields": sorted(fields)})
    return providers[0]


def require_entry(context: SearchContext, name: str) -> CatalogEntry:
    try:
        return context.catalog.entries[name]
    except KeyError as exc:
        raise SynthesisError("missing_primitive", f"Required generic provider {name!r} is unavailable.") from exc


def infer_parameters(
    entry: CatalogEntry,
    *,
    input_builds: list[BuildResult],
    input_context: dict[str, Any],
) -> dict[str, Any]:
    if entry.name == "multi_line_model":
        return {
            "anchor_frame_field": enum(str(input_context.get("anchor_frame_field", "physical_release_frame_id"))),
            "goal_side_buffer_m": number(1.0, "metre"),
            "line_band_width_m": number(2.5, "metre"),
            "minimum_line_defenders": number(2.0, "count"),
            "target_line_rank": number(2.0, "count"),
        }
    if entry.name == "controlled_line_break_episode":
        return {
            "line_buffer_m": number(0.5, "metre"),
        }
    if entry.name == "relative_position_to_line":
        return {
            "entity_id_field": enum(str(input_context.get("entity_id_field", "receiver_id"))),
            "entity_frame_field": enum(str(input_context.get("entity_frame_field", "controlled_reception_frame_id"))),
            "line_buffer_m": number(0.5, "metre"),
        }
    if entry.name == "support_arrival_relation":
        return support_arrival_parameters(entry, input_context=input_context)
    if entry.name == "support_arrival_point_pair":
        return support_arrival_parameters(entry, input_context=input_context)
    if entry.name == "pressure_on_carrier":
        context = declared_parameter_context(entry, input_context)
        return {
            "frame_field": enum(context_enum_value(context, "frame_field", "controlled_reception_frame_id")),
            "carrier_id_field": enum(context_enum_value(context, "carrier_id_field", "receiver_id")),
            "maximum_pressure_distance_m": number(context_number_value(context, "maximum_pressure_distance_m", 4.0), "metre"),
            "minimum_closing_speed_mps": number(context_number_value(context, "minimum_closing_speed_mps", 0.2), "none"),
            "maximum_approach_angle_degrees": number(context_number_value(context, "maximum_approach_angle_degrees", 100.0), "none"),
            "minimum_pressure_duration_seconds": number(context_number_value(context, "minimum_pressure_duration_seconds", 0.0), "second"),
            "lookback_seconds": number(context_number_value(context, "lookback_seconds", 0.4), "second"),
            "candidate_scope": enum(context_enum_value(context, "candidate_scope", "defending_outfield")),
        }
    if entry.name == "defender_distance_candidate_set":
        context = declared_parameter_context(entry, input_context)
        return {
            "anchor_frame_field": enum(context_enum_value(context, "anchor_frame_field", "controlled_reception_frame_id")),
            "target_player_id_field": enum(context_enum_value(context, "target_player_id_field", "receiver_id")),
            "candidate_scope": enum(context_enum_value(context, "candidate_scope", "defending_outfield")),
            "required_anchor_status_field": enum(context_enum_value(context, "required_anchor_status_field", "none")),
            "required_anchor_status_value": enum(context_enum_value(context, "required_anchor_status_value", "PASS")),
            "minimum_observed_candidates": number(context_number_value(context, "minimum_observed_candidates", 6.0), "count"),
        }
    if entry.name == "team_compactness":
        return {
            "frame_field": enum(str(input_context.get("frame_field", "anchor_frame_id"))),
            "player_scope": enum("defending_outfield"),
            "maximum_team_width_m": number(45.0, "metre"),
            "maximum_team_depth_m": number(35.0, "metre"),
            "minimum_observed_players": number(8.0, "count"),
        }
    if entry.name == "transition_anchor":
        return {
            "transition_type": enum("regain"),
            "minimum_prior_possession_seconds": number(0.4, "second"),
            "zone_filter": enum("any"),
            "zone_boundary_buffer_m": number(0.5, "metre"),
        }
    if entry.name == "outcome_window":
        return {
            "maximum_window_seconds": number(8.0, "second"),
            "minimum_settled_possession_seconds": number(4.0, "second"),
            "required_anchor_status_field": enum("transition_status"),
            "required_anchor_status_value": enum("PASS"),
        }
    if entry.name == "space_region_generation":
        return {
            "frame_field": enum("anchor_frame_id"),
            "zone_scope": enum("any"),
            "grid_step_m": number(8.0, "metre"),
            "minimum_opponent_distance_m": number(8.0, "metre"),
            "minimum_teammate_distance_m": number(4.0, "metre"),
            "minimum_open_points": number(1.0, "count"),
            "maximum_candidate_points": number(5.0, "count"),
            "minimum_observed_players_per_team": number(6.0, "count"),
        }
    if entry.name == "cover_shadow":
        return {
            "frame_field": enum("anchor_frame_id"),
            "target_entity_field": enum("receiver_id"),
            "candidate_scope": enum("opposition_outfield_to_anchor_team"),
            "maximum_lane_distance_m": number(2.0, "metre"),
            "minimum_projection_fraction": number(0.05, "fraction"),
            "minimum_lane_length_m": number(5.0, "metre"),
            "minimum_observed_defenders": number(6.0, "count"),
        }
    if entry.name == "team_press":
        return {
            "frame_field": enum("anchor_frame_id"),
            "carrier_id_field": enum("receiver_id"),
            "candidate_scope": enum("defending_outfield"),
            "maximum_press_distance_m": number(7.0, "metre"),
            "minimum_closing_speed_mps": number(0.0, "none"),
            "maximum_approach_angle_degrees": number(135.0, "none"),
            "minimum_pressing_defenders": number(2.0, "count"),
            "minimum_angle_spread_degrees": number(30.0, "none"),
            "minimum_observed_defenders": number(6.0, "count"),
            "lookback_seconds": number(0.4, "second"),
        }
    return {}


SUPPORT_ARRIVAL_PARAMETER_DEFAULTS: dict[str, tuple[str, object, str]] = {
    "anchor_frame_field": ("enum", "controlled_reception_frame_id", "none"),
    "candidate_scope": ("enum", "perspective_outfield", "none"),
    "support_region_mode": ("enum", "WITHIN_DISTANCE_OF_REFERENCE_POINT", "none"),
    "maximum_arrival_seconds": ("number", 3.0, "second"),
    "minimum_duration_seconds": ("number", 0.0, "second"),
    "maximum_support_distance_m": ("number", 8.0, "metre"),
    "minimum_supporting_players": ("number", 1.0, "count"),
    "required_anchor_status_field": ("enum", "none", "none"),
    "required_anchor_status_value": ("enum", "PASS", "none"),
}


def support_arrival_parameters(entry: CatalogEntry, *, input_context: dict[str, Any]) -> dict[str, Any]:
    declared_names = {parameter.name for parameter in entry.parameters}
    unapplied = sorted(key for key in input_context if key not in declared_names)
    if unapplied:
        raise SynthesisError(
            "missing_constraint",
            "relation_on_anchor supplied keys that are not declared parameters for the relation.",
            {
                "relation_provider": entry.name,
                "unapplied_relation_constraint_keys": unapplied,
                "declared_parameter_names": sorted(declared_names),
            },
        )
    unhandled = sorted(key for key in input_context if key not in SUPPORT_ARRIVAL_PARAMETER_DEFAULTS)
    if unhandled:
        raise SynthesisError(
            "missing_constraint",
            "relation_on_anchor supplied keys without synthesis support.",
            {
                "relation_provider": entry.name,
                "unhandled_relation_constraint_keys": unhandled,
            },
        )

    params: dict[str, Any] = {}
    for key, (payload_type, default_value, unit) in SUPPORT_ARRIVAL_PARAMETER_DEFAULTS.items():
        if key not in declared_names:
            continue
        value = input_context.get(key, default_value)
        if payload_type == "enum":
            params[key] = enum(str(value))
        else:
            params[key] = number(float(value), unit)
    return params


def field_dependencies_for_consumer(entry: CatalogEntry) -> set[str]:
    if entry.name == "off_ball_run_type":
        return {
            "candidate_team_role",
            "off_ball_run_status",
            "run_end_frame_id",
            "run_forward_progression_m",
            "run_lateral_displacement_m",
            "run_player_id",
            "run_start_frame_id",
        }
    if entry.name == "space_region_generation":
        return {"anchor_id", "anchor_frame_id"}
    if entry.name == "cover_shadow":
        return {"anchor_id", "anchor_frame_id", "receiver_id", "team_role"}
    if entry.name == "team_press":
        return {"anchor_id", "anchor_frame_id", "receiver_id", "team_role"}
    dependencies: set[str] = set()
    for parameter in entry.parameters:
        if "_field" not in parameter.name:
            continue
        if parameter.default is None:
            continue
        value = str(parameter.default.value)
        if value != "none":
            dependencies.add(value)
    return dependencies


def output_matches_input(output: CatalogOutput, input_def: CatalogInput) -> bool:
    return (
        output.temporal_type == input_def.temporal_type
        and output.payload_type == input_def.payload_type
        and output.cardinality == input_def.cardinality
        and (input_def.entity_scope.value in {"none", output.entity_scope.value} or output.entity_scope.value == "anchor")
    )


def required_target_fields(contract: dict[str, Any]) -> set[str]:
    fields = set(contract.get("required_evidence", []))
    for item in contract.get("status_semantics", []):
        if field := item.get("field"):
            fields.add(str(field))
    return fields


def unsupported_composition_constraints(contract: dict[str, Any]) -> list[dict[str, Any]]:
    unsupported: list[dict[str, Any]] = []
    constraints = contract.get("composition_constraints", [])
    if not isinstance(constraints, list):
        return [{"kind": "<invalid>", "reason": "composition_constraints must be a list"}]
    for index, constraint in enumerate(constraints):
        if not isinstance(constraint, dict):
            unsupported.append({"index": index, "kind": "<invalid>", "reason": "constraint must be an object"})
            continue
        kind = str(constraint.get("kind", ""))
        if kind not in SUPPORTED_COMPOSITION_CONSTRAINT_KINDS:
            unsupported.append({"index": index, "kind": kind or "<missing>"})
    return unsupported


def assemble_document(
    *,
    target: dict[str, Any],
    build: BuildResult,
    perspective_team_role: str | None = None,
) -> dict[str, Any]:
    contract = target["target_contract"]
    predicates = predicates_for_contract(contract, build.field_sources)
    terminal_evidence_fields = terminal_output_fields(build)
    requested_evidence = [
        {
            "source": {
                "source_node_id": build.terminal_node_id if field in terminal_evidence_fields else build.field_sources[field][0],
                "output_name": build.terminal_output if field in terminal_evidence_fields else build.field_sources[field][1],
            },
            "field": field,
            "alias": field,
            "required": True,
        }
        for field in contract.get("required_evidence", [])
        if field in build.field_sources
    ]
    return document(
        target_id=target["target_id"],
        display_name=f"Search Synthesized {target['target_id'].replace('_', ' ').title()}",
        description="Generated by bounded backward search from typed evidence and predicate requirements.",
        nodes=[*build.nodes, *predicates],
        predicate_ids=[predicate["node_id"] for predicate in predicates],
        anchor_source=ref(build.terminal_node_id, build.terminal_output),
        requested_evidence=requested_evidence,
        claim_boundary=contract["claim_boundary"],
        perspective_team_role=perspective_team_role or PERSPECTIVE_TEAM_ROLES[0],
    )


def terminal_output_fields(build: BuildResult) -> set[str]:
    if build.terminal_entry == "operator:typed_join":
        if "typed_join_output_fields" in build.metadata:
            return set(str(field) for field in build.metadata["typed_join_output_fields"])
        return set(TYPED_JOIN_FIELDS)
    if build.terminal_entry == "operator:window":
        return set(WINDOW_FIELDS)
    if build.terminal_entry == "operator:extremum_over_set":
        return set(EXTREMUM_OVER_SET_FIELDS)
    if build.terminal_entry == "operator:delta_across_anchor":
        return set(DELTA_ACROSS_ANCHOR_FIELDS)
    if build.terminal_entry == "operator:project_onto_axis":
        return set(PROJECT_ONTO_AXIS_FIELDS)
    return set()


def predicates_for_contract(contract: dict[str, Any], field_sources: dict[str, tuple[str, str]]) -> list[dict[str, Any]]:
    predicates: list[dict[str, Any]] = []
    for index, item in enumerate(contract.get("status_semantics", []), start=1):
        field = str(item["field"])
        if field not in field_sources:
            continue
        source_node_id, output_name = field_sources[field]
        operator = item.get("operator")
        if "required_value" in item:
            predicates.append(predicate_eq(f"predicate_{index}", source_node_id, output_name, str(item["required_value"])))
        elif operator == "gte":
            predicates.append(
                predicate_gte(
                    f"predicate_{index}",
                    source_node_id,
                    output_name,
                    float(item["threshold"]),
                    str(item.get("unit", "none")),
                )
            )
    if not predicates:
        raise SynthesisError("missing_constraint", "No predicates could be assembled from target semantics.")
    return predicates


def output_name_for_field(catalog: CatalogIndex, entry: CatalogEntry, field: str) -> str | None:
    output = catalog.output_for_field(entry, field)
    return output.name if output is not None else None


def status_field_for(entry: CatalogEntry) -> str | None:
    for output in entry.outputs:
        if output.name.endswith("_status"):
            return output.name
    for field_name in entry.evidence_fields:
        if field_name.endswith("_status"):
            return field_name
    return None


def dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for node in nodes:
        node_id = str(node["node_id"])
        if node_id in seen:
            continue
        seen.add(node_id)
        deduped.append(node)
    return deduped


def row_result(
    *,
    target: dict[str, Any],
    row: dict[str, Any],
    result: str,
    failure_taxonomy: str | None,
    message: str,
    target_contract_hash: str,
    failure_details: dict[str, Any] | None = None,
    document_payload: dict[str, Any] | None = None,
    build: dict[str, Any] | None = None,
    execution: Any = None,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = rows or []
    evidence_failures = (
        None
        if execution is None
        else int(execution.provenance.get("requested_evidence_failure_count") or 0)
    )
    return {
        "target_id": target["target_id"],
        "concept": target["concept"],
        "held_out": bool(target.get("held_out")),
        "multi_step": bool(target.get("multi_step")),
        "coverage_classification": row.get("classification"),
        "input_composition_maturity": row.get("composition_maturity", "handwired"),
        "target_contract_hash": target_contract_hash,
        "semantic_correspondence": target.get("semantic_correspondence"),
        "concept_name_used_as_hint": concept_name_used_as_hint(target),
        "provider_name_used_as_hint": provider_name_used_as_hint(target),
        "gold_chain_used_as_input": False,
        "pattern_dispatch_used": False,
        "synthesizer_version": SYNTHESIZER_VERSION,
        "synthesizer_strategy": SYNTHESIZER_STRATEGY,
        "search_budget_label": SEARCH_BUDGET_LABEL,
        "result": result,
        "failure_taxonomy": failure_taxonomy,
        "failure_details": failure_details or {},
        "message": message,
        "plan_path": None if document_payload is None else relative_path(PLAN_DIR / f"{target['target_id']}.json"),
        "document_hash": None if document_payload is None else stable_hash(document_payload),
        "execution_status": None if execution is None else execution.status.value,
        "compatibility_profile": None if execution is None else execution.provenance.get("compatibility_profile"),
        "result_count": len(rows),
        "honest_zero": execution is not None and execution.status == ExecutionStatus.PASS and len(rows) == 0 and evidence_failures == 0,
        "requested_evidence_failure_count": evidence_failures,
        "runtime_trace_hash": None if execution is None else execution.provenance.get("runtime_trace_hash"),
        "runtime_value_count": None if execution is None else execution.provenance.get("runtime_value_count"),
        "execution_node_cache": None if execution is None else execution.provenance.get("node_cache"),
        "providers_used": [] if build is None else build.get("providers_used", []),
        "terminal_provider": None if build is None else build.get("terminal_provider"),
        "rules_used": [] if build is None else build.get("rules_used", []),
        "field_sources": {} if build is None else build.get("field_sources", {}),
        "build_metadata": {} if build is None else build.get("build_metadata", {}),
        "coverage_gold_chain_audit": gold_chain_audit(row),
    }


def classify_failure(taxonomy: str, row: dict[str, Any]) -> str:
    if taxonomy == "missing_primitive" and row.get("classification") == "supported":
        return "answer_key_error"
    return taxonomy


def update_coverage_rows(rows: list[dict[str, Any]], results: list[dict[str, Any]]) -> None:
    by_concept = {result["concept"]: result for result in results}
    for row in rows:
        result = by_concept.get(row.get("concept"))
        if result is None or result["result"] != "compiler_reachable":
            continue
        semantic_correspondence = validated_semantic_correspondence(row=row, result=result)
        if not result.get("plan_path") or not result.get("document_hash"):
            raise ValueError(
                "compiler_reachable result is missing certified plan reference; "
                f"concept={result.get('concept')} target_id={result.get('target_id')}"
            )
        row["composition_maturity"] = "compiler_reachable"
        row["composition_maturity_applicable"] = row.get("classification") == "supported"
        row["compiler_reachability_status"] = "compiler_reachable"
        row["compiler_reachability_evidence"] = {
            "synthesizer_version": SYNTHESIZER_VERSION,
            "synthesizer_strategy": SYNTHESIZER_STRATEGY,
            "target_id": result["target_id"],
            "report_path": relative_path(REPORT),
            "plan_path": result["plan_path"],
            "document_hash": result["document_hash"],
            "held_out": result["held_out"],
            "result_count": result["result_count"],
            "honest_zero": result["honest_zero"],
            "semantic_correspondence": semantic_correspondence,
        }


def validated_semantic_correspondence(*, row: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    declaration = result.get("semantic_correspondence")
    if not isinstance(declaration, dict):
        raise ValueError(
            "compiler_reachable result has non-conforming semantic_correspondence declaration; "
            f"concept={result.get('concept')} target_id={result.get('target_id')}"
        )
    missing = sorted(key for key in ("coverage_row", "meaning") if not declaration.get(key))
    if missing:
        raise ValueError(
            "compiler_reachable result semantic_correspondence declaration is missing required keys; "
            f"missing={missing} concept={result.get('concept')} target_id={result.get('target_id')}"
        )
    row_concept = str(row.get("concept") or "")
    if str(declaration["coverage_row"]) != row_concept:
        raise ValueError(
            "compiler_reachable result semantic_correspondence coverage_row does not match coverage row; "
            f"coverage_row={declaration['coverage_row']} row_concept={row_concept} "
            f"target_id={result.get('target_id')}"
        )
    return declaration


def build_report(
    *,
    targets_payload: dict[str, Any],
    coverage_rows: list[dict[str, Any]],
    results: list[dict[str, Any]],
    cache_backend_summary: dict[str, Any],
) -> dict[str, Any]:
    sample_policy = targets_payload.get("sample_policy", "bounded_stratified_sample_with_held_out_targets")
    requires_held_out_acceptance = sample_policy == "bounded_stratified_sample_with_held_out_targets"
    total = len(coverage_rows)
    supported = sum(1 for row in coverage_rows if row.get("classification") == "supported")
    compiler_reachable = sum(1 for row in coverage_rows if row.get("composition_maturity") == "compiler_reachable")
    result_counts = collections.Counter(result["result"] for result in results)
    failure_counts = collections.Counter(result["failure_taxonomy"] for result in results if result.get("failure_taxonomy"))
    cache_summary = search_node_cache_summary(results)
    held_out = [result for result in results if result.get("held_out")]
    held_out_success = [result for result in held_out if result["result"] == "compiler_reachable"]
    multi_step = [result for result in results if result.get("multi_step")]
    multi_step_success = [result for result in multi_step if result["result"] == "compiler_reachable"]
    held_out_multi_step = [result for result in multi_step if result.get("held_out")]
    held_out_multi_step_success = [
        result for result in held_out_multi_step if result["result"] == "compiler_reachable"
    ]
    carry_out_of_pressure = next((result for result in results if result["concept"] == "carry_out_of_pressure"), None)
    findings: list[dict[str, str]] = []
    if any(result.get("concept_name_used_as_hint") for result in results):
        findings.append({"code": "concept_name_hint_used", "message": "A target used concept name inside the typed contract.", "path": "row_ledger"})
    if any(result.get("provider_name_used_as_hint") for result in results):
        findings.append({"code": "provider_name_hint_used", "message": "A target used a provider/catalog name inside the typed contract.", "path": "row_ledger"})
    if any(result.get("gold_chain_used_as_input") for result in results):
        findings.append({"code": "gold_chain_used_as_input", "message": "Coverage-map gold chain was consumed during synthesis.", "path": "row_ledger"})
    if any(result.get("pattern_dispatch_used") for result in results):
        findings.append({"code": "pattern_dispatch_used", "message": "Pattern dispatch was used during search.", "path": "row_ledger"})
    if requires_held_out_acceptance and not held_out_success:
        findings.append({"code": "no_held_out_success", "message": "No held-out target became compiler_reachable.", "path": "row_ledger"})
    if requires_held_out_acceptance and (carry_out_of_pressure is None or carry_out_of_pressure["result"] != "compiler_reachable"):
        findings.append(
            {
                "code": "primary_multistep_flip_missing",
                "message": "carry_out_of_pressure did not flip to compiler_reachable.",
                "path": "row_ledger",
            }
        )
    if requires_held_out_acceptance and not held_out_multi_step_success:
        findings.append(
            {
                "code": "no_held_out_multistep_success",
                "message": "No held-out multi-step target became compiler_reachable.",
                "path": "row_ledger",
            }
        )
    return {
        "schema_version": "compiler_search_reachability_report.v0",
        "status": "PASS" if not findings else "FAIL",
        "synthesizer_version": SYNTHESIZER_VERSION,
        "synthesizer_strategy": targets_payload["strategy"],
        "scope": {
            "mode": sample_policy,
            "natural_language": False,
            "atlas_wide_execution": False,
            "target_count": len(results),
            "coverage_ledger_update_enabled": UPDATE_LEDGER,
            "shared_node_cache_enabled": SHARED_NODE_CACHE_ENABLED,
            "persistent_node_cache_enabled": PERSISTENT_NODE_CACHE_ENABLED,
            "search_worker_count": WORKERS,
            "pattern_dispatch_allowed": False,
            "coverage_gold_chain_allowed_as_input": False,
            "concept_name_allowed_as_input": False,
            "provider_name_allowed_as_input": False,
            "perspective_team_roles": PERSPECTIVE_TEAM_ROLES,
        },
        "search_budget": {
            "max_depth": MAX_DEPTH,
            "max_branching": MAX_BRANCHING,
            "budget_label": SEARCH_BUDGET_LABEL,
            "allowed_catalog_refs": sorted(default_allowed_catalog_refs()),
            "excluded_catalog_refs": CONCEPT_SHAPED_MACROS,
            "rules": [
                "provider_field_backward_search",
                "generic_before_after_change",
                "generic_binary_episode_join",
                "generic_delta_across_anchor_operator",
                "generic_vector_projection_operator",
            ],
        },
        "summary": {
            "coverage_supported_count": supported,
            "coverage_supported_pct": round(100 * supported / total, 1),
            "compiler_reachable_count": compiler_reachable,
            "compiler_reachable_pct": round(100 * compiler_reachable / total, 1),
            "sample_target_count": len(results),
            "sample_compiler_reachable_count": result_counts.get("compiler_reachable", 0),
            "sample_compiler_reachable_pct": round(100 * result_counts.get("compiler_reachable", 0) / max(len(results), 1), 1),
            "sample_only_note": (
                "sample_* fields are the measurement for non-updating runs; "
                "compiler_reachable_count reflects the supplied coverage ledger after mutation only when ledger updates are enabled."
            ),
            "held_out_target_count": len(held_out),
            "held_out_compiler_reachable_count": len(held_out_success),
            "held_out_compiler_reachable_pct": round(100 * len(held_out_success) / max(len(held_out), 1), 1),
            "multi_step_target_count": len(multi_step),
            "multi_step_compiler_reachable_count": len(multi_step_success),
            "held_out_multi_step_target_count": len(held_out_multi_step),
            "held_out_multi_step_compiler_reachable_count": len(held_out_multi_step_success),
            "execution_reuse_enabled": SHARED_NODE_CACHE_ENABLED,
            "execution_node_cache": cache_summary,
            "execution_cache_backend": cache_backend_summary,
        },
        "failure_distribution": dict(sorted(failure_counts.items())),
        "result_distribution": dict(sorted(result_counts.items())),
        "held_out_successes": [result["concept"] for result in held_out_success],
        "multi_step_successes": [result["concept"] for result in multi_step_success],
        "held_out_multi_step_successes": [result["concept"] for result in held_out_multi_step_success],
        "row_ledger_path": relative_path(ROW_LEDGER),
        "row_csv_path": relative_path(ROW_CSV),
        "plan_dir": relative_path(PLAN_DIR),
        "targets_path": relative_path(TARGETS),
        "report_priority": "Held-out successes and real failure distribution are the meaningful outputs.",
        "findings": findings,
    }


def search_node_cache_summary(results: list[dict[str, Any]]) -> dict[str, int]:
    summary: collections.Counter[str] = collections.Counter()
    for result in results:
        cache = result.get("execution_node_cache")
        if not isinstance(cache, dict):
            continue
        for key in ("hits", "local_hits", "shared_hits", "misses", "disabled", "bypassed"):
            summary[key] += int(cache.get(key) or 0)
    return dict(sorted(summary.items()))


def default_allowed_catalog_refs() -> list[str]:
    return [entry.name for entry in [*default_catalog().primitives, *default_catalog().relations] if entry.name not in EXCLUDED_CATALOG_REFS]


def write_rows(results: list[dict[str, Any]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ROW_LEDGER.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    keys = [
        "target_id",
        "concept",
        "held_out",
        "multi_step",
        "search_budget_label",
        "coverage_classification",
        "input_composition_maturity",
        "result",
        "failure_taxonomy",
        "result_count",
        "honest_zero",
        "requested_evidence_failure_count",
        "execution_node_cache",
        "document_hash",
        "terminal_provider",
        "message",
    ]
    with ROW_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for result in results:
            writer.writerow(result)


def concept_name_used_as_hint(target: dict[str, Any]) -> bool:
    concept = str(target["concept"]).lower()
    contract = json.dumps(target["target_contract"], sort_keys=True).lower()
    return concept in contract


def provider_name_used_as_hint(target: dict[str, Any]) -> bool:
    provider_names = {entry.name.lower() for entry in CatalogIndex().entries.values()}
    for value in json_string_values(target.get("target_contract")):
        if value.lower() in provider_names:
            return True
    return False


def json_string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        values: list[str] = []
        for child in value.values():
            values.extend(json_string_values(child))
        return values
    if isinstance(value, list):
        values = []
        for child in value:
            values.extend(json_string_values(child))
        return values
    return []


def gold_chain_audit(row: dict[str, Any]) -> dict[str, Any]:
    chain = str(row.get("closest_supported_substitute") or "")
    if not chain:
        return {"status": "not_available", "note": "coverage row has no closest_supported_substitute"}
    return {
        "status": "post_hoc_only",
        "note": "Gold chain is read only after synthesis for audit comparison.",
        "raw_chain": chain,
    }


def catalog_node(
    node_id: str,
    entry: CatalogEntry,
    *,
    inputs: dict[str, dict[str, str]] | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    node = {
        "kind": entry.kind.value,
        "node_id": node_id,
        "catalog_ref": entry.name,
        "version": entry.version,
    }
    if inputs:
        node["inputs"] = inputs
    if parameters:
        node["parameters"] = parameters
    return node


def operator_node(
    *,
    node_id: str,
    operator_name: str,
    version: str,
    inputs: dict[str, dict[str, str]],
    parameters: dict[str, Any],
    output_evidence_fields: set[str] | None = None,
) -> dict[str, Any]:
    signature = operator_signature(operator_name, version)
    outputs = [output.model_dump(mode="json") for output in signature.outputs]
    if output_evidence_fields is not None:
        evidence_fields = sorted(str(field) for field in output_evidence_fields if str(field) != "none")
        for output in outputs:
            output["evidence_fields"] = evidence_fields
    return {
        "kind": "operator",
        "node_id": node_id,
        "operator": {"name": operator_name, "version": version},
        "inputs": inputs,
        "parameters": parameters,
        "outputs": outputs,
    }


def operator_signature(operator_name: str, version: str) -> Any:
    for signature in OPERATOR_SIGNATURES_BY_CONSTRAINT_KIND.values():
        if signature.name == operator_name and signature.version == version:
            return signature
    raise SynthesisError(
        "missing_constraint",
        "No declared operator signature for generated operator node.",
        {"operator_name": operator_name, "operator_version": version},
    )


def document(
    *,
    target_id: str,
    display_name: str,
    description: str,
    nodes: list[dict[str, Any]],
    predicate_ids: list[str],
    anchor_source: dict[str, str],
    requested_evidence: list[dict[str, Any]],
    claim_boundary: str,
    perspective_team_role: str,
) -> dict[str, Any]:
    recipe_id = f"search_{target_id}"
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": recipe_id,
            "recipe_version": "0.1.0",
            "display_name": display_name,
            "description": description,
            "parameters": [],
            "default_unknown_evidence_policy": "exclude_candidate",
            "allowed_claims": [claim_boundary],
            "disallowed_claims": [
                "The system inferred player intent, tactical causation, decision quality, optimality, or pass probability.",
                "The system used a target-specific builder, pattern dispatch, or coverage-map gold chain as synthesis input.",
            ],
            "limitations": [
                "Generated by bounded backward search from typed requirements.",
                "Compiler reachability is relative to the declared v0 search strategy and budget.",
            ],
            "output_classifications": [target_id.upper()],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": f"{target_id}_probe",
            "match_ids": MATCH_IDS,
            "periods": ["firstHalf", "secondHalf"],
            "perspective_team_role": perspective_team_role,
            "parameters": {},
            "max_results": 20,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": f"search_{target_id}",
            "plan_version": "0.1.0",
            "recipe_id": recipe_id,
            "recipe_version": "0.1.0",
            "status": "experimental",
            "unknown_evidence_policy": "exclude_candidate",
            "classification_mode": "partial_declared",
            "nodes": nodes,
            "classification_rules": [
                {
                    "label": target_id.upper(),
                    "predicate_ids": predicate_ids,
                    "description": description,
                }
            ],
            "anchor_source": anchor_source,
            "requested_evidence": requested_evidence,
        },
    }


def predicate_eq(node_id: str, source_node_id: str, output_name: str, value: str) -> dict[str, Any]:
    return {
        "kind": "predicate",
        "node_id": node_id,
        "input": ref(source_node_id, output_name),
        "operator": {"name": "eq", "version": "1.0.0"},
        "compare": enum(value),
    }


def predicate_gte(node_id: str, source_node_id: str, output_name: str, value: float, unit: str) -> dict[str, Any]:
    return {
        "kind": "predicate",
        "node_id": node_id,
        "input": ref(source_node_id, output_name),
        "operator": {"name": "gte", "version": "1.0.0"},
        "compare": number(value, unit),
    }


def ref(node_id: str, output_name: str) -> dict[str, str]:
    return {"source_node_id": node_id, "output_name": output_name}


def enum(value: str) -> dict[str, str]:
    return {"payload_type": "enum", "unit": "none", "value": value}


def boolean(value: bool) -> dict[str, Any]:
    return {"payload_type": "boolean", "unit": "none", "value": bool(value)}


def number(value: float, unit: str) -> dict[str, Any]:
    return {"payload_type": "number", "unit": unit, "value": value}


def coverage_row(rows: list[dict[str, Any]], concept: str) -> dict[str, Any]:
    for row in rows:
        if row.get("concept") == concept:
            return row
    raise RuntimeError(f"Coverage concept not found: {concept}")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        if path.parent.name in {"out", "plans", "cache"}:
            return f"<external>/{path.parent.name}/{path.name}"
        return f"<external>/{path.name}"


if __name__ == "__main__":
    raise SystemExit(main())
