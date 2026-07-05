#!/usr/bin/env python3
"""Generate and summarize the R1-5 full-population audit."""

from __future__ import annotations

import argparse
import collections
import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tqe.runtime.binder import bind_document  # noqa: E402
from tqe.runtime.executor import TacticalQueryExecutor, project_requested_evidence  # noqa: E402
from tqe.runtime.ir import TacticalQueryDocument, stable_hash  # noqa: E402

DEFAULT_PLAN_BUNDLE = Path("delivery/packets/r1-5-copy-proof/search-run/plans/r1_5_fragile_possession_state_v0.json")
DEFAULT_AUDIT_JSON = Path("delivery/packets/r1-5-population-audit/audit.json")
DEFAULT_AUDIT_MD = Path("delivery/packets/r1-5-population-audit/audit.md")
DEFAULT_R1_C_AUDIT_JSON = Path("delivery/packets/r1-c-sweep/population-audit/audit.json")
DEFAULT_R1_C_AUDIT_MD = Path("delivery/packets/r1-c-sweep/population-audit/audit.md")
STATUS_FIELDS = (
    "typed_join_status",
    "window_status",
    "pressure_status",
    "support_arrival_status",
)
UNKNOWN_FIELDS = (
    "typed_join_unknown_rows",
    "window_unknown_rows",
    "pressure_unknown_rows",
    "support_arrival_unknown_rows",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def format_distribution(distribution: dict[str, int]) -> str:
    return ", ".join(f"{key} {value}" for key, value in distribution.items())


def ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def canonical_match_ids(canonical_root: Path) -> list[str]:
    import pandas as pd

    matches = pd.read_parquet(canonical_root / "matches.parquet", columns=["match_id"])
    return ordered_unique([str(match_id) for match_id in matches["match_id"].tolist()])


def render_markdown(audit: dict[str, Any]) -> str:
    summary = audit["summary"]
    lines = [
        "# R1-5 Full-Population Audit",
        "",
        f"Source plan: `{summary['source_plan_bundle']}`",
        f"Plan hash: `{summary['source_plan_bundle_hash']}`",
    ]
    if summary.get("execution_plan_bundle_hash"):
        lines.append(f"Execution plan hash: `{summary['execution_plan_bundle_hash']}`")
    if summary.get("match_scope"):
        scope = summary["match_scope"]
        lines.append(f"Match scope: `{scope['source']}` ({len(scope['match_ids'])} matches)")
    lines.extend(
        [
        "",
        "## Summary",
        "",
        f"Total terminal rows: {summary['total_rows']}",
        f"Terminal population hash: `{summary['terminal_population_hash']}`",
        "",
        "### Status Distributions",
        "",
        ]
    )
    for field in STATUS_FIELDS:
        lines.append(f"- `{field}`: {format_distribution(summary['status_distributions'][field])}")
    lines.extend(["", "### UNKNOWN Accounting", ""])
    for field in UNKNOWN_FIELDS:
        lines.append(f"- `{field}`: {summary['unknown_accounting'][field]}")
    lines.extend(
        [
            "",
            f"Requested-evidence missing rows: {summary['requested_evidence_missing_rows']}",
            "",
            "### By Role / Match / Period",
            "",
            "| Role | Match | Period | Rows | Status distribution |",
            "| --- | --- | --- | ---: | --- |",
        ]
    )
    for role_summary in summary["role_summaries"]:
        role = role_summary["role"]
        for period in role_summary["periods"]:
            lines.append(
                f"| `{role}` | `{period['match_id']}` | `{period['period']}` | "
                f"{period['rows']} | {format_distribution(period['status_distribution'])} |"
            )
    return "\n".join(lines) + "\n"


def audit_row(record: dict[str, Any], *, role: str, bound_plan: Any) -> dict[str, Any]:
    requested = project_requested_evidence(record, bound_plan)
    return {
        "match_id": record.get("match_id"),
        "period": record.get("period"),
        "audit_role": role,
        "anchor_id": record.get("anchor_id"),
        "anchor_frame_id": record.get("anchor_frame_id"),
        "typed_join_status": record.get("typed_join_status"),
        "typed_join_reason": record.get("typed_join_reason"),
        "typed_join_constraint_failures": record.get("typed_join_constraint_failures"),
        "left_status": record.get("left_status"),
        "right_status": record.get("right_status"),
        "left_required_status_value": record.get("left_required_status_value"),
        "right_required_status_value": record.get("right_required_status_value"),
        "left_team_role": record.get("left_team_role"),
        "right_team_role": record.get("right_team_role"),
        "window_status": requested.get("window_status"),
        "pressure_status": requested.get("pressure_status"),
        "support_arrival_status": requested.get("support_arrival_status"),
        "nearest_defender_distance_m": requested.get("nearest_defender_distance_m"),
        "supporting_player_ids": requested.get("supporting_player_ids"),
        "requested_evidence": requested,
    }


def terminal_records_for_document(
    *,
    document_payload: dict[str, Any],
    role: str,
    canonical_root: Path,
) -> list[dict[str, Any]]:
    document = TacticalQueryDocument.model_validate(copy.deepcopy(document_payload))
    bound = bind_document(document)
    executor = TacticalQueryExecutor(canonical_root=canonical_root)
    source = bound.anchor_source
    rows: list[dict[str, Any]] = []
    params = executor_runtime_parameters(bound)
    for match_id in bound.match_ids:
        for period in bound.periods:
            state = executor._execute_period(  # noqa: SLF001 - audit needs pre-truncation terminal population.
                bound_plan=bound,
                match_id=match_id,
                period=period,
                params=params,
                compatibility_profile=executor.compatibility_profile,
            )
            terminal = state.signals[source.source_node_id][source.output_name]
            for record in terminal:
                rows.append(audit_row(record, role=role, bound_plan=bound))
    return rows


def executor_runtime_parameters(bound_plan: Any) -> Any:
    # Keep the import local to avoid making this audit script part of the public
    # executor API surface.
    from tqe.runtime.executor import runtime_parameters

    return runtime_parameters(bound_plan)


def sorted_distribution(distribution: dict[str, int]) -> dict[str, int]:
    return {key: int(distribution[key]) for key in sorted(distribution)}


def population_number_signature(audit: dict[str, Any]) -> dict[str, Any]:
    summary = audit["summary"]
    role_totals = []
    period_rows = []
    for role_summary in summary["role_summaries"]:
        role_totals.append(
            {
                "role": role_summary["role"],
                "total_rows": role_summary["total_rows"],
                "status_distribution": sorted_distribution(role_summary["status_distribution"]),
            }
        )
        for period in role_summary["periods"]:
            period_rows.append(
                {
                    "role": role_summary["role"],
                    "match_id": period["match_id"],
                    "period": period["period"],
                    "rows": period["rows"],
                    "status_distribution": sorted_distribution(period["status_distribution"]),
                }
            )
    role_totals.sort(key=lambda row: row["role"])
    period_rows.sort(key=lambda row: (row["role"], row["match_id"], row["period"]))
    return {
        "total_rows": summary["total_rows"],
        "match_ids": sorted(str(match_id) for match_id in summary["match_ids"]),
        "periods": sorted(str(period) for period in summary["periods"]),
        "roles": sorted(str(role) for role in summary["roles"]),
        "status_distributions": {
            field: sorted_distribution(summary["status_distributions"][field])
            for field in STATUS_FIELDS
        },
        "unknown_accounting": {
            field: int(summary["unknown_accounting"][field])
            for field in sorted(summary["unknown_accounting"])
        },
        "requested_evidence_missing_rows": summary["requested_evidence_missing_rows"],
        "role_totals": role_totals,
        "period_rows": period_rows,
    }


def build_summary(
    *,
    rows: list[dict[str, Any]],
    plan_bundle_path: Path,
    source_plan_bundle: dict[str, Any],
    execution_plan_bundle: dict[str, Any],
    match_scope: dict[str, Any] | None,
) -> dict[str, Any]:
    match_ids = (
        [str(match_id) for match_id in match_scope["match_ids"]]
        if match_scope
        else ordered_unique([str(row["match_id"]) for row in rows])
    )
    periods = ["firstHalf", "secondHalf"]
    status_distributions = {
        field: dict(collections.Counter(str(row.get(field)) for row in rows))
        for field in STATUS_FIELDS
    }
    unknown_accounting = {
        "typed_join_unknown_rows": status_distributions["typed_join_status"].get("UNKNOWN", 0),
        "window_unknown_rows": status_distributions["window_status"].get("UNKNOWN", 0),
        "pressure_unknown_rows": status_distributions["pressure_status"].get("UNKNOWN", 0),
        "support_arrival_unknown_rows": status_distributions["support_arrival_status"].get("UNKNOWN", 0),
    }
    role_summaries = []
    for role in sorted({str(row["audit_role"]) for row in rows}):
        role_rows = [row for row in rows if row["audit_role"] == role]
        period_rows = []
        for match_id in match_ids:
            for period in periods:
                selected = [row for row in role_rows if row["match_id"] == match_id and row["period"] == period]
                period_rows.append(
                    {
                        "match_id": match_id,
                        "period": period,
                        "rows": len(selected),
                        "status_distribution": dict(collections.Counter(str(row["typed_join_status"]) for row in selected)),
                    }
                )
        role_summaries.append(
            {
                "role": role,
                "total_rows": len(role_rows),
                "status_distribution": dict(collections.Counter(str(row["typed_join_status"]) for row in role_rows)),
                "periods": period_rows,
            }
        )
    return {
        "schema_version": "r1_5_population_audit.v1",
        "source_plan_bundle": str(plan_bundle_path),
        "source_plan_bundle_hash": stable_hash(source_plan_bundle),
        "execution_plan_bundle_hash": stable_hash(execution_plan_bundle),
        "match_scope": match_scope,
        "match_ids": match_ids,
        "periods": periods,
        "roles": sorted({str(row["audit_role"]) for row in rows}),
        "max_results": "100 binder limit; terminal population read before result truncation",
        "total_rows": len(rows),
        "terminal_population_hash": stable_hash(rows),
        "status_distributions": status_distributions,
        "unknown_accounting": unknown_accounting,
        "requested_evidence_missing_rows": sum(
            1
            for row in rows
            if any(value is None for value in row.get("requested_evidence", {}).values())
        ),
        "role_summaries": role_summaries,
    }


def scoped_plan_bundle(
    *,
    plan_bundle: dict[str, Any],
    match_ids: list[str] | None,
) -> dict[str, Any]:
    execution_plan_bundle = copy.deepcopy(plan_bundle)
    if match_ids is None:
        return execution_plan_bundle
    for document_payload in execution_plan_bundle["documents"].values():
        default_invocation = document_payload.setdefault("default_invocation", {})
        default_invocation["match_ids"] = list(match_ids)
    return execution_plan_bundle


def generate_audit(
    *,
    plan_bundle_path: Path,
    canonical_root: Path,
    match_ids: list[str] | None = None,
    match_scope_source: str | None = None,
) -> dict[str, Any]:
    plan_bundle = load_json(plan_bundle_path)
    if match_ids is not None:
        match_ids = ordered_unique([str(match_id) for match_id in match_ids])
    execution_plan_bundle = scoped_plan_bundle(plan_bundle=plan_bundle, match_ids=match_ids)
    match_scope = None
    if match_ids is not None:
        match_scope = {
            "source": str(match_scope_source or "explicit_match_ids"),
            "match_ids": match_ids,
        }
    rows: list[dict[str, Any]] = []
    for role, document_payload in sorted(execution_plan_bundle["documents"].items()):
        rows.extend(
            terminal_records_for_document(
                document_payload=document_payload,
                role=role,
                canonical_root=canonical_root,
            )
        )
    match_order = {match_id: index for index, match_id in enumerate(match_ids or [])}
    period_order = {"firstHalf": 0, "secondHalf": 1}
    rows.sort(
        key=lambda row: (
            str(row.get("audit_role")),
            match_order.get(str(row.get("match_id")), 9999),
            str(row.get("match_id")),
            period_order.get(str(row.get("period")), 9999),
            str(row.get("period")),
            int(row.get("anchor_frame_id") or 0),
            str(row.get("anchor_id")),
        )
    )
    return {
        "summary": build_summary(
            rows=rows,
            plan_bundle_path=plan_bundle_path,
            source_plan_bundle=plan_bundle,
            execution_plan_bundle=execution_plan_bundle,
            match_scope=match_scope,
        ),
        "rows": rows,
    }


def summarize_command(args: argparse.Namespace) -> int:
    audit = load_json(args.audit_json)
    markdown = render_markdown(audit)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    return 0


def generate_command(args: argparse.Namespace) -> int:
    if args.all_canonical_matches and args.match_ids:
        raise SystemExit("--all-canonical-matches cannot be combined with --match-id")
    match_ids = None
    match_scope_source = None
    if args.all_canonical_matches:
        match_ids = canonical_match_ids(args.canonical_root)
        match_scope_source = "canonical_matches.parquet"
    elif args.match_ids:
        match_ids = args.match_ids
        match_scope_source = "explicit --match-id"
    audit = generate_audit(
        plan_bundle_path=args.plan_bundle,
        canonical_root=args.canonical_root,
        match_ids=match_ids,
        match_scope_source=match_scope_source,
    )
    write_json(args.output_json, audit)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(render_markdown(audit), encoding="utf-8")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    subparsers = root.add_subparsers(dest="command", required=True)

    summarize = subparsers.add_parser("summarize", help="Render audit markdown from an audit JSON file.")
    summarize.add_argument("--audit-json", type=Path, default=DEFAULT_AUDIT_JSON)
    summarize.add_argument("--output", type=Path)
    summarize.set_defaults(func=summarize_command)

    generate = subparsers.add_parser("generate", help="Regenerate full population audit JSON and markdown.")
    generate.add_argument("--plan-bundle", type=Path, default=DEFAULT_PLAN_BUNDLE)
    generate.add_argument("--canonical-root", type=Path, default=Path("data/canonical/v1"))
    generate.add_argument("--output-json", type=Path, default=DEFAULT_R1_C_AUDIT_JSON)
    generate.add_argument("--output-md", type=Path, default=DEFAULT_R1_C_AUDIT_MD)
    generate.add_argument("--all-canonical-matches", action="store_true")
    generate.add_argument("--match-id", dest="match_ids", action="append")
    generate.set_defaults(func=generate_command)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
