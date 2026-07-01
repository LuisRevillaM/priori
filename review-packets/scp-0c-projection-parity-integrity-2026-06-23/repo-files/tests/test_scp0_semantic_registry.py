from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tqe.semantic_registry.generate import (
    build_plan_artifact_index,
    build_projections,
    generate_scp0_artifacts,
    generate_runtime_manifest,
    load_registry,
    make_registry_lock,
    validate_projection_identities,
    validate_registry,
)
from tqe.semantic_registry.models import AuthoringExposure, MaturityLevel


def finding_codes(findings) -> set[str]:
    return {finding.code for finding in findings}


class SCP0SemanticRegistryTests(unittest.TestCase):
    def test_scp0_generation_passes_and_excludes_atlas_from_product_and_ai(self) -> None:
        registry, runtime_manifest, lock, report = generate_scp0_artifacts(write=False)

        self.assertEqual("PASS", report.status)
        self.assertEqual(11, report.runtime_capabilities["bound"])
        self.assertEqual(19, report.runtime_capabilities["including_operators_total"])
        self.assertEqual(8, report.operators["semantically_defined"])
        self.assertEqual(4, report.recipes["mapped"])
        self.assertEqual(1, report.validated_compositions["mapped"])
        self.assertEqual({"product": 0, "ai": 0}, report.atlas_leakage)
        self.assertEqual(741, len(registry.atlas_entries))
        self.assertEqual(runtime_manifest["runtime_manifest_revision"], lock.runtime_manifest_revision)

    def test_runtime_capability_without_binding_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        registry.runtime_bindings = registry.runtime_bindings[:-1]
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("orphan_runtime_capability", codes)

    def test_binding_without_runtime_capability_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        registry.runtime_bindings[0].runtime_capability.id = "not_registered"
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("runtime_binding_missing_runtime_capability", codes)
        self.assertIn("orphan_runtime_capability", codes)

    def test_duplicate_runtime_binding_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        registry.runtime_bindings.append(copy.deepcopy(registry.runtime_bindings[0]))
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("duplicate_runtime_binding", codes)

    def test_missing_operator_definition_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        registry.operator_definitions = [
            item for item in registry.operator_definitions if item.operator_id != "gte"
        ]
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("operator_missing_definition", codes)
        self.assertIn("recipe_references_unregistered_operator", codes)

    def test_reviewed_plan_only_capability_cannot_enter_ai_projection(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        for policy in registry.exposure_policies:
            if policy.subject_ref == "runtime:primitive:outcome_classification:0.1.0":
                policy.ai_compiler = AuthoringExposure.ALLOWED
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("reviewed_plan_only_capability_exposed_to_ai", codes)

    def test_atlas_entry_cannot_be_product_or_ai_exposed(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        registry.atlas_entries[0].exposure_default = AuthoringExposure.ALLOWED
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("atlas_entry_exposure_not_denied", codes)

    def test_claim_contract_cannot_broaden_parent_prohibited_claim(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        child = next(
            item for item in registry.claim_contracts if item.id == "claim.high_bypass_completed_pass.v1"
        )
        child.permitted.append("defensive_line_was_broken")
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("claim_contract_broadens_parent", codes)

    def test_evidence_contract_cannot_remove_required_parent_evidence(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        child = next(
            item
            for item in registry.evidence_contracts
            if item.id == "evidence.high_bypass_completed_pass.v1"
        )
        child.required.remove("passer_id")
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("evidence_contract_removes_parent_required_evidence", codes)

    def test_projection_without_lock_identity_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        lock = make_registry_lock(registry, runtime_manifest)
        projections = build_projections(registry, runtime_manifest, lock)
        del projections["product"]["registry_lock"]

        codes = finding_codes(validate_projection_identities(projections, lock))

        self.assertIn("projection_missing_registry_lock", codes)

    def test_product_maturity_changed_to_not_exposed_changes_projection(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        for maturity in registry.maturity_assessments:
            if maturity.subject_ref == "runtime:primitive:controlled_pass_episode:0.1.0":
                maturity.product = MaturityLevel.NOT_EXPOSED
        lock = make_registry_lock(registry, runtime_manifest)

        projections = build_projections(registry, runtime_manifest, lock)
        product_ids = {item["id"] for item in projections["product"]["capabilities"]}

        self.assertNotIn("controlled_pass_episode", product_ids)

    def test_agent_safety_changed_to_not_reviewed_changes_ai_projection(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        for maturity in registry.maturity_assessments:
            if maturity.subject_ref == "runtime:primitive:controlled_pass_episode:0.1.0":
                maturity.agent_safety = MaturityLevel.NOT_REVIEWED
        lock = make_registry_lock(registry, runtime_manifest)

        projections = build_projections(registry, runtime_manifest, lock)
        ai_ids = {item["id"] for item in projections["ai"]["capabilities"]}

        self.assertNotIn("controlled_pass_episode", ai_ids)

    def test_projection_policy_exclusion_changes_projection(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        for policy in registry.projection_policies:
            if policy.target.value == "product":
                policy.excludes.append("runtime:primitive:controlled_pass_episode:0.1.0")
        lock = make_registry_lock(registry, runtime_manifest)

        projections = build_projections(registry, runtime_manifest, lock)
        product_ids = {item["id"] for item in projections["product"]["capabilities"]}

        self.assertNotIn("controlled_pass_episode", product_ids)

    def test_recipe_dependency_disagreement_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        recipe = next(
            item for item in registry.recipe_definitions if item.id == "recipe.high_bypass_completed_pass.v1"
        )
        recipe.dependency_refs.remove("opponents_bypassed_by_action")
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("recipe_dependency_mismatch", codes)

    def test_plan_threshold_change_without_profile_update_changes_lock_and_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        baseline_lock = make_registry_lock(registry, runtime_manifest)
        artifact = next(
            item for item in registry.plan_artifacts if item.id == "plan.high_bypass_completed_pass.v1"
        )
        payload = json.loads(Path(artifact.exact_typed_plan_ref).read_text(encoding="utf-8"))
        for parameter in payload["recipe"]["parameters"]:
            if parameter["name"] == "minimum_forward_progression_m":
                parameter["default"]["value"] = 9.0

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "high_bypass_modified.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            artifact.exact_typed_plan_ref = str(path)
            mutated_lock = make_registry_lock(registry, runtime_manifest)

            self.assertNotEqual(
                baseline_lock.plan_artifact_revision, mutated_lock.plan_artifact_revision
            )
            codes = finding_codes(validate_registry(registry, runtime_manifest, mutated_lock))

        self.assertIn("profile_binding_plan_parameter_mismatch", codes)

    def test_composition_cannot_point_to_arbitrary_valid_plan_file(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        artifact = next(
            item for item in registry.plan_artifacts if item.id == "plan.ai_corridor_destination.2026_06_23"
        )
        artifact.exact_typed_plan_ref = "config/query-plans/high_bypass_completed_pass.experimental.v1.json"
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("composition_artifact_not_origin_bundle", codes)

    def test_concept_missing_claim_contract_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        registry.concepts[0].claim_contract_ref = "claim.missing"
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("concept_missing_claim_contract", codes)

    def test_implementation_binding_operationalization_mismatch_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        registry.implementations[0].implements = ["op.event_seeded_tracking_confirmed_pass.v1"]
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("binding_implementation_operationalization_mismatch", codes)

    def test_duplicate_policy_subject_and_projection_target_fail(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        registry.exposure_policies.append(copy.deepcopy(registry.exposure_policies[0]))
        registry.projection_policies.append(copy.deepcopy(registry.projection_policies[0]))
        registry.projection_policies[-1].id = "projection.product.duplicate"
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("duplicate_exposure_subject", codes)
        self.assertIn("duplicate_projection_policy_target", codes)

    def test_transitive_claim_contradiction_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        child = next(
            item
            for item in registry.claim_contracts
            if item.id == "claim.ai_corridor_destination_composition.v1"
        )
        child.permitted.append("proves_pass_probability")
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("claim_contract_broadens_parent", codes)

    def test_operator_signature_disagreement_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        operator = next(item for item in registry.operator_definitions if item.operator_id == "gte")
        operator.output.value = "Scalar"
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("operator_signature_mismatch", codes)

    def test_pilot_paths_are_discovered_from_plan_artifacts(self) -> None:
        registry, _, _, report = generate_scp0_artifacts(write=False)

        high_bypass = report.pilots["high_bypass_completed_pass"]

        self.assertTrue(high_bypass["recipe_mapped"])
        self.assertEqual(
            ["controlled_pass_episode", "opponents_bypassed_by_action"],
            [item["capability"]["name"] for item in high_bypass["capability_paths"]],
        )
        self.assertTrue(high_bypass["plan_integrity"]["valid_typed_plan"])
        self.assertEqual(
            build_plan_artifact_index(registry)["plan_artifact_revision"],
            report.recipes["plan_artifact_revision"],
        )


if __name__ == "__main__":
    unittest.main()
