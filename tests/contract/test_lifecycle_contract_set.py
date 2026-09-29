"""Focused tests for the nine-schema lifecycle contract set.

Every test exercises the SDK's public validator (stdlib-only) against
minimal valid instances, cross-schema ``$ref`` resolution, invalid
inputs, conditional allOf/if-then, and the canonical schema digest.
"""

from pathlib import Path

import pytest

from skillweave_sdk.validator import (
    EXPECTED_SCHEMA_DIGEST,
    canonical_digest,
    load_registry,
    validate,
    verify_canonical_digest,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas"

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

LIFECYCLE_SCHEMA_IDS = {
    "work-profile": "https://skillweave.dev/schemas/lifecycle/work-profile/v1",
    "lifecycle-profile": "https://skillweave.dev/schemas/lifecycle/lifecycle-profile/v1",
    "deliverable-contract": "https://skillweave.dev/schemas/lifecycle/deliverable-contract/v1",
    "evidence-contract": "https://skillweave.dev/schemas/lifecycle/evidence-contract/v1",
    "category-pack": "https://skillweave.dev/schemas/lifecycle/category-pack/v1",
    "category-taxonomy": "https://skillweave.dev/schemas/lifecycle/category-taxonomy/v1",
    "model-provider": "https://skillweave.dev/schemas/lifecycle/model-provider/v1",
    "search-provider": "https://skillweave.dev/schemas/lifecycle/search-provider/v1",
    "subject-ref": "https://skillweave.dev/schemas/subject-ref/v1",
}


def _valid(name: str) -> dict:
    """Return a minimal valid instance for the named lifecycle schema."""
    fixtures = {
        "work-profile": {
            "contractVersion": "1.0.0",
            "id": "wp-build",
            "category": "build",
            "kernelStages": ["K1", "K2"],
        },
        "lifecycle-profile": {
            "contractVersion": "1.0.0",
            "id": "lp-dev",
            "phases": [
                {"id": "discover", "order": 1, "kernelStage": "K0"},
            ],
        },
        "deliverable-contract": {
            "contractVersion": "1.0.0",
            "id": "dc-api",
            "entrypoints": [
                {
                    "id": "ep-rest",
                    "surface": "code",
                    "acceptance": "All endpoints return 200",
                },
            ],
        },
        "evidence-contract": {
            "contractVersion": "1.0.0",
            "id": "ec-tests",
            "requirements": [
                {"id": "ut-cov", "kind": "coverage", "strength": "declared"},
            ],
        },
        "category-pack": {
            "contractVersion": "1.0.0",
            "id": "pack-build",
            "category": "build",
        },
        "category-taxonomy": {
            "contractVersion": "1.0.0",
            "categories": ["build"],
            "kernelStages": ["K0"],
            "topologies": ["linear"],
            "humanCoupling": ["autonomous"],
            "changeSurfaces": ["code"],
        },
        "model-provider": {
            "contractVersion": "1.0.0",
            "id": "mp-gpt4",
            "hostFrameworkIdentifier": "openai",
            "catalogueIdentifier": "gpt-4",
        },
        "search-provider": {
            "contractVersion": "1.0.0",
            "id": "sp-semantic",
            "hostFrameworkIdentifier": "semantic-scholar",
            "catalogueIdentifier": "api-v2",
        },
        "subject-ref": {
            "contractVersion": "1.0.0",
            "kind": "git",
            "repo": "org/repo",
            "commit": "abc123def456",
        },
    }
    return fixtures[name]


# ---------------------------------------------------------------------------
# registry & digest
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_all_thirteen_schemas_loaded(self):
        registry = load_registry(SCHEMAS)
        assert len(registry) >= 13

    def test_every_lifecycle_id_is_present(self):
        registry = load_registry(SCHEMAS)
        for sid in LIFECYCLE_SCHEMA_IDS.values():
            assert sid in registry, f"missing {sid}"


class TestDigest:
    def test_canonical_digest_matches_embedded(self):
        assert canonical_digest(SCHEMAS) == EXPECTED_SCHEMA_DIGEST

    def test_verify_canonical_digest_passes(self):
        verify_canonical_digest(SCHEMAS)  # raises on mismatch

    def test_verify_canonical_digest_rejects_bogus(self):
        with pytest.raises(Exception):
            verify_canonical_digest(SCHEMAS, expected="0" * 64)


# ---------------------------------------------------------------------------
# positive validation — each lifecycle schema
# ---------------------------------------------------------------------------


class TestPositiveValidation:
    def test_work_profile(self):
        errors = validate(_valid("work-profile"), LIFECYCLE_SCHEMA_IDS["work-profile"], SCHEMAS)
        assert errors == []

    def test_lifecycle_profile(self):
        errors = validate(_valid("lifecycle-profile"), LIFECYCLE_SCHEMA_IDS["lifecycle-profile"], SCHEMAS)
        assert errors == []

    def test_deliverable_contract(self):
        errors = validate(_valid("deliverable-contract"), LIFECYCLE_SCHEMA_IDS["deliverable-contract"], SCHEMAS)
        assert errors == []

    def test_evidence_contract(self):
        errors = validate(_valid("evidence-contract"), LIFECYCLE_SCHEMA_IDS["evidence-contract"], SCHEMAS)
        assert errors == []

    def test_category_pack(self):
        errors = validate(_valid("category-pack"), LIFECYCLE_SCHEMA_IDS["category-pack"], SCHEMAS)
        assert errors == []

    def test_category_taxonomy(self):
        errors = validate(_valid("category-taxonomy"), LIFECYCLE_SCHEMA_IDS["category-taxonomy"], SCHEMAS)
        assert errors == []

    def test_model_provider(self):
        errors = validate(_valid("model-provider"), LIFECYCLE_SCHEMA_IDS["model-provider"], SCHEMAS)
        assert errors == []

    def test_search_provider(self):
        errors = validate(_valid("search-provider"), LIFECYCLE_SCHEMA_IDS["search-provider"], SCHEMAS)
        assert errors == []

    def test_subject_ref_git(self):
        errors = validate(_valid("subject-ref"), LIFECYCLE_SCHEMA_IDS["subject-ref"], SCHEMAS)
        assert errors == []

    def test_subject_ref_site(self):
        instance = {
            "contractVersion": "1.0.0",
            "kind": "site",
            "siteId": "my-site",
        }
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["subject-ref"], SCHEMAS)
        assert errors == []

    def test_subject_ref_incident(self):
        instance = {
            "contractVersion": "1.0.0",
            "kind": "incident",
            "incidentId": "inc-42",
        }
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["subject-ref"], SCHEMAS)
        assert errors == []


