"""Versioned, host-neutral hook protocol negotiation and response encoding.

The fabric separates:
- host transport and config dialect;
- event wire shape;
- canonical event semantics;
- response wire shape;
- host/application version evidence.

A host version is evidence, not authority. A live payload fingerprint may select a
different compatible shape when a host update lands before the registry is refreshed.

Hybridization happens only through the canonical IR: decode with one admitted
profile, apply policy to the canonical event, then encode through another response
shape that the selected host profile explicitly declares compatible.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence

PROFILE_SCHEMA = "agent-hook-protocol-profile/v1"
OBSERVATION_SCHEMA = "agent-hook-shape-observation/v1"
ROUTE_SCHEMA = "agent-hook-route-plan/v1"

_TYPE_NAMES = {
    str: "string",
    bool: "boolean",
    int: "integer",
    float: "number",
    list: "array",
    dict: "object",
    type(None): "null",
}

CANONICAL_EVENTS = {
    "session.start",
    "prompt.submit",
    "tool.pre",
    "tool.post",
    "compact.pre",
    "session.stop",
}

DECISION_ACTIONS = {"ALLOW", "BLOCK", "FOLLOW_UP", "CONTEXT"}

LIFECYCLE_SCHEMA = "agent-hook-shape-lifecycle/v1"

CATALOG_STATES = ("LEGACY", "ACTIVE", "PROSPECTIVE")
VALIDATION_STATES = ("UNTESTED", "PASS", "FAIL", "BLOCKED")
PROOF_CLASSES = ("DOCUMENTED", "SYNTHETIC", "SHADOW_OBSERVED", "LIVE_CANARY")
ROUTING_ELIGIBILITIES = (
    "OBSERVE_ONLY",
    "CANARY_ELIGIBLE",
    "AUTO_SWITCH_ELIGIBLE",
    "RETIRED",
)
ROLLOUT_STAGES = (
    "DISCOVERED",
    "PROFILED",
    "SYNTHETIC_PROVEN",
    "SHADOW_OBSERVED",
    "CANARY_ACCEPTED",
    "AUTO_SWITCH_ELIGIBLE",
)

ROUTING_RANK = {
    "OBSERVE_ONLY": 0,
    "CANARY_ELIGIBLE": 1,
    "AUTO_SWITCH_ELIGIBLE": 2,
    "RETIRED": -1,
}
CATALOG_RANK = {"ACTIVE": 0, "LEGACY": 1, "PROSPECTIVE": 2}
PROOF_RANK = {
    "DOCUMENTED": 0,
    "SYNTHETIC": 1,
    "SHADOW_OBSERVED": 2,
    "LIVE_CANARY": 3,
}
STAGE_PROOF_FLOOR = {
    "DISCOVERED": 0,
    "PROFILED": 0,
    "SYNTHETIC_PROVEN": 1,
    "SHADOW_OBSERVED": 2,
    "CANARY_ACCEPTED": 3,
    "AUTO_SWITCH_ELIGIBLE": 3,
}
ROUTABLE_ROUTING_STATES = frozenset({"CANARY_ELIGIBLE", "AUTO_SWITCH_ELIGIBLE"})
REJECTED_VALIDATION_STATES = frozenset({"FAIL", "BLOCKED"})


class ProtocolFabricError(ValueError):
    """Raised when a tracked protocol contract is malformed or unsafe to use."""


@dataclass(frozen=True)
class HookDecision:
    action: str
    message: str | None = None
    additional_context: str | None = None
    updated_input: Mapping[str, Any] | None = None

    def validate(self) -> None:
        if self.action not in DECISION_ACTIONS:
            raise ProtocolFabricError(f"unsupported decision action: {self.action}")
        if self.action in {"BLOCK", "FOLLOW_UP"} and not self.message:
            raise ProtocolFabricError(f"{self.action} requires message")
        if self.action == "CONTEXT" and not self.additional_context:
            raise ProtocolFabricError("CONTEXT requires additional_context")


@dataclass(frozen=True)
class Candidate:
    profile_id: str
    shape_version: str
    canonical_event: str
    host_event: str
    score: int
    version_match: str
    required_fields: tuple[str, ...]
    missing_required: tuple[str, ...]
    response_shapes: tuple[str, ...]


def _typename(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    for typ, name in _TYPE_NAMES.items():
        if typ is bool:
            continue
        if isinstance(value, typ):
            return name
    return type(value).__name__


def shape_fingerprint(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a privacy-safe structural fingerprint; values are never persisted."""

    if not isinstance(payload, Mapping):
        raise ProtocolFabricError("payload must be an object")
    fields = [f"{key}:{_typename(payload[key])}" for key in sorted(payload)]
    serialized = "\n".join(fields).encode("utf-8")
    return {
        "field_types": fields,
        "shape_sha256": hashlib.sha256(serialized).hexdigest(),
        "field_count": len(fields),
        "content_persisted": False,
    }


