"""Provider- and harness-neutral runtime-adapter admission fabric.

This module selects an already-authorized execution *modality* from probed
runtime profiles. It does not choose semantic ownership, grant judgment
authority, execute the native runtime, or promote synthetic proof to live proof.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, MutableMapping, Protocol, Sequence, runtime_checkable

PROFILE_SCHEMA = "agent-runtime-profile/v1"
REQUIREMENT_SCHEMA = "agent-runtime-work-requirement/v1"
ROUTE_SCHEMA = "agent-runtime-route-decision/v1"

PROFILE_FIELDS = {
    "schema_version",
    "adapter_id",
    "harness_family",
    "state",
    "capabilities",
    "admitted_roles",
    "hard_limits",
    "reserve",
    "quotas",
    "dispatch_costs",
    "proof_ceiling",
}
REQUIREMENT_FIELDS = {
    "schema_version",
    "work_unit_id",
    "required_role",
    "required_capabilities",
    "expected_usage",
    "preferred_adapters",
    "proof_ceiling",
}
QUOTA_FIELDS = {"state", "remaining", "unit"}


class RuntimeFabricError(ValueError):
    """Raised when a profile or work requirement violates the public contract."""


class DuplicateAdapterError(RuntimeFabricError):
    """Raised when two adapters claim the same stable adapter id."""


@runtime_checkable
class RuntimeAdapter(Protocol):
    """Minimal adapter seam: probe only; native execution stays adapter-owned."""

    @property
    def adapter_id(self) -> str:
        """Stable semantic id for one concrete execution modality."""

    def probe(self) -> Mapping[str, Any]:
        """Return one current ``agent-runtime-profile/v1`` without mutation."""


@dataclass(frozen=True)
class AdmissionDecision:
    adapter_id: str
    allowed: bool
    reasons: tuple[str, ...] = ()
    effective_limits: Mapping[str, float] = field(default_factory=dict)
    quota_checks: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["reasons"] = list(self.reasons)
        value["effective_limits"] = dict(self.effective_limits)
        value["quota_checks"] = {
            key: dict(item) for key, item in self.quota_checks.items()
        }
        return value


def _require_nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeFabricError(f"{label} must be a non-empty string")
    return value.strip()


def _string_set(value: Any, label: str) -> set[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise RuntimeFabricError(f"{label} must be a list of non-empty strings")
    return {item.strip() for item in value}


def _number_map(value: Any, label: str) -> dict[str, float]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise RuntimeFabricError(f"{label} must be an object")
    result: dict[str, float] = {}
    for key, raw in value.items():
        _require_nonempty_string(key, f"{label} key")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw < 0:
            raise RuntimeFabricError(f"{label}.{key} must be a non-negative number")
        result[str(key)] = float(raw)
    return result


def validate_profile(profile: Mapping[str, Any]) -> None:
    if not isinstance(profile, Mapping):
        raise RuntimeFabricError("runtime profile must be an object")
    extra = sorted(set(profile) - PROFILE_FIELDS)
    if extra:
        raise RuntimeFabricError(f"runtime profile contains unsupported fields: {extra}")
    if profile.get("schema_version") != PROFILE_SCHEMA:
        raise RuntimeFabricError(f"schema_version must be {PROFILE_SCHEMA}")
    _require_nonempty_string(profile.get("adapter_id"), "adapter_id")
    _require_nonempty_string(profile.get("harness_family"), "harness_family")
    if profile.get("state") not in {"READY", "BLOCKED", "UNKNOWN"}:
        raise RuntimeFabricError("state must be READY, BLOCKED, or UNKNOWN")
    _string_set(profile.get("capabilities"), "capabilities")
    roles = _string_set(profile.get("admitted_roles"), "admitted_roles")
    if not roles:
        raise RuntimeFabricError("admitted_roles must contain at least one role")

    hard = _number_map(profile.get("hard_limits"), "hard_limits")
    reserve = _number_map(profile.get("reserve"), "reserve")
    _number_map(profile.get("dispatch_costs"), "dispatch_costs")
    for axis, amount in reserve.items():
        if axis not in hard:
            raise RuntimeFabricError(
                f"reserve.{axis} has no corresponding hard_limits.{axis}"
            )
        if amount > hard[axis]:
            raise RuntimeFabricError(f"reserve.{axis} exceeds hard limit")

    quotas = profile.get("quotas", {})
    if not isinstance(quotas, Mapping):
        raise RuntimeFabricError("quotas must be an object")
    for axis, quota in quotas.items():
        _require_nonempty_string(axis, "quota axis")
        if not isinstance(quota, Mapping):
            raise RuntimeFabricError(f"quotas.{axis} must be an object")
        quota_extra = sorted(set(quota) - QUOTA_FIELDS)
        if quota_extra:
            raise RuntimeFabricError(
                f"quotas.{axis} contains unsupported fields: {quota_extra}"
            )
        state = quota.get("state")
        if state not in {"KNOWN", "UNLIMITED", "UNKNOWN"}:
            raise RuntimeFabricError(
                f"quotas.{axis}.state must be KNOWN, UNLIMITED, or UNKNOWN"
            )
        _require_nonempty_string(quota.get("unit"), f"quotas.{axis}.unit")
        remaining = quota.get("remaining")
        if state == "KNOWN":
            if (
                isinstance(remaining, bool)
                or not isinstance(remaining, (int, float))
                or remaining < 0
            ):
                raise RuntimeFabricError(
                    f"quotas.{axis}.remaining must be non-negative for KNOWN quota"
                )
        elif remaining is not None:
            raise RuntimeFabricError(
                f"quotas.{axis}.remaining must be null unless state is KNOWN"
            )

    _require_nonempty_string(profile.get("proof_ceiling"), "proof_ceiling")


def validate_requirement(requirement: Mapping[str, Any]) -> None:
    if not isinstance(requirement, Mapping):
        raise RuntimeFabricError("work requirement must be an object")
    extra = sorted(set(requirement) - REQUIREMENT_FIELDS)
    if extra:
        raise RuntimeFabricError(f"work requirement contains unsupported fields: {extra}")
    if requirement.get("schema_version") != REQUIREMENT_SCHEMA:
        raise RuntimeFabricError(f"schema_version must be {REQUIREMENT_SCHEMA}")
    _require_nonempty_string(requirement.get("work_unit_id"), "work_unit_id")
    _require_nonempty_string(requirement.get("required_role"), "required_role")
    _string_set(requirement.get("required_capabilities"), "required_capabilities")
    _number_map(requirement.get("expected_usage"), "expected_usage")
    preferred = requirement.get("preferred_adapters", [])
    _string_set(preferred, "preferred_adapters")
    _require_nonempty_string(requirement.get("proof_ceiling"), "proof_ceiling")


def assess(
    profile: Mapping[str, Any],
    requirement: Mapping[str, Any],
) -> AdmissionDecision:
    """Evaluate one adapter profile against one already-authorized work unit."""
    validate_profile(profile)
    validate_requirement(requirement)

    adapter_id = str(profile["adapter_id"])
    reasons: list[str] = []
    if profile["state"] != "READY":
        reasons.append(f"ADAPTER_{profile['state']}")

    required_role = str(requirement["required_role"])
    admitted_roles = set(profile["admitted_roles"])
    if required_role not in admitted_roles:
        reasons.append(f"ROLE_NOT_ADMITTED:{required_role}")

    missing = sorted(
        set(requirement["required_capabilities"]) - set(profile["capabilities"])
    )
    reasons.extend(f"CAPABILITY_MISSING:{item}" for item in missing)

    hard = _number_map(profile.get("hard_limits"), "hard_limits")
    reserve = _number_map(profile.get("reserve"), "reserve")
    expected = _number_map(requirement.get("expected_usage"), "expected_usage")
    effective = {
        axis: limit - reserve.get(axis, 0.0)
        for axis, limit in hard.items()
    }
    for axis, amount in expected.items():
        if axis in effective and amount > effective[axis]:
            reasons.append(
                f"HARD_LIMIT_EXCEEDED:{axis}:expected={amount:g}:effective={effective[axis]:g}"
            )

    quotas = profile.get("quotas", {})
    costs = _number_map(profile.get("dispatch_costs"), "dispatch_costs")
    quota_checks: dict[str, dict[str, Any]] = {}
    for axis, cost in costs.items():
        quota = quotas.get(axis)
        if not isinstance(quota, Mapping):
            quota_checks[axis] = {"state": "MISSING", "required": cost}
            reasons.append(f"QUOTA_MISSING:{axis}")
            continue
        state = quota["state"]
        check = {
            "state": state,
            "required": cost,
            "remaining": quota.get("remaining"),
            "unit": quota.get("unit"),
        }
        quota_checks[axis] = check
        if state == "UNKNOWN":
            reasons.append(f"QUOTA_UNKNOWN:{axis}")
        elif state == "KNOWN" and float(quota["remaining"]) < cost:
            reasons.append(
                f"QUOTA_EXHAUSTED:{axis}:required={cost:g}:remaining={float(quota['remaining']):g}"
            )

    return AdmissionDecision(
        adapter_id=adapter_id,
        allowed=not reasons,
        reasons=tuple(reasons),
        effective_limits=effective,
        quota_checks=quota_checks,
    )


class AdapterRegistry:
    """Registry + deterministic admission router; native execution is out of scope."""

    def __init__(self) -> None:
        self._adapters: dict[str, RuntimeAdapter] = {}

    def register(self, adapter: RuntimeAdapter) -> None:
        adapter_id = _require_nonempty_string(
            getattr(adapter, "adapter_id", None),
            "adapter.adapter_id",
        )
        if adapter_id in self._adapters:
            raise DuplicateAdapterError(f"adapter already registered: {adapter_id}")
        self._adapters[adapter_id] = adapter

    def registered_ids(self) -> list[str]:
        return sorted(self._adapters)

    def _route_order(self, preferred: Sequence[str]) -> list[str]:
        preferred_unique: list[str] = []
        for adapter_id in preferred:
            if (
                adapter_id in self._adapters
                and adapter_id not in preferred_unique
            ):
                preferred_unique.append(adapter_id)
        remainder = sorted(set(self._adapters) - set(preferred_unique))
        return preferred_unique + remainder

    def route(
        self,
        requirement: Mapping[str, Any],
    ) -> MutableMapping[str, Any]:
        validate_requirement(requirement)
        preferred = list(requirement.get("preferred_adapters", []))
        evaluations: list[dict[str, Any]] = []
        for adapter_id in self._route_order(preferred):
            profile = dict(self._adapters[adapter_id].probe())
            if profile.get("adapter_id") != adapter_id:
                raise RuntimeFabricError(
                    f"adapter {adapter_id} returned profile for "
                    f"{profile.get('adapter_id')!r}"
                )
            decision = assess(profile, requirement)
            evaluations.append(
                {
                    "adapter_id": adapter_id,
                    "profile": profile,
                    "admission": decision.to_dict(),
                }
            )
            if decision.allowed:
                return {
                    "schema_version": ROUTE_SCHEMA,
                    "state": "SELECTED",
                    "work_unit_id": requirement["work_unit_id"],
                    "selected_adapter_id": adapter_id,
                    "evaluations": evaluations,
                    "proof_ceiling": (
                        "Adapter admission/profile proof only; native execution, "
                        "side effects, provider delivery, and live-host acceptance "
                        "require downstream evidence."
                    ),
                }
        return {
            "schema_version": ROUTE_SCHEMA,
            "state": "BLOCKED",
            "work_unit_id": requirement["work_unit_id"],
            "selected_adapter_id": None,
            "evaluations": evaluations,
            "proof_ceiling": (
                "No probed adapter satisfied the declared role, capability, "
                "hard-limit, and quota constraints; no native execution was attempted."
            ),
        }