# ---------------------------------------------------------------------------
# cross-schema $ref resolution
# ---------------------------------------------------------------------------


class TestCrossSchemaRef:
    def test_work_profile_refs_taxonomy_category(self):
        """work-profile.category is validated against taxonomy $defs/category."""
        instance = _valid("work-profile").copy()
        instance["category"] = "invalid-category"
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["work-profile"], SCHEMAS)
        assert errors != []

    def test_work_profile_refs_taxonomy_kernel_stage(self):
        instance = _valid("work-profile").copy()
        instance["kernelStages"] = ["K99"]
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["work-profile"], SCHEMAS)
        assert errors != []

    def test_lifecycle_profile_phase_refs_taxonomy_kernel_stage(self):
        instance = {
            "contractVersion": "1.0.0",
            "id": "lp-bad",
            "phases": [
                {"id": "p1", "order": 1, "kernelStage": "K99"},
            ],
        }
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["lifecycle-profile"], SCHEMAS)
        assert errors != []

    def test_deliverable_entrypoint_refs_taxonomy_surface(self):
        instance = {
            "contractVersion": "1.0.0",
            "id": "dc-bad",
            "entrypoints": [
                {"id": "ep1", "surface": "magic", "acceptance": "n/a"},
            ],
        }
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["deliverable-contract"], SCHEMAS)
        assert errors != []

    def test_evidence_requirement_refs_evidence_strength(self):
        instance = {
            "contractVersion": "1.0.0",
            "id": "ec-bad",
            "requirements": [
                {"id": "r1", "kind": "test", "strength": "guaranteed"},
            ],
        }
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["evidence-contract"], SCHEMAS)
        assert errors != []


