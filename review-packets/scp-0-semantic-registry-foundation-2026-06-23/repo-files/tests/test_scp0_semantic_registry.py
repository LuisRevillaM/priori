from __future__ import annotations

import copy
import unittest

from tqe.semantic_registry.generate import (
    build_projections,
    generate_scp0_artifacts,
    generate_runtime_manifest,
    load_registry,
    make_registry_lock,
    validate_projection_identities,
    validate_registry,
)
from tqe.semantic_registry.models import AuthoringExposure


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


if __name__ == "__main__":
    unittest.main()
