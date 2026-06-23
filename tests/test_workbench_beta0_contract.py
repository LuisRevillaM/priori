from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from tqe.runtime.ir import ExecutionStatus, QueryExecution, TacticalQueryDocument
from tqe.workshop.app_service import (
    execution_cache_key,
    hermes_draft_provenance,
    hermes_invocation_output_root,
    hermes_python_executable,
    host_owned_plan_document,
    interpret_request,
    load_plan_from_path,
    match_library,
    recover_n1f_hermes_draft_record,
)
from tqe.workshop.m1_2 import (
    CallerProfile,
    CapabilityGap,
    ExecuteQueryPlanRequest,
    SubmitQueryPlanRequest,
    ValidateQueryPlanRequest,
    execution_record_payload,
    host_confirm_bound_plan,
    read_handle,
    submit_query_plan,
    validate_query_plan,
    write_handle,
)


APPROVED_PLAN = Path("config/query-plans/ball_side_block_shift.ir.v1.json")
N1I_ORIGIN_BUNDLE = Path("delivery/n1d/n1f-origin-bundle.json")
N1D1_ATTESTATION = Path("delivery/n1d/n1d1-attestation.json")


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


def n1i_attested_document() -> dict:
    bundle = json.loads(N1I_ORIGIN_BUNDLE.read_text(encoding="utf-8"))
    return deepcopy(bundle["host_augmentation"]["augmented_document"])


def n1d1_plan_hash() -> str:
    attestation = json.loads(N1D1_ATTESTATION.read_text(encoding="utf-8"))
    return str(attestation["plan_hash"])


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

    def test_attested_novel_composition_requires_verified_plan_hash(self) -> None:
        document = n1i_attested_document()

        source, details = hermes_draft_provenance(document, n1d1_plan_hash())
        self.assertEqual("HERMES_NOVEL_COMPOSITION", source)
        self.assertTrue(details["verified"])

        mismatch_source, mismatch_details = hermes_draft_provenance(document, "wrong_hash")
        self.assertEqual("HERMES_EXPERIMENTAL_UNVERIFIED", mismatch_source)
        self.assertIn("plan_hash", mismatch_details["failures"])

        mutated = deepcopy(document)
        mutated["draft_plan"]["nodes"] = mutated["draft_plan"]["nodes"][:-1]
        structure_source, structure_details = hermes_draft_provenance(mutated, n1d1_plan_hash())
        self.assertEqual("HERMES_EXPERIMENTAL_UNVERIFIED", structure_source)
        self.assertIn("structural_fingerprint_hash", structure_details["failures"])

    def test_attested_novel_composition_scope_mutation_is_rejected(self) -> None:
        document = n1i_attested_document()
        accepted = host_owned_plan_document(document)
        self.assertEqual("possession_corridor_destination_entry_v1", accepted.recipe.recipe_id)

        mutated = deepcopy(document)
        mutated["default_invocation"]["match_ids"] = ["J03WPY"]
        with self.assertRaises(CapabilityGap):
            host_owned_plan_document(mutated)

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

    def test_hermes_invocation_uses_active_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(root.resolve(), hermes_invocation_output_root(root))

    def test_n1f_draft_recovery_prefers_active_handle_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            document = host_owned_plan_document(scoped_approved_plan(["J03WOY"])).model_dump(mode="json")
            draft_id = "draft_deadbeefdeadbeef"
            write_handle(
                "draft-plans",
                draft_id,
                {
                    "schema_version": "1.0",
                    "draft_plan_id": draft_id,
                    "draft_plan_hash": "handle_hash",
                    "document": document,
                },
                output_root=output_root,
            )

            recovered = recover_n1f_hermes_draft_record(
                draft_id,
                {"hermes_origin": {"session_trace": {"ordered_tool_calls": [], "tool_responses": []}}},
                output_root=output_root,
                hermes_workshop_root=output_root,
            )

            self.assertEqual("handle", recovered["draft_record_source"])
            self.assertEqual("handle_hash", recovered["draft_plan_hash"])
            self.assertEqual(document, recovered["document"])

    def test_n1f_draft_recovery_falls_back_to_persisted_mcp_trace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            document = host_owned_plan_document(scoped_approved_plan(["J03WOY"])).model_dump(mode="json")
            draft_id = "draft_deadbeefdeadbeef"
            bundle = {
                "hermes_origin": {
                    "session_trace": {
                        "ordered_tool_calls": [
                            {
                                "name": "mcp_priori_tactical_submit_query_plan",
                                "arguments": {"plan_document": document, "source_label": "hermes_mcp"},
                            }
                        ],
                        "tool_responses": [
                            {
                                "tool_name": "mcp_priori_tactical_submit_query_plan",
                                "content": {
                                    "ok": True,
                                    "draft_plan_id": draft_id,
                                    "draft_plan_hash": "response_hash",
                                },
                            }
                        ],
                    }
                }
            }

            recovered = recover_n1f_hermes_draft_record(
                draft_id,
                bundle,
                output_root=output_root,
                hermes_workshop_root=output_root,
            )

            self.assertEqual("persisted_mcp_trace", recovered["draft_record_source"])
            self.assertEqual("submit_query_plan.arguments.plan_document", recovered["draft_document_source"])
            self.assertEqual("submit_query_plan.response.draft_plan_hash", recovered["draft_hash_source"])
            self.assertEqual("response_hash", recovered["draft_plan_hash"])
            self.assertEqual(document, recovered["document"])
            self.assertTrue(recovered["draft_lookup_errors"])


if __name__ == "__main__":
    unittest.main()