# ---------------------------------------------------------------------------
# negative validation — missing required, invalid enums, extra props
# ---------------------------------------------------------------------------


class TestNegativeValidation:
    def test_work_profile_missing_contract_version(self):
        instance = _valid("work-profile").copy()
        del instance["contractVersion"]
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["work-profile"], SCHEMAS)
        assert errors != []

    def test_work_profile_wrong_contract_version(self):
        instance = _valid("work-profile").copy()
        instance["contractVersion"] = "2.0.0"
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["work-profile"], SCHEMAS)
        assert errors != []

    def test_lifecycle_profile_missing_phases(self):
        instance = _valid("lifecycle-profile").copy()
        del instance["phases"]
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["lifecycle-profile"], SCHEMAS)
        assert errors != []

    def test_deliverable_contract_missing_entrypoints(self):
        instance = _valid("deliverable-contract").copy()
        del instance["entrypoints"]
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["deliverable-contract"], SCHEMAS)
        assert errors != []

    def test_category_pack_missing_category(self):
        instance = _valid("category-pack").copy()
        del instance["category"]
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["category-pack"], SCHEMAS)
        assert errors != []

    def test_category_taxonomy_wrong_category_enum(self):
        instance = _valid("category-taxonomy").copy()
        instance["categories"] = ["bogus-category"]
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["category-taxonomy"], SCHEMAS)
        assert errors != []

    def test_model_provider_missing_id(self):
        instance = _valid("model-provider").copy()
        del instance["id"]
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["model-provider"], SCHEMAS)
        assert errors != []

    def test_search_provider_missing_catalogue_identifier(self):
        instance = _valid("search-provider").copy()
        del instance["catalogueIdentifier"]
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["search-provider"], SCHEMAS)
        assert errors != []

    def test_additional_property_rejected(self):
        instance = _valid("work-profile").copy()
        instance["unknownField"] = "should fail"
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["work-profile"], SCHEMAS)
        assert errors != []


# ---------------------------------------------------------------------------
# subject-ref allOf / if-then conditionals
# ---------------------------------------------------------------------------


class TestSubjectRefConditionals:
    def test_git_missing_repo(self):
        instance = {
            "contractVersion": "1.0.0",
            "kind": "git",
            "commit": "abc123",
        }
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["subject-ref"], SCHEMAS)
        assert errors != []

    def test_git_missing_commit(self):
        instance = {
            "contractVersion": "1.0.0",
            "kind": "git",
            "repo": "org/repo",
        }
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["subject-ref"], SCHEMAS)
        assert errors != []

    def test_git_missing_both(self):
        instance = {
            "contractVersion": "1.0.0",
            "kind": "git",
        }
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["subject-ref"], SCHEMAS)
        assert errors != []

    def test_site_missing_site_id(self):
        instance = {
            "contractVersion": "1.0.0",
            "kind": "site",
        }
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["subject-ref"], SCHEMAS)
        assert errors != []

    def test_page_missing_page_id(self):
        instance = {
            "contractVersion": "1.0.0",
            "kind": "page",
        }
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["subject-ref"], SCHEMAS)
        assert errors != []

    def test_content_item_missing_id(self):
        instance = {
            "contractVersion": "1.0.0",
            "kind": "content_item",
        }
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["subject-ref"], SCHEMAS)
        assert errors != []

    def test_configuration_missing_id(self):
        instance = {
            "contractVersion": "1.0.0",
            "kind": "configuration",
        }
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["subject-ref"], SCHEMAS)
        assert errors != []

    def test_deployment_missing_id(self):
        instance = {
            "contractVersion": "1.0.0",
            "kind": "deployment",
        }
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["subject-ref"], SCHEMAS)
        assert errors != []

    def test_incident_missing_id(self):
        instance = {
            "contractVersion": "1.0.0",
            "kind": "incident",
        }
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["subject-ref"], SCHEMAS)
        assert errors != []

    def test_invalid_kind_enum(self):
        instance = {
            "contractVersion": "1.0.0",
            "kind": "nonexistent",
        }
        errors = validate(instance, LIFECYCLE_SCHEMA_IDS["subject-ref"], SCHEMAS)
        assert errors != []