_VERSION_RE = re.compile(r"\d+")


def _version_tuple(value: str | None) -> tuple[int, ...] | None:
    if not value or not isinstance(value, str):
        return None
    parts = tuple(int(item) for item in _VERSION_RE.findall(value))
    return parts or None


def _cmp_versions(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    width = max(len(left), len(right))
    a = left + (0,) * (width - len(left))
    b = right + (0,) * (width - len(right))
    return (a > b) - (a < b)


def _version_match(profile: Mapping[str, Any], host_version: str | None) -> str:
    evidence = profile.get("host_version_evidence", {})
    if not isinstance(evidence, Mapping):
        raise ProtocolFabricError("host_version_evidence must be an object")

    observed = evidence.get("observed_versions", [])
    if observed is None:
        observed = []
    if not isinstance(observed, list) or not all(isinstance(item, str) for item in observed):
        raise ProtocolFabricError("observed_versions must be an array of strings")
    if host_version and host_version in observed:
        return "EXACT_OBSERVED"

    parsed = _version_tuple(host_version)
    minimum = _version_tuple(evidence.get("min"))
    maximum = _version_tuple(evidence.get("max"))
    if parsed is None:
        return "UNKNOWN"
    if minimum is not None and _cmp_versions(parsed, minimum) < 0:
        return "OUTSIDE_RANGE"
    if maximum is not None and _cmp_versions(parsed, maximum) > 0:
        return "OUTSIDE_RANGE"
    if minimum is not None or maximum is not None:
        return "IN_RANGE"
    return "UNBOUND"


def _check_field_type(value: Any, expected: str) -> bool:
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    mapping = {
        "string": str,
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }
    typ = mapping.get(expected)
    if typ is None:
        raise ProtocolFabricError(f"unsupported field type in profile: {expected}")
    return isinstance(value, typ)


def max_routing_eligibility(lifecycle: Mapping[str, Any]) -> str:
    """Return the strongest routing eligibility a lifecycle declaration may claim.

    Catalog state and proof strength are orthogonal but they do not stack:
    documentation is never proof, a passing prospective candidate never becomes
    auto-switch material, and a legacy shape is never auto-switch material
    because it still happens to validate.
    """

    catalog = lifecycle["catalog_state"]
    validation = lifecycle["validation_state"]
    proof = lifecycle["proof_class"]
    admitted = lifecycle.get("compatibility_admitted", False) is True

    if validation != "PASS":
        return "OBSERVE_ONLY"

    if proof == "LIVE_CANARY":
        ceiling = "AUTO_SWITCH_ELIGIBLE"
    elif proof in {"SYNTHETIC", "SHADOW_OBSERVED"}:
        ceiling = "CANARY_ELIGIBLE"
    else:
        ceiling = "OBSERVE_ONLY"

    if catalog == "PROSPECTIVE" and ROUTING_RANK[ceiling] > ROUTING_RANK["CANARY_ELIGIBLE"]:
        return "CANARY_ELIGIBLE"
    if catalog == "LEGACY":
        if not admitted:
            return "OBSERVE_ONLY"
        if ROUTING_RANK[ceiling] > ROUTING_RANK["CANARY_ELIGIBLE"]:
            return "CANARY_ELIGIBLE"
    return ceiling


def _is_degraded_active(lifecycle: Mapping[str, Any]) -> bool:
    return (
        lifecycle["catalog_state"] == "ACTIVE"
        and lifecycle["validation_state"] in REJECTED_VALIDATION_STATES
    )


def validate_lifecycle(lifecycle: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one profile's catalog/validation/proof/routing declaration."""

    if not isinstance(lifecycle, Mapping):
        raise ProtocolFabricError("lifecycle must be an object")
    required = {
        "catalog_state",
        "validation_state",
        "proof_class",
        "routing_eligibility",
        "rollout_stage",
        "compatibility_admitted",
    }
    missing = sorted(required - set(lifecycle))
    if missing:
        raise ProtocolFabricError("lifecycle missing fields: " + ", ".join(missing))

    catalog = lifecycle["catalog_state"]
    validation = lifecycle["validation_state"]
    proof = lifecycle["proof_class"]
    routing = lifecycle["routing_eligibility"]
    stage = lifecycle["rollout_stage"]
    admitted = lifecycle["compatibility_admitted"]

    if catalog not in CATALOG_STATES:
        raise ProtocolFabricError(f"unsupported catalog_state: {catalog}")
    if validation not in VALIDATION_STATES:
        raise ProtocolFabricError(f"unsupported validation_state: {validation}")
    if proof not in PROOF_CLASSES:
        raise ProtocolFabricError(f"unsupported proof_class: {proof}")
    if routing not in ROUTING_ELIGIBILITIES:
        raise ProtocolFabricError(f"unsupported routing_eligibility: {routing}")
    if stage not in ROLLOUT_STAGES:
        raise ProtocolFabricError(f"unsupported rollout_stage: {stage}")
    if not isinstance(admitted, bool):
        raise ProtocolFabricError("lifecycle.compatibility_admitted must be a boolean")

    for key in ("quarantined", "retained_negative_evidence"):
        if key in lifecycle and not isinstance(lifecycle[key], bool):
            raise ProtocolFabricError(f"lifecycle.{key} must be a boolean")
    if "superseded_by" in lifecycle and lifecycle["superseded_by"] is not None:
        superseded_by = lifecycle["superseded_by"]
        if not isinstance(superseded_by, str) or not superseded_by.strip():
            raise ProtocolFabricError("lifecycle.superseded_by must be null or a non-empty string")
    if "note" in lifecycle and not isinstance(lifecycle["note"], str):
        raise ProtocolFabricError("lifecycle.note must be a string")

    if validation == "PASS" and proof == "DOCUMENTED":
        raise ProtocolFabricError(
            "documentation cannot prove a PASS validation state; raise the proof class"
        )
    if validation == "UNTESTED" and proof != "DOCUMENTED":
        raise ProtocolFabricError(
            "an UNTESTED shape may only carry DOCUMENTED proof strength"
        )

    ceiling = max_routing_eligibility(lifecycle)
    if routing != "RETIRED" and ROUTING_RANK[routing] > ROUTING_RANK[ceiling]:
        raise ProtocolFabricError(
            f"routing_eligibility {routing} exceeds the {ceiling} ceiling for "
            f"{catalog}/{validation}/{proof}"
        )

    degraded = _is_degraded_active(lifecycle)
    quarantined = lifecycle.get("quarantined", False) is True
    if degraded:
        if routing != "OBSERVE_ONLY":
            raise ProtocolFabricError(
                "an ACTIVE shape in FAIL/BLOCKED must be routed OBSERVE_ONLY"
            )
        if not quarantined:
            raise ProtocolFabricError(
                "an ACTIVE shape in FAIL/BLOCKED requires an explicit quarantined state"
            )
    elif quarantined:
        raise ProtocolFabricError(
            "quarantined may only be set on a degraded ACTIVE shape"
        )

    if catalog == "PROSPECTIVE" and validation in REJECTED_VALIDATION_STATES:
        if lifecycle.get("retained_negative_evidence") is not True:
            raise ProtocolFabricError(
                "a rejected PROSPECTIVE candidate must be retained as negative evidence"
            )
        if ROUTING_RANK[routing] > ROUTING_RANK["OBSERVE_ONLY"]:
            raise ProtocolFabricError(
                "a rejected PROSPECTIVE candidate may only route OBSERVE_ONLY"
            )
    if lifecycle.get("retained_negative_evidence") and not (
        catalog == "PROSPECTIVE" and validation in REJECTED_VALIDATION_STATES
    ):
        raise ProtocolFabricError(
            "retained_negative_evidence only applies to rejected PROSPECTIVE candidates"
        )

    if PROOF_RANK[proof] < STAGE_PROOF_FLOOR[stage]:
        raise ProtocolFabricError(
            f"rollout_stage {stage} requires proof_class at rank "
            f"{STAGE_PROOF_FLOOR[stage]} or stronger, not {proof}"
        )
    if stage == "AUTO_SWITCH_ELIGIBLE" and not (
        catalog == "ACTIVE"
        and validation == "PASS"
        and routing == "AUTO_SWITCH_ELIGIBLE"
    ):
        raise ProtocolFabricError(
            "AUTO_SWITCH_ELIGIBLE rollout requires an ACTIVE, PASS, "
            "auto-switch-eligible shape"
        )
    if stage in {"SHADOW_OBSERVED", "CANARY_ACCEPTED"} and ROUTING_RANK[routing] < ROUTING_RANK[
        "CANARY_ELIGIBLE"
    ]:
        raise ProtocolFabricError(
            f"rollout_stage {stage} requires at least CANARY_ELIGIBLE routing"
        )
    if stage == "DISCOVERED" and validation == "PASS":
        raise ProtocolFabricError("a DISCOVERED shape cannot already be PASS")

    normalized = {
        "catalog_state": catalog,
        "validation_state": validation,
        "proof_class": proof,
        "routing_eligibility": routing,
        "rollout_stage": stage,
        "compatibility_admitted": admitted,
        "quarantined": quarantined,
        "retained_negative_evidence": lifecycle.get("retained_negative_evidence", False)
        is True,
        "superseded_by": lifecycle.get("superseded_by"),
        "note": lifecycle.get("note", ""),
        "degraded": degraded,
        "max_routing_eligibility": ceiling,
    }
    return normalized


def lifecycle_index(profiles: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {profile["profile_id"]: dict(profile["lifecycle"]) for profile in profiles}


def may_route(lifecycle: Mapping[str, Any]) -> bool:
    return lifecycle["routing_eligibility"] in ROUTABLE_ROUTING_STATES


def selection_basis(lifecycle: Mapping[str, Any]) -> str:
    catalog = lifecycle["catalog_state"]
    if catalog == "ACTIVE":
        return "ACTIVE_PREFERRED"
    if catalog == "LEGACY":
        return "COMPATIBILITY_FALLBACK"
    return "PROSPECTIVE_CANDIDATE"


def validate_lifecycle_model(model: Any) -> dict[str, Any]:
    """Validate the registry's declared lifecycle vocabulary against the owner."""

    if not isinstance(model, Mapping):
        raise ProtocolFabricError("lifecycle_model must be an object")
    if model.get("schema_version") != LIFECYCLE_SCHEMA:
        raise ProtocolFabricError("unsupported lifecycle model schema")
    expected = {
        "catalog_states": CATALOG_STATES,
        "validation_states": VALIDATION_STATES,
        "proof_classes": PROOF_CLASSES,
        "routing_eligibilities": ROUTING_ELIGIBILITIES,
        "rollout_stages": ROLLOUT_STAGES,
    }
    for key, allowed in expected.items():
        value = model.get(key)
        if not isinstance(value, list) or tuple(value) != allowed:
            raise ProtocolFabricError(
                f"lifecycle_model.{key} must equal the owner vocabulary {list(allowed)}"
            )
    return dict(model)


def validate_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(profile, Mapping):
        raise ProtocolFabricError("profile must be an object")

    required = {
        "schema_version",
        "profile_id",
        "host_family",
        "shape_version",
        "transport",
        "config_shapes",
        "events",
        "response_shapes",
        "host_version_evidence",
        "proof_ceiling",
        "lifecycle",
    }
    missing = sorted(required - set(profile))
    if missing:
        raise ProtocolFabricError("profile missing fields: " + ", ".join(missing))
    if profile["schema_version"] != PROFILE_SCHEMA:
        raise ProtocolFabricError("unsupported protocol profile schema")
    for key in ("profile_id", "host_family", "shape_version", "transport", "proof_ceiling"):
        if not isinstance(profile[key], str) or not profile[key].strip():
            raise ProtocolFabricError(f"{key} must be a non-empty string")

    config_shapes = profile["config_shapes"]
    if not isinstance(config_shapes, list) or not config_shapes or not all(
        isinstance(item, str) and item for item in config_shapes
    ):
        raise ProtocolFabricError("config_shapes must be a non-empty string array")

    responses = profile["response_shapes"]
    if not isinstance(responses, Mapping) or not responses:
        raise ProtocolFabricError("response_shapes must be a non-empty object")
    for shape_id, spec in responses.items():
        if not isinstance(shape_id, str) or not shape_id:
            raise ProtocolFabricError("response shape id must be a non-empty string")
        if not isinstance(spec, Mapping):
            raise ProtocolFabricError(f"response shape {shape_id} must be an object")
        if spec.get("encoder") not in {
            "cursor-native-prompt-v1",
            "cursor-native-stop-v1",
            "cursor-native-session-start-v1",
            "claude-flat-decision-v1",
            "claude-nested-stop-v1",
            "codex-common-prompt-v1",
        }:
            raise ProtocolFabricError(f"unsupported encoder for response shape {shape_id}")

    events = profile["events"]
    if not isinstance(events, Mapping) or not events:
        raise ProtocolFabricError("events must be a non-empty object")
    for canonical_event, event in events.items():
        if canonical_event not in CANONICAL_EVENTS:
            raise ProtocolFabricError(f"unsupported canonical event: {canonical_event}")
        if not isinstance(event, Mapping):
            raise ProtocolFabricError(f"event {canonical_event} must be an object")
        host_events = event.get("host_events")
        if not isinstance(host_events, list) or not host_events or not all(
            isinstance(item, str) and item for item in host_events
        ):
            raise ProtocolFabricError(f"{canonical_event}.host_events invalid")
        event_name_field = event.get("event_name_field")
        if event_name_field is not None and (
            not isinstance(event_name_field, str) or not event_name_field.strip()
        ):
            raise ProtocolFabricError(
                f"{canonical_event}.event_name_field must be a non-empty string when present"
            )
        required_fields = event.get("required_fields", {})
        optional_fields = event.get("optional_fields", {})
        for name, fields in (("required_fields", required_fields), ("optional_fields", optional_fields)):
            if not isinstance(fields, Mapping):
                raise ProtocolFabricError(f"{canonical_event}.{name} must be an object")
            for field, expected in fields.items():
                if not isinstance(field, str) or not field:
                    raise ProtocolFabricError(f"{canonical_event}.{name} has invalid field")
                _check_field_type(None, expected) if expected == "null" else _validate_type_name(expected)
        accepted = event.get("accepted_response_shapes")
        if not isinstance(accepted, list) or not accepted:
            raise ProtocolFabricError(f"{canonical_event}.accepted_response_shapes invalid")
        unknown = [item for item in accepted if item not in responses]
        if unknown:
            raise ProtocolFabricError(
                f"{canonical_event} references unknown response shapes: {', '.join(unknown)}"
            )

    _version_match(profile, None)
    normalized = dict(profile)
    normalized["lifecycle"] = validate_lifecycle(profile["lifecycle"])
    return normalized


def _validate_type_name(expected: Any) -> None:
    if expected not in {"string", "boolean", "integer", "number", "array", "object", "null"}:
        raise ProtocolFabricError(f"unsupported field type in profile: {expected}")


def load_profiles(value: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        if "lifecycle_model" in value:
            validate_lifecycle_model(value["lifecycle_model"])
        profiles = value.get("profiles")
        if profiles is None:
            profiles = [value]
    else:
        profiles = list(value)
    if not isinstance(profiles, list) or not profiles:
        raise ProtocolFabricError("profile registry must contain at least one profile")
    validated = [validate_profile(profile) for profile in profiles]
    ids = [item["profile_id"] for item in validated]
    if len(ids) != len(set(ids)):
        raise ProtocolFabricError("duplicate profile_id")
    return validated


def observe_shape(
    *,
    host_family: str,
    host_event: str,
    payload: Mapping[str, Any],
    host_version: str | None = None,
    transport: str | None = None,
) -> dict[str, Any]:
    """Build a privacy-safe live/synthetic observation suitable for negotiation."""

    if not host_family or not host_event:
        raise ProtocolFabricError("host_family and host_event are required")
    fingerprint = shape_fingerprint(payload)
    return {
        "schema_version": OBSERVATION_SCHEMA,
        "host_family": host_family,
        "host_event": host_event,
        "host_version": host_version,
        "transport": transport,
        "fingerprint": fingerprint,
        "payload_keys": sorted(str(key) for key in payload),
        "content_persisted": False,
        "proof_ceiling": (
            "Structural hook-shape observation only; no payload values are persisted and "
            "host behavior is not inferred beyond this event."
        ),
    }


def bind_observation_to_profile(
    observation: Mapping[str, Any],
    profile_id: str,
) -> dict[str, Any]:
    """Emit evidence that one observed host version/shape matched a known profile."""

    if observation.get("schema_version") != OBSERVATION_SCHEMA:
        raise ProtocolFabricError("unsupported observation schema")
    return {
        "schema_version": "agent-hook-version-shape-binding/v1",
        "host_family": observation.get("host_family"),
        "host_version": observation.get("host_version"),
        "host_event": observation.get("host_event"),
        "shape_sha256": observation.get("fingerprint", {}).get("shape_sha256"),
        "profile_id": profile_id,
        "content_persisted": False,
    }


def _event_candidate(
    profile: Mapping[str, Any],
    *,
    canonical_event: str,
    host_event: str,
    payload: Mapping[str, Any],
    host_version: str | None,
) -> Candidate | None:
    if canonical_event not in profile["events"]:
        return None
    event = profile["events"][canonical_event]
    if host_event not in event["host_events"]:
        return None

    required = event.get("required_fields", {})
    missing: list[str] = []
    bad_type: list[str] = []
    for key, expected in required.items():
        if key not in payload:
            missing.append(key)
        elif not _check_field_type(payload[key], expected):
            bad_type.append(key)

    version_match = _version_match(profile, host_version)
    if profile.get("version_match_mode", "HINT") == "HARD" and version_match == "OUTSIDE_RANGE":
        return None

    score = 100
    score += 3 * len(required)
    score -= 60 * len(missing)
    score -= 50 * len(bad_type)
    score += 20 if host_event == event["host_events"][0] else 10
    score += {
        "EXACT_OBSERVED": 30,
        "IN_RANGE": 20,
        "UNBOUND": 5,
        "UNKNOWN": 0,
        "OUTSIDE_RANGE": -15,
    }[version_match]

    optional = event.get("optional_fields", {})
    for key, expected in optional.items():
        if key in payload and _check_field_type(payload[key], expected):
            score += 2

    return Candidate(
        profile_id=profile["profile_id"],
        shape_version=profile["shape_version"],
        canonical_event=canonical_event,
        host_event=host_event,
        score=score,
        version_match=version_match,
        required_fields=tuple(sorted(required)),
        missing_required=tuple(sorted(set(missing + bad_type))),
        response_shapes=tuple(event["accepted_response_shapes"]),
    )


def negotiate(
    profiles: Sequence[Mapping[str, Any]],
    *,
    host_family: str,
    canonical_event: str,
    host_event: str,
    payload: Mapping[str, Any],
    host_version: str | None = None,
    failed_response_shapes: Iterable[str] = (),
    preferred_response_shapes: Sequence[str] = (),
) -> dict[str, Any]:
    """Negotiate a decoder profile and response encoder for one observed event."""

    if canonical_event not in CANONICAL_EVENTS:
        raise ProtocolFabricError(f"unsupported canonical event: {canonical_event}")
    if not isinstance(payload, Mapping):
        raise ProtocolFabricError("payload must be an object")
    if host_version is None and isinstance(payload.get("cursor_version"), str):
        host_version = payload["cursor_version"]

    validated = load_profiles(profiles)
    host_profiles = [item for item in validated if item["host_family"] == host_family]
    observation = observe_shape(
        host_family=host_family,
        host_event=host_event,
        payload=payload,
        host_version=host_version,
    )

    # A self-describing event field is stronger evidence than the caller's
    # dispatch label. If the payload names an event outside the aliases admitted
    # for this canonical event, fail to UNKNOWN_SHAPE instead of silently
    # falling back to a looser/minimal profile.
    event_name_fields: dict[str, set[str]] = {}
    for profile in host_profiles:
        event = profile["events"].get(canonical_event)
        if not isinstance(event, Mapping):
            continue
        field = event.get("event_name_field")
        if isinstance(field, str) and field:
            event_name_fields.setdefault(field, set()).update(event["host_events"])

    mismatched_event_fields = []
    for field, allowed_values in event_name_fields.items():
        observed_value = payload.get(field)
        if observed_value is not None and (
            not isinstance(observed_value, str) or observed_value not in allowed_values
        ):
            mismatched_event_fields.append(field)

    if mismatched_event_fields:
        return {
            "schema_version": ROUTE_SCHEMA,
            "state": "UNKNOWN_SHAPE",
            "reason": "SELF_DESCRIBED_EVENT_MISMATCH",
            "host_family": host_family,
            "canonical_event": canonical_event,
            "host_event": host_event,
            "host_version": host_version,
            "observation": observation,
            "mismatch_fields": sorted(mismatched_event_fields),
            "candidates": [],
            "selected": None,
            "fallbacks": [],
            "safety": {
                "policy_decision": "DEFER_TO_CONSUMER",
                "rule": (
                    "A payload that self-identifies as a different event must not be "
                    "reinterpreted through a looser profile."
                ),
            },
        }

    candidates: list[Candidate] = []
    for profile in host_profiles:
        candidate = _event_candidate(
            profile,
            canonical_event=canonical_event,
            host_event=host_event,
            payload=payload,
            host_version=host_version,
        )
        if candidate is not None:
            candidates.append(candidate)
    lifecycle_by_id = lifecycle_index(validated)
    candidates.sort(
        key=lambda item: (
            CATALOG_RANK.get(lifecycle_by_id[item.profile_id]["catalog_state"], 99),
            -item.score,
            item.profile_id,
        )
    )

    def _lifecycle_of(candidate: Candidate) -> dict[str, Any]:
        return lifecycle_by_id[candidate.profile_id]

    def _regressed_active() -> list[str]:
        return [
            item.profile_id
            for item in candidates
            if _lifecycle_of(item)["catalog_state"] == "ACTIVE" and item.missing_required
        ]

    def _active_regression_route(regressed: list[str]) -> dict[str, Any]:
        return {
            "schema_version": ROUTE_SCHEMA,
            "state": "UNKNOWN_SHAPE",
            "reason": "ACTIVE_SHAPE_REGRESSION",
            "host_family": host_family,
            "canonical_event": canonical_event,
            "host_event": host_event,
            "host_version": host_version,
            "observation": observation,
            "candidates": [asdict(item) for item in candidates],
            "selected": None,
            "fallbacks": [],
            "lifecycle_safety": {
                "active_profiles_regressed": sorted(regressed),
                "prospective_fallback": "NOT_PERFORMED",
                "degraded": True,
                "rule": (
                    "A regressed ACTIVE shape is an explicit degradation. A prospective "
                    "or unadmitted candidate never silently replaces it."
                ),
            },
            "safety": {
                "policy_decision": "DEFER_TO_CONSUMER",
                "rule": (
                    "The previously accepted ACTIVE shape no longer matches. Consumers "
                    "must observe the regression rather than route through a weaker "
                    "candidate that merely happens to parse."
                ),
            },
        }

    viable = [item for item in candidates if not item.missing_required]
    if not viable:
        regressed = _regressed_active()
        if regressed:
            return _active_regression_route(regressed)
        return {
            "schema_version": ROUTE_SCHEMA,
            "state": "UNKNOWN_SHAPE",
            "host_family": host_family,
            "canonical_event": canonical_event,
            "host_event": host_event,
            "host_version": host_version,
            "observation": observation,
            "candidates": [asdict(item) for item in candidates],
            "selected": None,
            "fallbacks": [],
            "lifecycle_safety": {
                "active_profiles_regressed": [],
                "prospective_fallback": "NOT_PERFORMED",
                "degraded": False,
                "rule": "No tracked shape claimed this payload; nothing was invented.",
            },
            "safety": {
                "policy_decision": "DEFER_TO_CONSUMER",
                "rule": (
                    "Unknown wire shape is not automatically a global outage. Consumers may "
                    "fail open for observational/non-security hooks and fail closed only for "
                    "explicitly security-critical policy boundaries."
                ),
            },
        }

    routable = [item for item in viable if may_route(_lifecycle_of(item))]
    if not routable:
        regressed = _regressed_active()
        if regressed:
            return _active_regression_route(regressed)
        observed = [
            {
                "profile_id": item.profile_id,
                "catalog_state": _lifecycle_of(item)["catalog_state"],
                "validation_state": _lifecycle_of(item)["validation_state"],
                "proof_class": _lifecycle_of(item)["proof_class"],
                "routing_eligibility": _lifecycle_of(item)["routing_eligibility"],
            }
            for item in viable
        ]
        return {
            "schema_version": ROUTE_SCHEMA,
            "state": "OBSERVE_ONLY_SHAPE",
            "host_family": host_family,
            "canonical_event": canonical_event,
            "host_event": host_event,
            "host_version": host_version,
            "observation": observation,
            "candidates": [asdict(item) for item in candidates],
            "observed_profiles": observed,
            "selected": None,
            "fallbacks": [],
            "lifecycle_safety": {
                "active_profiles_regressed": [],
                "prospective_fallback": "NOT_PERFORMED",
                "degraded": False,
                "rule": (
                    "Structurally matching but non-routable shapes are observed and "
                    "retained; they never become an implicit route."
                ),
            },
            "safety": {
                "policy_decision": "DEFER_TO_CONSUMER",
                "rule": (
                    "Observation and structural classification are permitted; routing "
                    "authority is not."
                ),
            },
        }

    selected = routable[0]
    selected_lifecycle = _lifecycle_of(selected)
    if selected_lifecycle["catalog_state"] == "PROSPECTIVE":
        regressed = _regressed_active()
        if regressed:
            return _active_regression_route(regressed)
    profile = next(item for item in validated if item["profile_id"] == selected.profile_id)
    failed = set(failed_response_shapes)
    declared_response_shapes = list(selected.response_shapes)
    native_shape = declared_response_shapes[0]
    response_shapes = list(declared_response_shapes)

    preference = list(preferred_response_shapes)
    if preference:
        ranked: list[str] = []
        for item in preference + response_shapes:
            if item in response_shapes and item not in ranked:
                ranked.append(item)
        response_shapes = ranked

    available = [item for item in response_shapes if item not in failed]
    if not available:
        return {
            "schema_version": ROUTE_SCHEMA,
            "state": "NO_RESPONSE_SHAPE",
            "host_family": host_family,
            "canonical_event": canonical_event,
            "host_event": host_event,
            "host_version": host_version,
            "observation": observation,
            "candidates": [asdict(item) for item in candidates],
            "selected": asdict(selected),
            "lifecycle": dict(selected_lifecycle),
            "selection_basis": selection_basis(selected_lifecycle),
            "fallbacks": [],
            "safety": {"policy_decision": "DEFER_TO_CONSUMER"},
        }

    response_shape = available[0]
    state = "MATCHED" if response_shape == native_shape else "HYBRIDIZED"
    return {
        "schema_version": ROUTE_SCHEMA,
        "state": state,
        "host_family": host_family,
        "canonical_event": canonical_event,
        "host_event": host_event,
        "host_version": host_version,
        "observation": observation,
        "candidates": [asdict(item) for item in candidates],
        "selected": {
            **asdict(selected),
            "response_shape": response_shape,
            "config_shapes": list(profile["config_shapes"]),
        },
        "lifecycle": dict(selected_lifecycle),
        "selection_basis": selection_basis(selected_lifecycle),
        "canary_confirmation_required": (
            selected_lifecycle["catalog_state"] == "PROSPECTIVE"
            or selected_lifecycle["proof_class"] != "LIVE_CANARY"
        ),
        "fallbacks": [item for item in available[1:]],
        "version_binding": bind_observation_to_profile(observation, selected.profile_id),
        "proof_ceiling": (
            "Negotiation proves structural compatibility with tracked profiles. It does not "
            "prove the host accepted the selected response until a live canary/readback does."
        ),
    }


def encode_decision(
    profiles: Sequence[Mapping[str, Any]],
    *,
    profile_id: str,
    response_shape: str,
    canonical_event: str,
    decision: HookDecision,
) -> dict[str, Any]:
    """Encode one canonical policy decision into a negotiated host response shape."""

    decision.validate()
    validated = load_profiles(profiles)
    profile = next((item for item in validated if item["profile_id"] == profile_id), None)
    if profile is None:
        raise ProtocolFabricError(f"unknown profile_id: {profile_id}")
    if canonical_event not in profile["events"]:
        raise ProtocolFabricError(f"profile does not support event: {canonical_event}")
    event = profile["events"][canonical_event]
    if response_shape not in event["accepted_response_shapes"]:
        raise ProtocolFabricError("response shape is not admitted for this event")
    spec = profile["response_shapes"][response_shape]
    encoder = spec["encoder"]

    if encoder == "cursor-native-prompt-v1":
        if canonical_event != "prompt.submit":
            raise ProtocolFabricError("cursor native prompt encoder used for wrong event")
        if decision.action == "ALLOW":
            return {"continue": True}
        if decision.action == "BLOCK":
            return {"continue": False, "user_message": decision.message}
        if decision.action == "CONTEXT":
            return {"continue": True, "agent_message": decision.additional_context}
        raise ProtocolFabricError(f"decision {decision.action} unsupported by {encoder}")

    if encoder == "cursor-native-stop-v1":
        if canonical_event != "session.stop":
            raise ProtocolFabricError("cursor native stop encoder used for wrong event")
        if decision.action == "ALLOW":
            return {}
        if decision.action == "FOLLOW_UP":
            return {"followup_message": decision.message}
        raise ProtocolFabricError(f"decision {decision.action} unsupported by {encoder}")

    if encoder == "cursor-native-session-start-v1":
        if canonical_event != "session.start":
            raise ProtocolFabricError("cursor session-start encoder used for wrong event")
        if decision.action == "ALLOW":
            return {}
        if decision.action == "CONTEXT":
            return {"additional_context": decision.additional_context}
        raise ProtocolFabricError(f"decision {decision.action} unsupported by {encoder}")

    if encoder == "claude-flat-decision-v1":
        if decision.action == "ALLOW":
            return {}
        if decision.action in {"BLOCK", "FOLLOW_UP"}:
            return {"decision": "block", "reason": decision.message}
        raise ProtocolFabricError(f"decision {decision.action} unsupported by {encoder}")

    if encoder == "claude-nested-stop-v1":
        if canonical_event != "session.stop":
            raise ProtocolFabricError("nested stop encoder used for wrong event")
        if decision.action == "ALLOW":
            return {}
        if decision.action == "FOLLOW_UP":
            return {
                "hookSpecificOutput": {
                    "decision": "block",
                    "reason": decision.message,
                }
            }
        raise ProtocolFabricError(f"decision {decision.action} unsupported by {encoder}")

    if encoder == "codex-common-prompt-v1":
        if canonical_event != "prompt.submit":
            raise ProtocolFabricError("codex prompt encoder used for wrong event")
        if decision.action == "ALLOW":
            return {"continue": True}
        if decision.action == "BLOCK":
            return {"decision": "block", "reason": decision.message}
        if decision.action == "CONTEXT":
            return {
                "continue": True,
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": decision.additional_context,
                },
            }
        raise ProtocolFabricError(f"decision {decision.action} unsupported by {encoder}")

    raise ProtocolFabricError(f"unimplemented encoder: {encoder}")


def render_config(
    *,
    config_shape: str,
    bindings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Render a small provider config from canonical event bindings.

    Each binding requires canonical_event, command and optional timeout/fail_closed.
    This intentionally covers only shapes with tracked evidence. Unsupported shapes
    fail closed rather than inventing configuration syntax.
    """

    normalized: list[dict[str, Any]] = []
    for binding in bindings:
        if not isinstance(binding, Mapping):
            raise ProtocolFabricError("binding must be an object")
        event = binding.get("canonical_event")
        command = binding.get("command")
        if event not in CANONICAL_EVENTS or not isinstance(command, str) or not command:
            raise ProtocolFabricError("binding requires canonical_event and command")
        normalized.append(dict(binding))

    if config_shape == "cursor-native-config-v1":
        mapping = {
            "session.start": "sessionStart",
            "prompt.submit": "beforeSubmitPrompt",
            "session.stop": "stop",
            "tool.pre": "preToolUse",
            "tool.post": "postToolUse",
            "compact.pre": "preCompact",
        }
        hooks: dict[str, list[dict[str, Any]]] = {}
        for item in normalized:
            host_event = mapping[item["canonical_event"]]
            entry: dict[str, Any] = {"command": item["command"]}
            if "timeout" in item:
                entry["timeout"] = item["timeout"]
            if "fail_closed" in item:
                entry["failClosed"] = bool(item["fail_closed"])
            hooks.setdefault(host_event, []).append(entry)
        return {"version": 1, "hooks": hooks}

    if config_shape == "claude-codex-group-config-v1":
        mapping = {
            "session.start": "SessionStart",
            "prompt.submit": "UserPromptSubmit",
            "session.stop": "Stop",
            "tool.pre": "PreToolUse",
            "tool.post": "PostToolUse",
            "compact.pre": "PreCompact",
        }
        hooks: dict[str, list[dict[str, Any]]] = {}
        for item in normalized:
            host_event = mapping[item["canonical_event"]]
            hook: dict[str, Any] = {"type": "command", "command": item["command"]}
            if "timeout" in item:
                hook["timeout"] = item["timeout"]
            hooks.setdefault(host_event, []).append({"hooks": [hook]})
        return {"hooks": hooks}

    raise ProtocolFabricError(f"unsupported config shape: {config_shape}")
