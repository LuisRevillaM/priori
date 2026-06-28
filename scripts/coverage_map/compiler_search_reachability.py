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
MATCH_IDS = ["J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9", "J03WMX", "J03WN1"]

SUPPORTED_MODALITIES = {"tracking", "events", "tracking_event_synchronized"}
SUPPORTED_COMPOSITION_CONSTRAINT_KINDS = {
    "before_after_same_anchor",
    "distinct_entity_fields",
    "frame_alignment",
    "same_anchor_identity",
    "same_player_return",
    "temporal_order",
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
    def __init__(self) -> None:
        catalog = default_catalog()
        self.entries: dict[str, CatalogEntry] = {
            entry.name: entry
            for entry in [*catalog.primitives, *catalog.relations]
            if entry.name not in EXCLUDED_CATALOG_REFS
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


@dataclass
class BuildResult:
    nodes: list[dict[str, Any]]
    terminal_node_id: str
    terminal_entry: str
    terminal_output: str
    field_sources: dict[str, tuple[str, str]]
    rules_used: list[str] = field(default_factory=list)
    providers_used: list[str] = field(default_factory=list)


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

    plan_path = PLAN_DIR / f"{target['target_id']}.json"
    plan_path.write_text(json.dumps(build["document"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        document = TacticalQueryDocument.model_validate(build["document"])
        bound = bind_document(document)
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

    try:
        execution = executor.execute(bound)
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

    rows = execution_result_rows(execution)
    evidence_failures = int(execution.provenance.get("requested_evidence_failure_count") or 0)
    if execution.status != ExecutionStatus.PASS or evidence_failures != 0:
        return row_result(
            target=target,
            row=row,
            result="not_compiler_reachable",
            failure_taxonomy="runtime_gap",
            message="Discovered plan did not execute with complete requested evidence.",
            target_contract_hash=target_hash,
            document_payload=build["document"],
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
        document_payload=build["document"],
        build=build,
        execution=execution,
        rows=rows,
    )


def synthesize_by_search(*, target: dict[str, Any], row: dict[str, Any], context: SearchContext) -> dict[str, Any]:
    contract = target["target_contract"]
    required_fields = required_target_fields(contract)
    uncovered_fields = sorted(
        field for field in required_fields if not context.catalog.providers_covering_any({field})
    )
    if uncovered_fields:
        raise SynthesisError(
            "missing_primitive",
            "No catalog provider exposes one or more required target fields.",
            {"fields": uncovered_fields},
        )
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
    if entry.name == "change_across_anchor":
        return build_change_across_anchor(context, entry, required_fields, depth=depth, input_context=input_context)

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
                input_context={},
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
                    frame_field=candidate["before_frame_field"],
                    carrier_id_field=candidate.get("carrier_id_field"),
                ),
            )
            after = build_entry(
                context,
                candidate["evaluator_entry"],
                {candidate["status_field"], candidate["value_field"]},
                depth=depth + 1,
                input_context=evaluator_input_context(
                    anchor=anchor,
                    frame_field=candidate["after_frame_field"],
                    carrier_id_field=candidate.get("carrier_id_field"),
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
    frame_field: str,
    carrier_id_field: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"anchors": anchor, "frame_field": frame_field}
    if carrier_id_field is not None:
        payload["carrier_id_field"] = carrier_id_field
    return payload


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
            score += 6 if evaluator.name in {"pressure_on_carrier", "team_compactness"} else 0
            score += 4 if anchor_entry.name in {"carry_episode", "controlled_pass_episode", "switch_of_play"} else 0
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
    scored: list[tuple[int, int, str, str, CatalogEntry, CatalogOutput]] = []
    for provider, output in candidates:
        if provider.name == consumer.name:
            continue
        fields = set(output.evidence_fields)
        score = 0
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


def required_fields_for_input(entry: CatalogEntry, input_def: CatalogInput, target_fields: set[str]) -> set[str]:
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
    if entry.name == "pressure_on_carrier":
        return {
            "frame_field": enum(str(input_context.get("frame_field", "controlled_reception_frame_id"))),
            "carrier_id_field": enum(str(input_context.get("carrier_id_field", "receiver_id"))),
            "maximum_pressure_distance_m": number(4.0, "metre"),
            "minimum_closing_speed_mps": number(0.2 if not input_context else -5.0, "none"),
            "maximum_approach_angle_degrees": number(100.0 if not input_context else 180.0, "none"),
            "minimum_pressure_duration_seconds": number(0.0, "second"),
            "lookback_seconds": number(0.4, "second"),
            "candidate_scope": enum("defending_outfield"),
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
    return {}


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


def assemble_document(*, target: dict[str, Any], build: BuildResult) -> dict[str, Any]:
    contract = target["target_contract"]
    predicates = predicates_for_contract(contract, build.field_sources)
    requested_evidence = [
        {
            "source": {"source_node_id": build.field_sources[field][0], "output_name": build.field_sources[field][1]},
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
    )


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
        "concept_name_used_as_hint": concept_name_used_as_hint(target),
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
        row["composition_maturity"] = "compiler_reachable"
        row["composition_maturity_applicable"] = row.get("classification") == "supported"
        row["compiler_reachability_status"] = "compiler_reachable"
        row["compiler_reachability_evidence"] = {
            "synthesizer_version": SYNTHESIZER_VERSION,
            "synthesizer_strategy": SYNTHESIZER_STRATEGY,
            "target_id": result["target_id"],
            "report_path": relative_path(REPORT),
            "document_hash": result["document_hash"],
            "held_out": result["held_out"],
            "result_count": result["result_count"],
            "honest_zero": result["honest_zero"],
        }


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
            "perspective_team_role": "home",
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
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
