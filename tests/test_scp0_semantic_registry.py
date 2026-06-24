from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tqe.semantic_registry import generate as scpgen
from tqe.semantic_registry.generate import (
    build_plan_artifact_index,
    build_projections,
    generate_scp0_artifacts,
    generate_runtime_manifest,
    load_registry,
    make_registry_lock,
    validate_projection_parity,
    validate_projection_identities,
    validate_registry,
)
from tqe.semantic_registry.models import AuthoringExposure, MaturityLevel
from tqe.semantic_registry.models import RuntimeInputBinding


def finding_codes(findings) -> set[str]:
    return {finding.code for finding in findings}


def runtime_capability(
    runtime_manifest: dict, *, kind: str, name: str, version: str = "0.1.0"
) -> dict:
    return next(
        item
        for item in runtime_manifest["capabilities"]
        if item["kind"] == kind and item["name"] == name and item["version"] == version
    )


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

    def test_projection_policy_requires_value_changes_projection(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        for policy in registry.projection_policies:
            if policy.target.value == "product":
                policy.requires["product_maturity"] = "NOT_EXPOSED"
        lock = make_registry_lock(registry, runtime_manifest)

        projections = build_projections(registry, runtime_manifest, lock)

        self.assertEqual([], projections["product"]["capabilities"])
        self.assertEqual([], projections["product"]["recipes"])
        self.assertEqual([], projections["product"]["validated_compositions"])

    def test_missing_baseline_file_fails_projection_parity(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        lock = make_registry_lock(registry, runtime_manifest)
        projections = build_projections(registry, runtime_manifest, lock)
        original_paths = scpgen.BASELINE_PATHS
        original_capability_path = scpgen.CAPABILITY_CATALOG_BASELINE_PATH
        try:
            scpgen.CAPABILITY_CATALOG_BASELINE_PATH = Path("generated/missing-baseline.json")
            scpgen.BASELINE_PATHS = {
                **original_paths,
                "capability_catalog": scpgen.CAPABILITY_CATALOG_BASELINE_PATH,
            }

            codes = finding_codes(
                validate_projection_parity(registry, runtime_manifest, projections)
            )
        finally:
            scpgen.CAPABILITY_CATALOG_BASELINE_PATH = original_capability_path
            scpgen.BASELINE_PATHS = original_paths

        self.assertIn("projection_baseline_missing", codes)

    def test_canonical_product_shared_records_have_no_contract_drift(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        lock = make_registry_lock(registry, runtime_manifest)
        projections = build_projections(registry, runtime_manifest, lock)

        differences = scpgen.build_projection_differences(runtime_manifest, projections)

        self.assertEqual([], differences["product"]["contract_changed"])
        self.assertEqual(15, differences["product"]["shared_count"])

    def test_unapproved_baseline_add_remove_or_contract_change_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        lock = make_registry_lock(registry, runtime_manifest)
        projections = build_projections(registry, runtime_manifest, lock)

        added_projection = copy.deepcopy(projections)
        added_projection["product"]["capabilities"].append(
            {
                "id": "fake_capability",
                "version": "0.1.0",
                "kind": "primitive",
                "runtime_contract": {
                    "kind": "primitive",
                    "name": "fake_capability",
                    "version": "0.1.0",
                    "inputs": [],
                    "outputs": [],
                    "parameters": [],
                    "evidence_fields": [],
                    "missing_data_semantics": "unknown",
                    "limitations": [],
                    "purpose": "fake",
                },
            }
        )
        removed_projection = copy.deepcopy(projections)
        removed_projection["product"]["capabilities"] = removed_projection["product"][
            "capabilities"
        ][1:]
        changed_projection = copy.deepcopy(projections)
        changed_projection["product"]["capabilities"][0]["runtime_contract"][
            "purpose"
        ] = "mutated purpose"

        self.assertIn(
            "projection_parity_unapproved_difference",
            finding_codes(validate_projection_parity(registry, runtime_manifest, added_projection)),
        )
        self.assertIn(
            "projection_parity_unapproved_difference",
            finding_codes(
                validate_projection_parity(registry, runtime_manifest, removed_projection)
            ),
        )
        self.assertIn(
            "projection_parity_unapproved_difference",
            finding_codes(
                validate_projection_parity(registry, runtime_manifest, changed_projection)
            ),
        )

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

    def test_recipe_omitting_profile_claim_or_evidence_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        recipe = next(
            item
            for item in registry.recipe_definitions
            if item.id == "recipe.opposite_corridor_after_shift.v1"
        )
        recipe.claim_contract_ref = "claim.ai_corridor_destination_composition.v1"
        recipe.evidence_contract_ref = "evidence.ai_corridor_destination_composition.v1"
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("recipe_claim_omits_profile_contract", codes)
        self.assertIn("recipe_evidence_omits_profile_contract", codes)

    def test_every_recipe_and_composition_requires_top_level_concept(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        registry.recipe_definitions[0].concept_ref = "concept.missing"
        registry.composition_instances[0].concept_ref = "concept.missing"
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("recipe_missing_concept", codes)
        self.assertIn("composition_missing_concept", codes)

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

    def test_origin_bundle_byte_change_changes_source_artifact_hash(self) -> None:
        registry = load_registry()
        artifact = next(
            item
            for item in registry.plan_artifacts
            if item.id == "plan.ai_corridor_destination.2026_06_23"
        )
        baseline = build_plan_artifact_index(registry)["artifacts"][artifact.id]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "n1f-origin-bundle.json"
            path.write_text(
                Path(artifact.exact_typed_plan_ref).read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            artifact.exact_typed_plan_ref = str(path)
            changed = build_plan_artifact_index(registry)["artifacts"][artifact.id]

        self.assertNotEqual(
            baseline["source_artifact_sha256"],
            changed["source_artifact_sha256"],
        )
        self.assertEqual(
            baseline["normalized_selected_document_hash"],
            changed["normalized_selected_document_hash"],
        )

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

    def test_composition_with_unbound_capability_or_undefined_operator_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        artifact = next(
            item
            for item in registry.plan_artifacts
            if item.id == "plan.ai_corridor_destination.2026_06_23"
        )
        payload = json.loads(Path(artifact.exact_typed_plan_ref).read_text(encoding="utf-8"))
        document = payload["host_augmentation"]["augmented_document"]
        document["draft_plan"]["nodes"][0]["catalog_ref"] = "missing_capability"
        document["draft_plan"]["nodes"][-1]["operator"]["name"] = "missing_operator"

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "n1f-origin-bundle-mutated.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            artifact.exact_typed_plan_ref = str(path)
            lock = make_registry_lock(registry, runtime_manifest)
            codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("composition_references_unbound_runtime_capability", codes)
        self.assertIn("composition_references_unregistered_operator", codes)

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

    def test_exact_binding_missing_runtime_or_semantic_port_or_parameter_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        op = next(
            item
            for item in registry.operationalizations
            if item.id == "op.relation_destination_entry.v1"
        )
        op.outputs[0].name = "missing_runtime_output"
        binding = next(
            item
            for item in registry.runtime_bindings
            if item.id == "binding.primitive.relation_destination_entry.0_1_0"
        )
        del binding.parameter_bindings["episode_selection"]
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("runtime_signature_mismatch", codes)
        self.assertIn("runtime_parameter_signature_mismatch", codes)

    def test_exact_binding_unbound_required_semantic_context_input_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        binding = next(
            item
            for item in registry.runtime_bindings
            if item.id == "binding.primitive.possession_segment.0_1_0"
        )
        binding.input_bindings = {}
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("runtime_signature_mismatch", codes)

    def test_unknown_runtime_context_ref_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        binding = next(
            item
            for item in registry.runtime_bindings
            if item.id == "binding.primitive.possession_segment.0_1_0"
        )
        binding.input_bindings["canonical_match_state"].context_ref = (
            "fake.context.that.does.not.exist"
        )
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("runtime_context_signature_mismatch", codes)

    def test_runtime_input_binding_source_targets_are_exclusive(self) -> None:
        with self.assertRaises(ValueError):
            RuntimeInputBinding.model_validate(
                {
                    "source": "RUNTIME_CONTEXT",
                    "context_ref": "canonical_match_state",
                    "runtime_port": "canonical_match_state",
                }
            )
        with self.assertRaises(ValueError):
            RuntimeInputBinding.model_validate(
                {
                    "source": "NODE_INPUT",
                    "runtime_port": "anchors",
                    "context_ref": "canonical_match_state",
                }
            )

    def test_exact_field_unit_entity_scope_cardinality_and_requiredness_drift_fail(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        signed_shift = runtime_capability(
            runtime_manifest, kind="primitive", name="signed_lateral_shift"
        )
        signed_shift["outputs"][0]["unit"] = "none"
        signed_shift["outputs"][0]["cardinality"] = "collection"
        signed_shift["inputs"][2]["entity_scope"] = "player"
        signed_shift["inputs"][2]["required"] = False
        lock = make_registry_lock(registry, runtime_manifest)

        findings = validate_registry(registry, runtime_manifest, lock)
        messages = "\n".join(finding.message for finding in findings)

        self.assertIn("runtime_signature_mismatch", finding_codes(findings))
        self.assertIn("unit metre != none", messages)
        self.assertIn("cardinality single != collection", messages)
        self.assertIn("entity_scope team != player", messages)
        self.assertIn("required True != False", messages)

    def test_exact_parameter_bounds_default_and_allowed_value_drift_fail(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        relation_entry = runtime_capability(
            runtime_manifest, kind="primitive", name="relation_destination_entry"
        )
        for parameter in relation_entry["parameters"]:
            if parameter["name"] == "destination_entry_horizon_seconds":
                parameter["minimum"] = 0.3
            if parameter["name"] == "episode_selection":
                parameter["allowed_values"] = ["first_by_duration_clearance"]
            if parameter["name"] == "result_id_seed":
                parameter["default"] = {
                    "payload_type": "enum",
                    "value": "unexpected",
                    "unit": "none",
                }
        lock = make_registry_lock(registry, runtime_manifest)

        findings = validate_registry(registry, runtime_manifest, lock)
        messages = "\n".join(finding.message for finding in findings)

        self.assertIn("runtime_parameter_signature_mismatch", finding_codes(findings))
        self.assertIn("minimum 0.2 != 0.3", messages)
        self.assertIn(
            "allowed_values ['entry_first_then_progression', 'first_by_duration_clearance'] != ['first_by_duration_clearance']",
            messages,
        )
        self.assertIn("default None !=", messages)

    def test_partial_binding_nonexistent_mapping_key_or_target_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        binding = next(
            item
            for item in registry.runtime_bindings
            if item.id == "binding.primitive.controlled_pass_episode.0_1_0"
        )
        binding.output_bindings["anchors"].runtime_port = "not_a_runtime_output"
        binding.input_bindings["not_a_semantic_input"] = copy.deepcopy(
            binding.input_bindings["candidate_pass_events"]
        )
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("runtime_signature_mismatch", codes)

    def test_partial_binding_unmapped_runtime_parameter_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        binding = next(
            item
            for item in registry.runtime_bindings
            if item.id == "binding.primitive.controlled_pass_episode.0_1_0"
        )
        del binding.parameter_bindings["release_search_before_seconds"]
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("runtime_parameter_signature_mismatch", codes)

    def test_unknown_uncovered_runtime_or_semantic_field_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        binding = next(
            item
            for item in registry.runtime_bindings
            if item.id == "binding.primitive.controlled_pass_episode.0_1_0"
        )
        binding.uncovered_runtime_outputs.append("not_a_real_runtime_output")
        binding.uncovered_semantic_inputs.append("not_a_real_semantic_input")
        binding.uncovered_runtime_outputs.append("not_a_real_runtime_output")
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("runtime_uncovered_field_mismatch", codes)

    def test_exact_parameter_binding_to_missing_semantic_target_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        binding = next(
            item
            for item in registry.runtime_bindings
            if item.id == "binding.primitive.relation_destination_entry.0_1_0"
        )
        binding.parameter_bindings["episode_selection"] = "missing_semantic_parameter"
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("runtime_parameter_signature_mismatch", codes)

    def test_pinned_waiver_fails_when_projection_hash_changes(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        lock = make_registry_lock(registry, runtime_manifest)
        projections = build_projections(registry, runtime_manifest, lock)
        projections["ai"]["recipes"][0]["plan_integrity"]["normalized_plan_hash"] = "mutated"

        codes = finding_codes(validate_projection_parity(registry, runtime_manifest, projections))

        self.assertIn("projection_parity_waiver_hash_mismatch", codes)

    def test_unused_or_stale_parity_waiver_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        lock = make_registry_lock(registry, runtime_manifest)
        projections = build_projections(registry, runtime_manifest, lock)
        ai_policy = next(item for item in registry.projection_policies if item.target.value == "ai")
        stale = copy.deepcopy(ai_policy.accepted_differences[0])
        stale.subject_ref = "recipe:not_currently_different:1.0.0"
        ai_policy.accepted_differences.append(stale)

        codes = finding_codes(validate_projection_parity(registry, runtime_manifest, projections))

        self.assertIn("projection_parity_stale_waiver", codes)

    def test_duplicate_waiver_key_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        ai_policy = next(item for item in registry.projection_policies if item.target.value == "ai")
        ai_policy.accepted_differences.append(copy.deepcopy(ai_policy.accepted_differences[0]))
        lock = make_registry_lock(registry, runtime_manifest)
        projections = build_projections(registry, runtime_manifest, lock)

        registry_codes = finding_codes(validate_registry(registry, runtime_manifest, lock))
        parity_codes = finding_codes(
            validate_projection_parity(registry, runtime_manifest, projections)
        )

        self.assertIn("projection_parity_duplicate_waiver", registry_codes)
        self.assertIn("projection_parity_duplicate_waiver", parity_codes)

    def test_accepted_composition_content_change_with_same_id_fails(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        lock = make_registry_lock(registry, runtime_manifest)
        projections = build_projections(registry, runtime_manifest, lock)
        projections["product"]["validated_compositions"][0]["plan_integrity"][
            "normalized_plan_hash"
        ] = "mutated"

        codes = finding_codes(validate_projection_parity(registry, runtime_manifest, projections))

        self.assertIn("projection_parity_waiver_hash_mismatch", codes)

    def test_composition_circular_concept_contract_cannot_omit_dependency_contract(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        concept = next(
            item
            for item in registry.concepts
            if item.id == "concept.progressive_connection_followed_by_destination_entry"
        )
        composition = registry.composition_instances[0]
        concept.claim_contract_ref = "claim.progressive_connection_availability.v1"
        concept.evidence_contract_ref = "evidence.progressive_connection_availability.v1"
        composition.claim_contract_ref = "claim.progressive_connection_availability.v1"
        composition.evidence_contract_ref = "evidence.progressive_connection_availability.v1"
        lock = make_registry_lock(registry, runtime_manifest)

        codes = finding_codes(validate_registry(registry, runtime_manifest, lock))

        self.assertIn("composition_claim_omits_dependency_contract", codes)
        self.assertIn("composition_evidence_omits_dependency_contract", codes)

    def test_ai_projection_policy_exclusion_removes_operator(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        for policy in registry.projection_policies:
            if policy.target.value == "ai":
                policy.excludes.append("operator:gte:1.0.0")
        lock = make_registry_lock(registry, runtime_manifest)

        projections = build_projections(registry, runtime_manifest, lock)
        ai_operator_ids = {item["id"] for item in projections["ai"]["operators"]}

        self.assertNotIn("gte", ai_operator_ids)

    def test_unsupported_projection_policy_changes_unsupported_projection(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        baseline_lock = make_registry_lock(registry, runtime_manifest)
        baseline = build_projections(registry, runtime_manifest, baseline_lock)
        unsupported_subject = (
            f"runtime:{baseline['unsupported']['items'][0]['kind']}:"
            f"{baseline['unsupported']['items'][0]['id']}:"
            f"{baseline['unsupported']['items'][0]['version']}"
        )
        for policy in registry.projection_policies:
            if policy.target.value == "unsupported":
                policy.excludes.append(unsupported_subject)
        lock = make_registry_lock(registry, runtime_manifest)

        changed = build_projections(registry, runtime_manifest, lock)

        self.assertEqual(
            len(baseline["unsupported"]["items"]) - 1,
            len(changed["unsupported"]["items"]),
        )

    def test_product_recipe_parity_reports_current_runtime_alignment_mode(self) -> None:
        registry = load_registry()
        runtime_manifest = generate_runtime_manifest()
        lock = make_registry_lock(registry, runtime_manifest)
        projections = build_projections(registry, runtime_manifest, lock)

        differences = scpgen.build_projection_differences(runtime_manifest, projections)

        self.assertEqual(
            "current_runtime_alignment",
            differences["product"]["recipe_contract_baseline_mode"],
        )
        self.assertFalse(differences["product"]["recipe_contract_frozen_baseline"])

    def test_failed_generation_leaves_last_valid_projection_untouched(self) -> None:
        registry = load_registry()
        registry.runtime_bindings = registry.runtime_bindings[:-1]
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = Path(tmp) / "registry.yaml"
            output_root = Path(tmp) / "generated"
            output_root.mkdir()
            product_projection = output_root / "product-projection.json"
            product_projection.write_text('{"sentinel": true}\n', encoding="utf-8")
            payload = registry.model_dump(mode="json", exclude_none=True)
            payload["atlas_entries"] = []
            registry_path.write_text(json.dumps(payload), encoding="utf-8")

            _, _, _, report = generate_scp0_artifacts(
                registry_path=registry_path, output_root=output_root, write=True
            )

            self.assertEqual("FAIL", report.status)
            self.assertEqual('{"sentinel": true}\n', product_projection.read_text(encoding="utf-8"))

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
