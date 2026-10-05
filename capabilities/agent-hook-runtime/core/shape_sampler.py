"""Deterministic shape-lifecycle sampling and certification.

The sampler is a proof instrument, not a second hook engine. It replays a fixed
positive/negative matrix against the canonical protocol registry and records a
typed, privacy-safe receipt.

Four case kinds are supported:

- ``shape``     negotiate an observed wire shape and assert the selected profile,
                route state and lifecycle;
- ``config``    render a documented configuration dialect from canonical bindings;
- ``lifecycle`` validate a catalog/validation/proof/routing declaration;
- ``encode``    prove that an unadmitted response shape fails closed.

Binding certifications replay recorded version/shape bindings against the
current observation so stale evidence cannot authorize current auto switching.

Receipts retain structure, hashes, catalog/validation/proof/routing state and
evidence references only. Payload values never reach the receipt.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from core.protocol_fabric import (
    CATALOG_STATES,
    PROOF_CLASSES,
    ROUTING_ELIGIBILITIES,
    ROLLOUT_STAGES,
    VALIDATION_STATES,
    HookDecision,
    ProtocolFabricError,
    encode_decision,
    load_profiles,
    max_routing_eligibility,
    may_route,
    negotiate,
    render_config,
    validate_lifecycle,
)

MATRIX_SCHEMA = "agent-hook-shape-sampling-matrix/v1"
RECEIPT_SCHEMA = "agent-hook-shape-sampling-receipt/v1"
BINDING_SCHEMA = "agent-hook-version-shape-binding/v1"
BINDING_CERTIFICATION_SCHEMA = "agent-hook-binding-certification/v1"

CASE_KINDS = ("shape", "config", "lifecycle", "encode")
CASE_CLASSES = ("POSITIVE", "NEGATIVE")
BINDING_STATES = (
    "CURRENT",
    "CURRENT_WITH_PROOF_CEILING",
    "PROFILE_MISMATCH",
    "PROFILE_NOT_ROUTABLE",
    "STALE_SHAPE",
    "STALE_VERSION",
)
PROOF_ROUTING_CEILING = {
    "DOCUMENTED": "OBSERVE_ONLY",
    "SYNTHETIC": "CANARY_ELIGIBLE",
    "SHADOW_OBSERVED": "CANARY_ELIGIBLE",
    "LIVE_CANARY": "AUTO_SWITCH_ELIGIBLE",
}
_ROUTING_RANK = {name: index for index, name in enumerate(ROUTING_ELIGIBILITIES)}

RETAINED_RECEIPT_FIELDS = (
    "host family",
    "observed host/application version",
    "structural field names/types",
    "structural SHA-256",
    "candidate profile",
    "catalog state",
    "validation state",
    "proof class",
    "decoder result",
    "canonical event",
    "explicitly compatible response shapes",
    "routing eligibility",
    "evidence references",
)
EXCLUDED_RECEIPT_FIELDS = (
    "raw prompt text",
    "session IDs",
    "conversation IDs",
    "private workspace paths",
    "attachment content",
    "attachment paths",
    "arbitrary payload values",
    "credentials/secrets",
)


class ShapeSamplerError(ValueError):
    """Raised when a sampling matrix or registry entry is malformed."""


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_matrix(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ShapeSamplerError("sampling matrix must be an object")
    if value.get("schema_version") != MATRIX_SCHEMA:
        raise ShapeSamplerError("unsupported sampling matrix schema")
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ShapeSamplerError("sampling matrix must contain at least one case")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, Mapping):
            raise ShapeSamplerError("matrix case must be an object")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ShapeSamplerError("matrix case_id must be a non-empty string")
        if case_id in seen:
            raise ShapeSamplerError(f"duplicate case_id: {case_id}")
        seen.add(case_id)
        if case.get("class") not in CASE_CLASSES:
            raise ShapeSamplerError(f"case {case_id} has unsupported class")
        if case.get("kind", "shape") not in CASE_KINDS:
            raise ShapeSamplerError(f"case {case_id} has unsupported kind")
        if not isinstance(case.get("intent"), str) or not case["intent"].strip():
            raise ShapeSamplerError(f"case {case_id} requires a non-empty intent")
        if not isinstance(case.get("expect"), Mapping):
            raise ShapeSamplerError(f"case {case_id} requires an expect object")
        if case.get("kind", "shape") == "shape":
            payload = case.get("payload")
            if not isinstance(payload, Mapping):
                raise ShapeSamplerError(f"case {case_id} requires a payload object")
            for key in ("host_family", "canonical_event", "host_event"):
                if not isinstance(case.get(key), str) or not case[key]:
                    raise ShapeSamplerError(f"case {case_id} requires {key}")

    certifications = value.get("binding_certifications", [])
    if not isinstance(certifications, list):
        raise ShapeSamplerError("binding_certifications must be an array")
    for item in certifications:
        if not isinstance(item, Mapping):
            raise ShapeSamplerError("binding certification must be an object")
        if not isinstance(item.get("case_id"), str) or not item["case_id"].strip():
            raise ShapeSamplerError("binding certification requires case_id")
        if item.get("class") not in CASE_CLASSES:
            raise ShapeSamplerError("binding certification requires a supported class")
        if not isinstance(item.get("binding"), Mapping):
            raise ShapeSamplerError("binding certification requires a binding object")
        if not isinstance(item.get("current_observation"), Mapping):
            raise ShapeSamplerError("binding certification requires a current_observation")
        if not isinstance(item.get("expect"), Mapping):
            raise ShapeSamplerError("binding certification requires an expect object")
    return dict(value)


def _route_checks(route: Mapping[str, Any], expect: Mapping[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(key: str, description: str, satisfied: bool) -> None:
        checks.append(
            {
                "expectation": description,
                "expected": expect.get(key),
                "satisfied": bool(satisfied),
            }
        )

    if "route_state" in expect:
        add(
            "route_state",
            f"route state is {expect['route_state']}",
            route.get("state") == expect["route_state"],
        )
    if "reason" in expect:
        add("reason", f"route reason is {expect['reason']}", route.get("reason") == expect["reason"])
    if "selected_profile_id" in expect:
        selected = route.get("selected") or {}
        add(
            "selected_profile_id",
            f"selected profile is {expect['selected_profile_id']}",
            selected.get("profile_id") == expect["selected_profile_id"],
        )
    if expect.get("no_selection"):
        add("no_selection", "no profile was selected", route.get("selected") is None)
    if "selection_basis" in expect:
        add(
            "selection_basis",
            f"selection basis is {expect['selection_basis']}",
            route.get("selection_basis") == expect["selection_basis"],
        )
    lifecycle = route.get("lifecycle") or {}
    for key in ("catalog_state", "validation_state", "proof_class", "routing_eligibility", "rollout_stage"):
        if key in expect:
            add(
                key,
                f"selected {key} is {expect[key]}",
                lifecycle.get(key) == expect[key],
            )
    if "selected_not_profile_ids" in expect:
        selected = route.get("selected") or {}
        forbidden = list(expect["selected_not_profile_ids"])
        add(
            "selected_not_profile_ids",
            f"selected profile is not one of {forbidden}",
            selected.get("profile_id") not in forbidden,
        )
    if "observed_profile_ids" in expect:
        observed = [item["profile_id"] for item in route.get("observed_profiles", [])]
        wanted = list(expect["observed_profile_ids"])
        add(
            "observed_profile_ids",
            f"observed profiles include {wanted}",
            all(item in observed for item in wanted),
        )
    if "viable_profile_ids" in expect:
        viable = [
            item["profile_id"]
            for item in route.get("candidates", [])
            if not item.get("missing_required")
        ]
        wanted = list(expect["viable_profile_ids"])
        add(
            "viable_profile_ids",
            f"viable candidates include {wanted}",
            all(item in viable for item in wanted),
        )
    if "canary_confirmation_required" in expect:
        add(
            "canary_confirmation_required",
            f"canary confirmation required is {expect['canary_confirmation_required']}",
            route.get("canary_confirmation_required")
            is expect["canary_confirmation_required"],
        )
    if "response_shape" in expect:
        selected = route.get("selected") or {}
        add(
            "response_shape",
            f"negotiated response shape is {expect['response_shape']}",
            selected.get("response_shape") == expect["response_shape"],
        )
    if "fingerprint_field_types" in expect:
        fingerprint = (route.get("observation") or {}).get("fingerprint") or {}
        field_types = list(fingerprint.get("field_types", []))
        wanted = list(expect["fingerprint_field_types"])
        add(
            "fingerprint_field_types",
            f"structural fingerprint retains {wanted}",
            all(item in field_types for item in wanted),
        )
    if "lifecycle_safety" in expect:
        safety = route.get("lifecycle_safety") or {}
        for key, value in expect["lifecycle_safety"].items():
            checks.append(
                {
                    "expectation": f"lifecycle_safety.{key} is {value}",
                    "expected": value,
                    "satisfied": safety.get(key) == value,
                }
            )
    if "content_persisted" in expect:
        observation = route.get("observation") or {}
        add(
            "content_persisted",
            f"observation content_persisted is {expect['content_persisted']}",
            observation.get("content_persisted") is expect["content_persisted"],
        )
    return checks


def _evaluate_shape_case(
    registry: Mapping[str, Any],
    case: Mapping[str, Any],
) -> dict[str, Any]:
    expect = case["expect"]
    route = negotiate(
        load_profiles(registry),
        host_family=case["host_family"],
        canonical_event=case["canonical_event"],
        host_event=case["host_event"],
        payload=dict(case["payload"]),
        host_version=case.get("host_version"),
        failed_response_shapes=tuple(case.get("failed_response_shapes", ())),
        preferred_response_shapes=tuple(case.get("preferred_response_shapes", ())),
    )
    checks = _route_checks(route, expect)
    return {
        "route_state": route.get("state"),
        "route_reason": route.get("reason"),
        "selected_profile_id": (route.get("selected") or {}).get("profile_id"),
        "selection_basis": route.get("selection_basis"),
        "lifecycle": route.get("lifecycle"),
        "observation_fingerprint": (route.get("observation") or {}).get("fingerprint"),
        "explicitly_compatible_response_shapes": list(
            ((route.get("selected") or {}).get("response_shapes") or ())
        ),
        "checks": checks,
        "error": None,
    }


def _evaluate_config_case(case: Mapping[str, Any]) -> dict[str, Any]:
    expect = case["expect"]
    rendered = render_config(
        config_shape=case["config_shape"],
        bindings=list(case.get("bindings", ())),
    )
    checks: list[dict[str, Any]] = []
    host_events = sorted(rendered.get("hooks", {}))
    if "config_host_events" in expect:
        wanted = sorted(expect["config_host_events"])
        checks.append(
            {
                "expectation": f"rendered dialect exposes host events {wanted}",
                "expected": wanted,
                "satisfied": host_events == wanted,
            }
        )
    if "config_shape_version" in expect:
        checks.append(
            {
                "expectation": f"rendered dialect version is {expect['config_shape_version']}",
                "expected": expect["config_shape_version"],
                "satisfied": rendered.get("version") == expect["config_shape_version"],
            }
        )
    return {
        "route_state": "CONFIG_RENDERED",
        "route_reason": None,
        "selected_profile_id": case.get("config_shape"),
        "selection_basis": "DOCUMENTED_CONFIG_DIALECT",
        "lifecycle": None,
        "observation_fingerprint": None,
        "explicitly_compatible_response_shapes": [],
        "checks": checks,
        "error": None,
    }


def _evaluate_lifecycle_case(
    registry: Mapping[str, Any],
    case: Mapping[str, Any],
) -> dict[str, Any]:
    expect = case["expect"]
    checks: list[dict[str, Any]] = []
    declaration = case.get("lifecycle")
    profile_id = case.get("profile_id")
    resolved: Mapping[str, Any] | None = None
    if profile_id is not None:
        for profile in load_profiles(registry):
            if profile["profile_id"] == profile_id:
                resolved = profile["lifecycle"]
                break
        if resolved is None:
            raise ShapeSamplerError(f"unknown profile_id in lifecycle case: {profile_id}")
    elif declaration is None:
        raise ShapeSamplerError("lifecycle case requires profile_id or lifecycle")
    else:
        resolved = declaration

    error: str | None = None
    normalized: Mapping[str, Any] | None = None
    if expect.get("raises"):
        try:
            validate_lifecycle(resolved)
        except ProtocolFabricError as exc:
            error = str(exc)
        checks.append(
            {
                "expectation": "declaration is rejected by the lifecycle validator",
                "expected": "ProtocolFabricError",
                "satisfied": error is not None,
            }
        )
    else:
        normalized = validate_lifecycle(resolved)
        checks.append(
            {
                "expectation": "declaration is accepted by the lifecycle validator",
                "expected": "valid",
                "satisfied": True,
            }
        )
        for key in (
            "catalog_state",
            "validation_state",
            "proof_class",
            "routing_eligibility",
            "rollout_stage",
            "max_routing_eligibility",
        ):
            if key in expect:
                checks.append(
                    {
                        "expectation": f"{key} is {expect[key]}",
                        "expected": expect[key],
                        "satisfied": normalized.get(key) == expect[key],
                    }
                )
        if "degraded" in expect:
            checks.append(
                {
                    "expectation": f"degraded is {expect['degraded']}",
                    "expected": expect["degraded"],
                    "satisfied": normalized.get("degraded") is expect["degraded"],
                }
            )
        if "may_route" in expect:
            checks.append(
                {
                    "expectation": f"may_route is {expect['may_route']}",
                    "expected": expect["may_route"],
                    "satisfied": may_route(normalized) is expect["may_route"],
                }
            )
        if "max_routing_eligibility" not in expect and "routing_eligibility" in expect:
            checks.append(
                {
                    "expectation": "declared routing never exceeds its derived ceiling",
                    "expected": normalized["max_routing_eligibility"],
                    "satisfied": _ROUTING_RANK[normalized["routing_eligibility"]]
                    <= _ROUTING_RANK[normalized["max_routing_eligibility"]],
                }
            )

    return {
        "route_state": "LIFECYCLE_REJECTED" if error else "LIFECYCLE_VALID",
        "route_reason": error,
        "selected_profile_id": profile_id,
        "selection_basis": "LIFECYCLE_DECLARATION",
        "lifecycle": dict(normalized) if normalized is not None else None,
        "observation_fingerprint": None,
        "explicitly_compatible_response_shapes": [],
        "checks": checks,
        "error": error,
    }


def _evaluate_encode_case(registry: Mapping[str, Any], case: Mapping[str, Any]) -> dict[str, Any]:
    expect = case["expect"]
    decision_raw = dict(case.get("decision", {"action": "ALLOW"}))
    checks: list[dict[str, Any]] = []
    error: str | None = None
    response: Any = None
    try:
        response = encode_decision(
            load_profiles(registry),
            profile_id=case["profile_id"],
            response_shape=case["response_shape"],
            canonical_event=case["canonical_event"],
            decision=HookDecision(
                action=decision_raw["action"],
                message=decision_raw.get("message"),
                additional_context=decision_raw.get("additional_context"),
            ),
        )
    except ProtocolFabricError as exc:
        error = str(exc)

    if expect.get("raises"):
        checks.append(
            {
                "expectation": "unadmitted response shape fails closed",
                "expected": "ProtocolFabricError",
                "satisfied": error is not None,
            }
        )
    else:
        response_ok = error is None
        summary: dict[str, Any] = {}
        if "response_fields" in expect:
            fields = sorted(response or {})
            wanted = sorted(expect["response_fields"])
            summary["response_fields"] = wanted
            response_ok = response_ok and fields == wanted
            checks.append(
                {
                    "expectation": f"encoded response exposes fields {wanted}",
                    "expected": summary,
                    "satisfied": response_ok and fields == wanted,
                }
            )
        if "response_contains" in expect:
            wanted = dict(expect["response_contains"])
            summary["response_contains"] = wanted
            matches = isinstance(response, dict) and all(
                response.get(key) == value for key, value in wanted.items()
            )
            response_ok = response_ok and matches
            checks.append(
                {
                    "expectation": f"encoded response contains {sorted(wanted)}",
                    "expected": summary,
                    "satisfied": matches,
                }
            )
        if expect.get("reason_nonempty_string"):
            summary["reason_nonempty_string"] = True
            matches = isinstance(response, dict) and isinstance(response.get("reason"), str) and bool(
                response["reason"].strip()
            )
            response_ok = response_ok and matches
            checks.append(
                {
                    "expectation": "encoded response reason is a non-empty string",
                    "expected": summary,
                    "satisfied": matches,
                }
            )
        if not checks:
            checks.append(
                {
                    "expectation": "admitted response shape encodes",
                    "expected": "encoded",
                    "satisfied": response_ok,
                }
            )
    return {
        "route_state": "ENCODE_REJECTED" if error else "ENCODED",
        "route_reason": error,
        "selected_profile_id": case["profile_id"],
        "selection_basis": "ADMITTED_RESPONSE_SHAPE",
        "lifecycle": None,
        "observation_fingerprint": None,
        "explicitly_compatible_response_shapes": [case["response_shape"]],
        "checks": checks,
        "error": error,
    }


def certify_binding(
    binding: Mapping[str, Any],
    *,
    profile: Mapping[str, Any],
    current_observation: Mapping[str, Any],
) -> dict[str, Any]:
    """Certify one recorded version/shape binding against current evidence.

    A binding is evidence, never authority. Stale shape or version evidence
    always collapses to OBSERVE_ONLY so historical proof cannot authorize
    current automatic switching.
    """

    if not isinstance(binding, Mapping) or binding.get("schema_version") != BINDING_SCHEMA:
        raise ShapeSamplerError("unsupported version/shape binding schema")
    if profile.get("profile_id") != binding.get("profile_id"):
        raise ShapeSamplerError("binding profile_id does not match the supplied profile")

    lifecycle = profile["lifecycle"]
    proof_class = binding.get("proof_class", "DOCUMENTED")
    if proof_class not in PROOF_CLASSES:
        raise ShapeSamplerError(f"unsupported binding proof_class: {proof_class}")
    if not isinstance(current_observation, Mapping):
        raise ShapeSamplerError("current_observation must be an object")

    fingerprint = current_observation.get("fingerprint")
    if not isinstance(fingerprint, Mapping):
        raise ShapeSamplerError("current_observation requires a fingerprint")
    observed_shape = fingerprint.get("shape_sha256")
    if not isinstance(observed_shape, str) or not observed_shape:
        raise ShapeSamplerError("current_observation fingerprint requires shape_sha256")
    observed_version = current_observation.get("host_version")
    bound_version = binding.get("host_version")

    state = "CURRENT"
    reasons: list[str] = []
    if binding.get("shape_sha256") != observed_shape:
        state = "STALE_SHAPE"
        reasons.append("recorded shape fingerprint no longer matches current evidence")
    elif bound_version != observed_version:
        state = "STALE_VERSION"
        reasons.append("recorded host version no longer matches current evidence")
    elif not may_route(lifecycle):
        state = "PROFILE_NOT_ROUTABLE"
        reasons.append("bound profile does not carry routing eligibility")
    elif lifecycle["validation_state"] != "PASS":
        state = "PROFILE_NOT_ROUTABLE"
        reasons.append("bound profile validation state is not PASS")

    authorized = "OBSERVE_ONLY"
    if state in {"CURRENT", "CURRENT_WITH_PROOF_CEILING"}:
        ceiling = lifecycle["max_routing_eligibility"]
        proof_ceiling = PROOF_ROUTING_CEILING[proof_class]
        authorized = (
            ceiling if _ROUTING_RANK[ceiling] <= _ROUTING_RANK[proof_ceiling] else proof_ceiling
        )
        if _ROUTING_RANK[authorized] < _ROUTING_RANK[lifecycle["routing_eligibility"]]:
            state = "CURRENT_WITH_PROOF_CEILING"
            reasons.append(
                f"binding proof class {proof_class} caps routing at {authorized}"
            )

    return {
        "schema_version": BINDING_CERTIFICATION_SCHEMA,
        "state": state,
        "profile_id": binding.get("profile_id"),
        "host_family": binding.get("host_family"),
        "bound_host_version": bound_version,
        "observed_host_version": observed_version,
        "bound_shape_sha256": binding.get("shape_sha256"),
        "observed_shape_sha256": observed_shape,
        "binding_proof_class": proof_class,
        "catalog_state": lifecycle["catalog_state"],
        "validation_state": lifecycle["validation_state"],
        "declared_routing_eligibility": lifecycle["routing_eligibility"],
        "authorized_routing_eligibility": authorized,
        "reasons": reasons,
        "content_persisted": False,
        "proof_ceiling": (
            "Binding certification compares structural evidence only. It never converts "
            "historical or synthetic proof into live host acceptance."
        ),
    }


def _evaluate_binding_case(
    registry: Mapping[str, Any],
    case: Mapping[str, Any],
) -> dict[str, Any]:
    expect = case["expect"]
    profiles = {item["profile_id"]: item for item in load_profiles(registry)}
    profile_id = case["binding"].get("profile_id")
    if profile_id not in profiles:
        raise ShapeSamplerError(f"binding references unknown profile_id: {profile_id}")
    certification = certify_binding(
        case["binding"],
        profile=profiles[profile_id],
        current_observation=case["current_observation"],
    )
    checks: list[dict[str, Any]] = []
    for key in ("state", "authorized_routing_eligibility"):
        if key in expect:
            checks.append(
                {
                    "expectation": f"{key} is {expect[key]}",
                    "expected": expect[key],
                    "satisfied": certification[key] == expect[key],
                }
            )
    return {
        "route_state": certification["state"],
        "route_reason": "; ".join(certification["reasons"]) or None,
        "selected_profile_id": profile_id,
        "selection_basis": "VERSION_SHAPE_BINDING",
        "lifecycle": {
            "catalog_state": certification["catalog_state"],
            "validation_state": certification["validation_state"],
            "proof_class": certification["binding_proof_class"],
            "routing_eligibility": certification["authorized_routing_eligibility"],
        },
        "observation_fingerprint": case["current_observation"].get("fingerprint"),
        "explicitly_compatible_response_shapes": [],
        "checks": checks,
        "error": None,
    }


def _evaluate_case(
    registry: Mapping[str, Any],
    case: Mapping[str, Any],
) -> dict[str, Any]:
    kind = case.get("kind", "shape")
    if kind == "shape":
        return _evaluate_shape_case(registry, case)
    if kind == "config":
        return _evaluate_config_case(case)
    if kind == "lifecycle":
        return _evaluate_lifecycle_case(registry, case)
    if kind == "encode":
        return _evaluate_encode_case(registry, case)
    raise ShapeSamplerError(f"unsupported case kind: {kind}")


def _case_receipt(
    case: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    checks = list(result["checks"])
    verdict = "PASS" if checks and all(item["satisfied"] for item in checks) else "FAIL"
    if not checks:
        verdict = "FAIL"
    return {
        "case_id": case["case_id"],
        "class": case["class"],
        "kind": case.get("kind", "shape"),
        "intent": case["intent"],
        "host_family": case.get("host_family"),
        "canonical_event": case.get("canonical_event"),
        "host_event": case.get("host_event"),
        "route_state": result["route_state"],
        "route_reason": result["route_reason"],
        "selected_profile_id": result["selected_profile_id"],
        "selection_basis": result["selection_basis"],
        "lifecycle": result["lifecycle"],
        "observation_fingerprint": result["observation_fingerprint"],
        "explicitly_compatible_response_shapes": result[
            "explicitly_compatible_response_shapes"
        ],
        "checks": checks,
        "verdict": verdict,
        "error": result["error"],
    }


def run_sampling_matrix(
    registry: Mapping[str, Any],
    matrix: Mapping[str, Any],
) -> dict[str, Any]:
    """Replay the deterministic sampling matrix and emit a privacy-safe receipt."""

    validated_matrix = load_matrix(matrix)
    load_profiles(registry)

    receipts: list[dict[str, Any]] = []
    failures: list[str] = []
    for case in validated_matrix["cases"]:
        try:
            result = _evaluate_case(registry, case)
        except ShapeSamplerError as exc:
            result = {
                "route_state": "SAMPLER_ERROR",
                "route_reason": str(exc),
                "selected_profile_id": None,
                "selection_basis": None,
                "lifecycle": None,
                "observation_fingerprint": None,
                "explicitly_compatible_response_shapes": [],
                "checks": [],
                "error": str(exc),
            }
        receipt = _case_receipt(case, result)
        receipts.append(receipt)
        if receipt["verdict"] != "PASS":
            failures.append(case["case_id"])

    binding_receipts: list[dict[str, Any]] = []
    for case in validated_matrix.get("binding_certifications", ()):
        try:
            result = _evaluate_binding_case(registry, case)
        except ShapeSamplerError as exc:
            result = {
                "route_state": "SAMPLER_ERROR",
                "route_reason": str(exc),
                "selected_profile_id": None,
                "selection_basis": None,
                "lifecycle": None,
                "observation_fingerprint": None,
                "explicitly_compatible_response_shapes": [],
                "checks": [],
                "error": str(exc),
            }
        receipt = _case_receipt(case, result)
        binding_receipts.append(receipt)
        if receipt["verdict"] != "PASS":
            failures.append(case["case_id"])

    all_receipts = receipts + binding_receipts
    positive = [item for item in all_receipts if item["class"] == "POSITIVE"]
    negative = [item for item in all_receipts if item["class"] == "NEGATIVE"]
    positive_passed = [item for item in positive if item["verdict"] == "PASS"]
    negative_passed = [item for item in negative if item["verdict"] == "PASS"]

    if failures:
        sensitivity_state = "FAILED"
    elif not negative:
        sensitivity_state = "INSUFFICIENT"
    else:
        sensitivity_state = "SENSITIVE"

    overall = "PASS" if not failures and sensitivity_state == "SENSITIVE" else "FAIL"

    return {
        "schema_version": RECEIPT_SCHEMA,
        "capability_id": "agent-hook-runtime",
        "matrix_schema": validated_matrix["schema_version"],
        "deterministic": True,
        "registry_sha256": _canonical_sha256(registry),
        "matrix_sha256": _canonical_sha256(validated_matrix),
        "case_count": len(all_receipts),
        "failed_case_ids": sorted(failures),
        "sensitivity": {
            "positive_total": len(positive),
            "positive_passed": len(positive_passed),
            "negative_total": len(negative),
            "negative_passed": len(negative_passed),
            "state": sensitivity_state,
        },
        "state": overall,
        "cases": all_receipts,
        "privacy": {
            "raw_payload_values_persisted": False,
            "retained_fields": list(RETAINED_RECEIPT_FIELDS),
            "excluded_fields": list(EXCLUDED_RECEIPT_FIELDS),
            "reused_mechanism": "core.protocol_fabric.shape_fingerprint",
        },
        "vocabulary": {
            "catalog_states": list(CATALOG_STATES),
            "validation_states": list(VALIDATION_STATES),
            "proof_classes": list(PROOF_CLASSES),
            "routing_eligibilities": list(ROUTING_ELIGIBILITIES),
            "rollout_stages": list(ROLLOUT_STAGES),
        },
        "proof_ceiling": (
            "Synthetic deterministic sampling proves lifecycle validation, routing "
            "eligibility ceilings, privacy-safe receipts and negative-case sensitivity. "
            "It does not prove installed-host acceptance, shadow observation or live "
            "canary behavior."
        ),
    }


def receipt_json(receipt: Mapping[str, Any]) -> str:
    return json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


__all__ = [
    "BINDING_CERTIFICATION_SCHEMA",
    "CASE_CLASSES",
    "CASE_KINDS",
    "MATRIX_SCHEMA",
    "RECEIPT_SCHEMA",
    "ShapeSamplerError",
    "certify_binding",
    "load_matrix",
    "receipt_json",
    "run_sampling_matrix",
]
