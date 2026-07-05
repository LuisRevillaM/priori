"""SCP2-2 Hermes NL eval harness.

The CLI path always calls the real Hermes NL compiler. Tests may pass a local
compiler function into ``evaluate_case_set_payload`` to exercise verdict logic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from tqe.runtime.ir import stable_hash
from tqe.semantic_compiler.hermes_nl import (
    ClarificationRequiredOutcome,
    ExpressionOutcome,
    HermesNLContext,
    HermesOutcome,
    compile_nl_request,
)
from tqe.semantic_compiler.meaning_expression import DEFAULT_KNOWLEDGE_PACK_PATH
from tqe.semantic_compiler.target_synthesis import synthesize_and_bind


CompilerFn = Callable[[str, HermesNLContext | None], HermesOutcome]
DEFAULT_COVERAGE_MAP_PATH = Path("generated/coverage-map.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SCP2-2 NL eval cases through Hermes.")
    parser.add_argument("--case-set", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pack-path", default=DEFAULT_KNOWLEDGE_PACK_PATH, type=Path)
    parser.add_argument("--coverage-map", default=DEFAULT_COVERAGE_MAP_PATH, type=Path)
    parser.add_argument("--provider", default=os.environ.get("HERMES_SCP2_2_PROVIDER", "anthropic"))
    parser.add_argument("--model", default=os.environ.get("HERMES_SCP2_2_MODEL", "claude-sonnet-4-5"))
    parser.add_argument("--long-threshold-seconds", default=300.0, type=float)
    args = parser.parse_args(argv)

    os.environ["HERMES_SCP2_2_PROVIDER"] = args.provider
    os.environ["HERMES_SCP2_2_MODEL"] = args.model

    def real_compiler(text: str, context: HermesNLContext | None = None) -> HermesOutcome:
        return compile_nl_request(text, context, pack_path=args.pack_path)

    result = evaluate_case_set(
        case_set_path=args.case_set,
        compiler=real_compiler,
        pack_path=args.pack_path,
        coverage_map_path=args.coverage_map,
        long_threshold_seconds=args.long_threshold_seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print_verdict_table(result)
    return 0 if result["summary"]["fail"] == 0 else 1


def evaluate_case_set(
    *,
    case_set_path: Path,
    compiler: CompilerFn,
    pack_path: Path = DEFAULT_KNOWLEDGE_PACK_PATH,
    coverage_map_path: Path = DEFAULT_COVERAGE_MAP_PATH,
    long_threshold_seconds: float = 300.0,
) -> dict[str, Any]:
    payload_bytes = case_set_path.read_bytes()
    payload = json.loads(payload_bytes)
    return evaluate_case_set_payload(
        payload,
        compiler=compiler,
        case_set_ref=str(case_set_path),
        case_set_sha256=hashlib.sha256(payload_bytes).hexdigest(),
        pack_path=pack_path,
        coverage_rows=load_coverage_rows(coverage_map_path),
        long_threshold_seconds=long_threshold_seconds,
    )


def evaluate_case_set_payload(
    payload: dict[str, Any],
    *,
    compiler: CompilerFn,
    case_set_ref: str,
    case_set_sha256: str | None = None,
    pack_path: Path = DEFAULT_KNOWLEDGE_PACK_PATH,
    coverage_rows: list[dict[str, Any]] | None = None,
    long_threshold_seconds: float = 300.0,
) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    started_monotonic = time.monotonic()
    cases = list(payload.get("cases") or [])
    verdicts = [
        evaluate_case(case, compiler=compiler, coverage_rows=coverage_rows)
        for case in cases
    ]
    elapsed_seconds = time.monotonic() - started_monotonic
    finished_at = datetime.now(UTC)
    pass_count = sum(1 for verdict in verdicts if verdict["status"] == "PASS")
    fail_count = len(verdicts) - pass_count
    pack_payload = json.loads(pack_path.read_text(encoding="utf-8"))
    return {
        "schema_version": "scp2_2.eval_results.v0",
        "case_set_ref": case_set_ref,
        "case_set_sha256": case_set_sha256 or stable_hash(payload),
        "pack_path": str(pack_path),
        "pack_sha256": str(pack_payload["knowledge_pack_sha256"]),
        "started_at_utc": started_at.isoformat().replace("+00:00", "Z"),
        "finished_at_utc": finished_at.isoformat().replace("+00:00", "Z"),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "long_run_threshold_seconds": long_threshold_seconds,
        "long_run_flag": elapsed_seconds > long_threshold_seconds,
        "summary": {
            "total": len(verdicts),
            "pass": pass_count,
            "fail": fail_count,
        },
        "verdicts": verdicts,
    }


def evaluate_case(
    case: dict[str, Any],
    *,
    compiler: CompilerFn,
    coverage_rows: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    kind = str(case.get("kind") or "single")
    if kind == "single":
        return evaluate_single_case(case, compiler=compiler, coverage_rows=coverage_rows)
    if kind == "same_meaning_pair":
        return evaluate_pair_case(case, compiler=compiler, coverage_rows=coverage_rows, expect_equal=True)
    if kind == "changed_meaning_pair":
        return evaluate_pair_case(case, compiler=compiler, coverage_rows=coverage_rows, expect_equal=False)
    if kind == "clarification_turn":
        return evaluate_clarification_case(case, compiler=compiler, coverage_rows=coverage_rows)
    return fail_verdict(case, [f"unknown case kind: {kind}"], observations=[])


def evaluate_single_case(
    case: dict[str, Any],
    *,
    compiler: CompilerFn,
    coverage_rows: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    outcome, observation = compile_observation(
        compiler,
        str(case["request_text"]),
        None,
        coverage_rows=coverage_rows,
    )
    failures = []
    if outcome is None:
        failures.append(observation["exception"])
    else:
        failures.extend(expected_failures(case.get("expected") or {}, observation))
    return verdict(case, failures, [observation])


def evaluate_pair_case(
    case: dict[str, Any],
    *,
    compiler: CompilerFn,
    coverage_rows: list[dict[str, Any]] | None,
    expect_equal: bool,
) -> dict[str, Any]:
    outcomes_and_observations = [
        compile_observation(compiler, str(text), None, coverage_rows=coverage_rows)
        for text in case.get("request_texts") or []
    ]
    outcomes = [item[0] for item in outcomes_and_observations]
    observations = [item[1] for item in outcomes_and_observations]
    failures: list[str] = []
    if len(observations) != 2:
        failures.append("pair case must contain exactly two request_texts")
    for index, (outcome, observation) in enumerate(zip(outcomes, observations, strict=False)):
        if outcome is None:
            failures.append(f"request {index + 1}: {observation['exception']}")
            continue
        if observation["outcome"] != "expression":
            failures.append(f"request {index + 1} outcome was {observation['outcome']}, not expression")
        if observation.get("synthesis_error"):
            failures.append(f"request {index + 1} synthesis failed: {observation['synthesis_error']}")
        for expected_failure in expected_failures(case.get("expected") or {}, observation):
            failures.append(f"request {index + 1}: {expected_failure}")
    if len(observations) == 2 and not failures:
        left = observations[0].get("synthesized_document_hash")
        right = observations[1].get("synthesized_document_hash")
        if expect_equal and left != right:
            failures.append("same-meaning synthesized document hashes differ")
        if not expect_equal and left == right:
            failures.append("changed-meaning synthesized document hashes are equal")
    return verdict(case, failures, observations)


def evaluate_clarification_case(
    case: dict[str, Any],
    *,
    compiler: CompilerFn,
    coverage_rows: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    first, first_observation = compile_observation(
        compiler,
        str(case["request_text"]),
        None,
        coverage_rows=coverage_rows,
    )
    failures = []
    if first is None:
        failures.append(first_observation["exception"])
    else:
        failures.extend(expected_failures(case.get("expected") or {}, first_observation))
    observations = [first_observation]
    if not isinstance(first, ClarificationRequiredOutcome):
        failures.append(f"first turn outcome was {first_observation['outcome']}, not clarification_required")
        return verdict(case, failures, observations)
    answer = str(case.get("answer") or "")
    context = HermesNLContext(pending_clarification=first.state, answer=answer)
    second, second_observation = compile_observation(
        compiler,
        answer or str(case["request_text"]),
        context,
        coverage_rows=coverage_rows,
    )
    observations.append(second_observation)
    if second is None:
        failures.append(second_observation["exception"])
        return verdict(case, failures, observations)
    final_expected = dict(case.get("final_expected") or {})
    if final_expected:
        failures.extend(expected_failures(final_expected, second_observation))
    if second_observation["outcome"] == "clarification_required":
        failures.append("clarification resume re-asked instead of resolving typed state")
    return verdict(case, failures, observations)


def compile_observation(
    compiler: CompilerFn,
    text: str,
    context: HermesNLContext | None,
    *,
    coverage_rows: list[dict[str, Any]] | None,
) -> tuple[HermesOutcome | None, dict[str, Any]]:
    try:
        outcome = compiler(text, context)
    except Exception as exc:  # noqa: BLE001
        return None, {
            "outcome": "exception",
            "exception_type": type(exc).__name__,
            "exception": f"{type(exc).__name__}: {exc}",
        }
    return outcome, observe_outcome(outcome, coverage_rows=coverage_rows)


def observe_outcome(
    outcome: HermesOutcome,
    *,
    coverage_rows: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "outcome": outcome.outcome,
        "transcript": transcript_ref(outcome.transcript),
    }
    if isinstance(outcome, ExpressionOutcome):
        operators = [item.operator for item in outcome.expression.operator_applications]
        base.update(
            {
                "expression_id": outcome.expression.expression_id,
                "concept_identity": outcome.expression.concept_identity,
                "expression_document_hash": outcome.document_hash,
                "operators": operators,
            }
        )
        try:
            synthesized = synthesize_and_bind(outcome.expression, coverage_rows=coverage_rows)
        except Exception as exc:  # noqa: BLE001
            base["synthesis_error"] = f"{type(exc).__name__}: {exc}"
        else:
            base["synthesized_document_hash"] = synthesized["document_hash"]
            base["terminal_provider"] = synthesized["build"].get("terminal_provider")
            metadata = synthesized["build"].get("build_metadata") or {}
            base["population_terminal"] = metadata.get("population_terminal")
    elif isinstance(outcome, ClarificationRequiredOutcome):
        base.update(
            {
                "dimension": outcome.dimension,
                "reading_count": len(outcome.readings),
                "state_id": outcome.state.state_id,
            }
        )
    else:
        if hasattr(outcome, "gap_code"):
            base["gap_code"] = outcome.gap_code
        if hasattr(outcome, "missing_capability"):
            base["missing_capability"] = outcome.missing_capability
        if hasattr(outcome, "modality"):
            base["modality"] = outcome.modality
    return base


def expected_failures(expected: dict[str, Any], observation: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for field in (
        "outcome",
        "gap_code",
        "dimension",
        "modality",
        "concept_identity",
        "expression_id",
        "synthesized_document_hash",
        "terminal_provider",
        "population_terminal",
    ):
        if field in expected and observation.get(field) != expected[field]:
            failures.append(f"{field} expected {expected[field]!r}, got {observation.get(field)!r}")
    if "operators_include" in expected:
        actual = set(observation.get("operators") or [])
        missing = sorted(set(expected["operators_include"]) - actual)
        if missing:
            failures.append(f"operators missing {missing!r}")
    if expected.get("synthesis") == "pass" and observation.get("synthesis_error"):
        failures.append(f"synthesis failed: {observation['synthesis_error']}")
    return failures


def transcript_ref(transcript: Any) -> dict[str, Any]:
    return {
        "prompt_hash": transcript.prompt_hash,
        "completion_hash": transcript.completion_hash,
        "model_provider": transcript.model_provider,
        "model_name": transcript.model_name,
    }


def verdict(case: dict[str, Any], failures: list[str], observations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "case_id": case.get("case_id"),
        "kind": case.get("kind") or "single",
        "status": "FAIL" if failures else "PASS",
        "failures": failures,
        "observations": observations,
    }


def fail_verdict(
    case: dict[str, Any],
    failures: list[str],
    *,
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    return verdict(case, failures, observations)


def load_coverage_rows(path: Path) -> list[dict[str, Any]] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return None


def print_verdict_table(result: dict[str, Any]) -> None:
    print("case_id\tkind\tstatus\tfailures")
    for item in result["verdicts"]:
        print(
            f"{item.get('case_id')}\t{item.get('kind')}\t{item.get('status')}\t"
            f"{'; '.join(item.get('failures') or [])}"
        )
    summary = result["summary"]
    print(f"summary\t-\tPASS={summary['pass']} FAIL={summary['fail']} TOTAL={summary['total']}")
    if result.get("long_run_flag"):
        print(
            "LONG_RUN\t-\t"
            f"elapsed={result['elapsed_seconds']}s threshold={result['long_run_threshold_seconds']}s"
        )


if __name__ == "__main__":
    raise SystemExit(main())
