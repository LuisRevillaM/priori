from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from tqe.runtime.ir import ExecutionStatus, QueryExecution, TacticalQueryDocument
from tqe.workshop.app_service import (
    execution_cache_key,
    hermes_python_executable,
    host_owned_plan_document,
    interpret_request,
    load_plan_from_path,
    match_library,
)
from tqe.workshop.m1_2 import (
    CallerProfile,
    ExecuteQueryPlanRequest,
    SubmitQueryPlanRequest,
    ValidateQueryPlanRequest,
    execution_record_payload,
    host_confirm_bound_plan,
    read_handle,
    submit_query_plan,
    validate_query_plan,
)


APPROVED_PLAN = Path("config/query-plans/ball_side_block_shift.ir.v1.json")


def scoped_approved_plan(match_ids: list[str]) -> dict:
    payload = load_plan_from_path(APPROVED_PLAN)
    payload["default_invocation"]["match_ids"] = match_ids
    return payload


def submit_and_validate(plan_document: dict, output_root: Path) -> dict:
    document = TacticalQueryDocument.model_validate(plan_document)
    submit = submit_query_plan(
        SubmitQueryPlanRequest(plan_document=document, source_label="beta0_contract"),
        output_root=output_root,
        caller_profile=CallerProfile.HOST_MANUAL,
    )
    validation = validate_query_plan(
        ValidateQueryPlanRequest(draft_plan_id=submit.draft_plan_id),
        output_root=output_root,
        caller_profile=CallerProfile.HOST_MANUAL,
    )
    assert validation.ok
    return read_handle("bound-plans", str(validation.bound_plan_id), output_root=output_root)


