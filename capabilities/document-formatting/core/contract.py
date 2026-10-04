from __future__ import annotations

import hashlib
import json
from typing import Any

PROFILE_SCHEMA = "document-formatting-consumer-profile/v1"
PLAN_SCHEMA = "document-formatting-plan/v1"

HOSTS = {
    "CURRENT_CHAT_RUNTIME",
    "LOCAL_AGENT_RUNTIME",
    "CI_OR_REMOTE_RUNNER",
    "OPERATOR_OR_PHYSICAL_RUNTIME",
    "UNKNOWN_RUNTIME",
}


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any, *, field: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or not value:
        errors.append(f"{field} must be a non-empty array")
        return []
    result: list[str] = []
    for index, item in enumerate(value):
        if not _non_empty_string(item):
            errors.append(f"{field}[{index}] must be a non-empty string")
            continue
        result.append(item.strip())
    if len(result) != len(set(result)):
        errors.append(f"{field} must not contain duplicates")
    return result


def validate_profile(profile: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(profile, dict):
        return ["profile root must be an object"]

    if profile.get("schema_version") != PROFILE_SCHEMA:
        errors.append(f"schema_version must be {PROFILE_SCHEMA!r}")

    for field in ("consumer_id", "profile_id", "consumer_contract_ref"):
        if not _non_empty_string(profile.get(field)):
            errors.append(f"{field} must be a non-empty string")

    _string_list(profile.get("archetypes"), field="archetypes", errors=errors)

    providers = profile.get("provider_adapters")
    provider_ids: set[str] = set()
    if not isinstance(providers, list):
        errors.append("provider_adapters must be an array")
        providers = []
    for index, provider in enumerate(providers):
        prefix = f"provider_adapters[{index}]"
        if not isinstance(provider, dict):
            errors.append(f"{prefix} must be an object")
            continue
        provider_id = provider.get("provider_id")
        if not _non_empty_string(provider_id):
            errors.append(f"{prefix}.provider_id must be a non-empty string")
        elif provider_id in provider_ids:
            errors.append(f"{prefix}.provider_id must be unique")
        else:
            provider_ids.add(provider_id)
        host = provider.get("execution_environment")
        if host not in HOSTS:
            errors.append(f"{prefix}.execution_environment is invalid: {host!r}")
        features = provider.get("required_features", [])
        cleaned: list[str] = []
        if not isinstance(features, list):
            errors.append(f"{prefix}.required_features must be an array")
        else:
            for feature_index, feature in enumerate(features):
                if not _non_empty_string(feature):
                    errors.append(
                        f"{prefix}.required_features[{feature_index}] must be a non-empty string"
                    )
                else:
                    cleaned.append(feature)
            if len(cleaned) != len(set(cleaned)):
                errors.append(f"{prefix}.required_features must not contain duplicates")

        degradations = provider.get("accepted_degradations", [])
        if not isinstance(degradations, list):
            errors.append(f"{prefix}.accepted_degradations must be an array")
            degradations = []
        seen_degradations: set[str] = set()
        for degradation_index, degradation in enumerate(degradations):
            d_prefix = f"{prefix}.accepted_degradations[{degradation_index}]"
            if not isinstance(degradation, dict):
                errors.append(f"{d_prefix} must be an object")
                continue
            feature = degradation.get("feature")
            accepted_state = degradation.get("accepted_state")
            fallback_semantics = degradation.get("fallback_semantics")
            disclosure_required = degradation.get("disclosure_required")
            if not _non_empty_string(feature):
                errors.append(f"{d_prefix}.feature must be a non-empty string")
                continue
            if feature not in cleaned:
                errors.append(
                    f"{d_prefix}.feature must also appear in required_features"
                )
            if feature in seen_degradations:
                errors.append(f"{d_prefix}.feature must be unique")
            seen_degradations.add(feature)
            if not _non_empty_string(accepted_state):
                errors.append(f"{d_prefix}.accepted_state must be a non-empty string")
            if not _non_empty_string(fallback_semantics):
                errors.append(
                    f"{d_prefix}.fallback_semantics must be a non-empty string"
                )
            if not isinstance(disclosure_required, bool):
                errors.append(f"{d_prefix}.disclosure_required must be boolean")

    surfaces = profile.get("visual_surfaces")
    surface_ids: set[str] = set()
    if not isinstance(surfaces, list) or not surfaces:
        errors.append("visual_surfaces must be a non-empty array")
        surfaces = []
    for index, surface in enumerate(surfaces):
        prefix = f"visual_surfaces[{index}]"
        if not isinstance(surface, dict):
            errors.append(f"{prefix} must be an object")
            continue
        surface_id = surface.get("surface_id")
        if not _non_empty_string(surface_id):
            errors.append(f"{prefix}.surface_id must be a non-empty string")
        elif surface_id in surface_ids:
            errors.append(f"{prefix}.surface_id must be unique")
        else:
            surface_ids.add(surface_id)
        host = surface.get("execution_environment")
        if host not in HOSTS:
            errors.append(f"{prefix}.execution_environment is invalid: {host!r}")
        provider_id = surface.get("provider_id")
        if provider_id is not None and provider_id not in provider_ids:
            errors.append(f"{prefix}.provider_id must reference provider_adapters")

    policy = profile.get("proof_policy")
    if not isinstance(policy, dict):
        errors.append("proof_policy must be an object")
        policy = {}
    for field in (
        "provider_readback_required",
        "prevent_proof_promotion",
        "lock_non_color_before_branding",
    ):
        if not isinstance(policy.get(field), bool):
            errors.append(f"proof_policy.{field} must be boolean")

    branding = profile.get("branding")
    if not isinstance(branding, dict):
        errors.append("branding must be an object")
        branding = {}
    enabled = branding.get("enabled")
    if not isinstance(enabled, bool):
        errors.append("branding.enabled must be boolean")
    if enabled is True and policy.get("lock_non_color_before_branding") is not True:
        errors.append(
            "branding requires proof_policy.lock_non_color_before_branding=true"
        )

    return errors


def _canonical_profile(profile: dict[str, Any]) -> bytes:
    errors = validate_profile(profile)
    if errors:
        raise ValueError("; ".join(errors))
    return json.dumps(
        profile,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def profile_sha256(profile: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_profile(profile)).hexdigest()


def build_plan(profile: dict[str, Any]) -> dict[str, Any]:
    errors = validate_profile(profile)
    if errors:
        raise ValueError("; ".join(errors))

    stages: list[dict[str, Any]] = [
        {
            "stage_id": "VALIDATE_CONSUMER_PROFILE",
            "execution_environment": "LOCAL_AGENT_RUNTIME",
            "depends_on": [],
            "proof_ceiling": "PROFILE_VALIDATED",
        },
        {
            "stage_id": "COMPILE_PROVIDER_NEUTRAL_DOCUMENT",
            "execution_environment": "LOCAL_AGENT_RUNTIME",
            "depends_on": ["VALIDATE_CONSUMER_PROFILE"],
            "proof_ceiling": "PROVIDER_NEUTRAL_DOCUMENT_COMPILED",
        },
    ]

    provider_terminal: dict[str, str] = {}
    readback_required = profile["proof_policy"]["provider_readback_required"]
    for provider in profile["provider_adapters"]:
        provider_id = provider["provider_id"]
        apply_id = f"APPLY_PROVIDER::{provider_id}"
        stages.append(
            {
                "stage_id": apply_id,
                "execution_environment": provider["execution_environment"],
                "depends_on": ["COMPILE_PROVIDER_NEUTRAL_DOCUMENT"],
                "required_features": list(provider.get("required_features", [])),
                "accepted_degradations": [
                    dict(item) for item in provider.get("accepted_degradations", [])
                ],
                "proof_ceiling": "PROVIDER_MUTATION_ATTEMPTED",
            }
        )
        terminal = apply_id
        if readback_required:
            readback_id = f"READBACK_PROVIDER::{provider_id}"
            stages.append(
                {
                    "stage_id": readback_id,
                    "execution_environment": provider["execution_environment"],
                    "depends_on": [apply_id],
                    "required_features": list(provider.get("required_features", [])),
                    "accepted_degradations": [
                        dict(item) for item in provider.get("accepted_degradations", [])
                    ],
                    "proof_ceiling": "PROVIDER_READBACK_VERIFIED",
                }
            )
            terminal = readback_id
        provider_terminal[provider_id] = terminal

    visual_acceptance_ids: list[str] = []
    for surface in profile["visual_surfaces"]:
        surface_id = surface["surface_id"]
        acceptance_id = f"VISUAL_ACCEPTANCE::{surface_id}"
        provider_id = surface.get("provider_id")
        dependency = (
            provider_terminal[provider_id]
            if provider_id
            else "COMPILE_PROVIDER_NEUTRAL_DOCUMENT"
        )
        stages.append(
            {
                "stage_id": acceptance_id,
                "execution_environment": surface["execution_environment"],
                "depends_on": [dependency],
                "proof_ceiling": "VISUAL_ACCEPTED_ON_DECLARED_SURFACE",
            }
        )
        visual_acceptance_ids.append(acceptance_id)

    final_dependencies = list(visual_acceptance_ids)
    if len(visual_acceptance_ids) > 1:
        stages.append(
            {
                "stage_id": "CROSS_SURFACE_FIDELITY",
                "execution_environment": "LOCAL_AGENT_RUNTIME",
                "depends_on": list(visual_acceptance_ids),
                "proof_ceiling": "CROSS_SURFACE_FIDELITY_ACCEPTED",
            }
        )
        final_dependencies = ["CROSS_SURFACE_FIDELITY"]

    if profile["proof_policy"]["lock_non_color_before_branding"]:
        stages.append(
            {
                "stage_id": "LOCK_NON_COLOR_MECHANICS",
                "execution_environment": "LOCAL_AGENT_RUNTIME",
                "depends_on": final_dependencies,
                "proof_ceiling": "GENERIC_NON_COLOR_MECHANICS_LOCKED",
            }
        )
        final_dependencies = ["LOCK_NON_COLOR_MECHANICS"]

    if profile["branding"]["enabled"]:
        stages.append(
            {
                "stage_id": "APPLY_BRAND_OVERLAY",
                "execution_environment": "LOCAL_AGENT_RUNTIME",
                "depends_on": final_dependencies,
                "proof_ceiling": "BRAND_OVERLAY_CANDIDATE",
            }
        )
        final_dependencies = ["APPLY_BRAND_OVERLAY"]

    return {
        "schema_version": PLAN_SCHEMA,
        "capability_id": "document-formatting",
        "consumer_id": profile["consumer_id"],
        "profile_id": profile["profile_id"],
        "consumer_contract_ref": profile["consumer_contract_ref"],
        "profile_sha256": profile_sha256(profile),
        "state": "PLAN_READY",
        "prevent_proof_promotion": profile["proof_policy"]["prevent_proof_promotion"],
        "stages": stages,
        "terminal_dependencies": final_dependencies,
        "proof_ceiling": (
            "PLAN_ONLY_NO_PROVIDER_EXECUTION; provider mutation/readback and visual "
            "acceptance require their own stage evidence"
        ),
    }