class WorkbenchBeta0ContractTests(unittest.TestCase):
    def test_host_approved_recipe_only_preserves_allowlisted_scope_overrides(self) -> None:
        canonical = load_plan_from_path(APPROVED_PLAN)
        requested = deepcopy(canonical)
        requested["recipe"]["description"] = "malicious semantic replacement"
        requested["default_invocation"]["match_ids"] = ["J03WOY"]
        requested["default_invocation"]["max_results"] = 1
        requested["default_invocation"]["execution_mode"] = "dry_run"
        requested["default_invocation"]["parameters"]["wide_entry_fraction"] = {
            "payload_type": "number",
            "unit": "fraction",
            "value": 0.1,
        }

        host_owned = host_owned_plan_document(requested).model_dump(mode="json")

        self.assertEqual(["J03WOY"], host_owned["default_invocation"]["match_ids"])
        self.assertEqual(canonical["default_invocation"]["periods"], host_owned["default_invocation"]["periods"])
        self.assertEqual(
            canonical["default_invocation"]["perspective_team_role"],
            host_owned["default_invocation"]["perspective_team_role"],
        )
        self.assertEqual(canonical["default_invocation"]["max_results"], host_owned["default_invocation"]["max_results"])
        self.assertEqual(
            canonical["default_invocation"]["execution_mode"],
            host_owned["default_invocation"]["execution_mode"],
        )
        canonical_model = TacticalQueryDocument.model_validate(canonical).model_dump(mode="json")
        self.assertEqual(canonical_model["default_invocation"]["parameters"], host_owned["default_invocation"]["parameters"])
        self.assertEqual(canonical["recipe"]["description"], host_owned["recipe"]["description"])
        self.assertEqual(canonical_model["draft_plan"], host_owned["draft_plan"])

    def test_match_library_is_limited_to_deployed_manifest_with_canonical_metadata(self) -> None:
        payload = match_library()
        ids = [item["match_id"] for item in payload["matches"]]

        self.assertEqual(["J03WOY", "J03WPY", "J03WQQ", "J03WR9"], ids)
        self.assertEqual(ids, payload["default_match_ids"])
        self.assertNotIn("J03WOH", ids)
        self.assertTrue(all(item["match_title"] and item["home_team"] and item["away_team"] for item in payload["matches"]))
        self.assertTrue(all("match_day" in item and "kickoff_time_utc" in item for item in payload["matches"]))

    def test_manual_interpretation_distinguishes_reviewed_recipe_from_manual_preset(self) -> None:
        approved = interpret_request({"mode": "manual", "query": "", "preset_id": "approved_block_shift"})
        experimental = interpret_request({"mode": "manual", "query": "", "preset_id": "experimental_corridor"})

        self.assertEqual("PLAN_INTERPRETED", approved["status"])
        self.assertEqual("REVIEWED_RECIPE", approved["provenance_source"])
        self.assertEqual("ball_side_block_shift_v1", approved["recipe_id"])
        self.assertEqual("PLAN_INTERPRETED", experimental["status"])
        self.assertEqual("MANUAL_PRESET", experimental["provenance_source"])
        self.assertEqual("possession_corridor_availability_v1", experimental["recipe_id"])

    def test_scope_changes_bound_hash_cache_key_and_execution_record_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            first = host_owned_plan_document(scoped_approved_plan(["J03WOY"])).model_dump(mode="json")
            second = host_owned_plan_document(scoped_approved_plan(["J03WPY"])).model_dump(mode="json")

            first_bound = submit_and_validate(first, output_root)
            second_bound = submit_and_validate(second, output_root)

            self.assertNotEqual(first_bound["bound_plan_hash"], second_bound["bound_plan_hash"])

            first_auth = host_confirm_bound_plan(first_bound["bound_plan_id"], reviewer="beta0", output_root=output_root)
            second_auth = host_confirm_bound_plan(second_bound["bound_plan_id"], reviewer="beta0", output_root=output_root)
            first_request = ExecuteQueryPlanRequest(
                bound_plan_id=first_bound["bound_plan_id"],
                execution_authorization_id=first_auth.execution_authorization_id,
                result_limit=3,
            )
            second_request = ExecuteQueryPlanRequest(
                bound_plan_id=second_bound["bound_plan_id"],
                execution_authorization_id=second_auth.execution_authorization_id,
                result_limit=3,
            )

            self.assertNotEqual(
                execution_cache_key(first_request, output_root=output_root),
                execution_cache_key(second_request, output_root=output_root),
            )

            record = execution_record_payload(
                bound_record=first_bound,
                execution=QueryExecution(
                    execution_id="unit",
                    status=ExecutionStatus.PASS,
                    plan_hash=first_bound["draft_plan_hash"],
                    bound_plan_hash=first_bound["bound_plan_hash"],
                    provenance={"compatibility_profile": first_bound["execution_profile"]},
                ),
                rows=[],
                profile=first_bound["execution_profile"],
                execution_id="exec_unit",
            )

            self.assertEqual(
                {
                    "match_ids": ["J03WOY"],
                    "periods": ["firstHalf", "secondHalf"],
                    "perspective_team_role": "home",
                },
                record["scope"],
            )

    def test_hermes_python_falls_back_to_shebang_when_configured_path_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python_path = root / "python3"
            python_path.write_text("#!/bin/sh\n", encoding="utf-8")
            python_path.chmod(0o755)
            hermes_path = root / "hermes"
            hermes_path.write_text(f"#!{python_path}\n", encoding="utf-8")
            hermes_path.chmod(0o755)

            with patch.dict("os.environ", {"WORKBENCH_HERMES_PYTHON": str(root / "missing-python")}, clear=False):
                self.assertEqual(str(python_path), hermes_python_executable(str(hermes_path)))

    def test_hermes_python_ignores_broken_shebang_when_configured_path_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hermes_path = root / "hermes"
            hermes_path.write_text(f"#!{root / 'missing-python3'}\n", encoding="utf-8")
            hermes_path.chmod(0o755)

            with patch.dict("os.environ", {"WORKBENCH_HERMES_PYTHON": str(root / "missing-python")}, clear=False):
                self.assertEqual(sys.executable, hermes_python_executable(str(hermes_path)))


if __name__ == "__main__":
    unittest.main()
