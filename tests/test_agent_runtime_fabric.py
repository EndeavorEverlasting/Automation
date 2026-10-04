from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "capabilities/agent-runtime-fabric/core/fabric.py"
FIXTURES = ROOT / "capabilities/agent-runtime-fabric/fixtures"
SCHEMAS = ROOT / "capabilities/agent-runtime-fabric/schemas"

spec = importlib.util.spec_from_file_location("agent_runtime_fabric", CORE)
assert spec is not None and spec.loader is not None
fabric = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fabric
spec.loader.exec_module(fabric)


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def requirement(**overrides) -> dict:
    base = {
        "schema_version": "agent-runtime-work-requirement/v1",
        "work_unit_id": "synthetic-work-1",
        "required_role": "EXECUTION_ONLY",
        "required_capabilities": ["repo_edit"],
        "expected_usage": {"wall_clock_ms": 5000},
        "preferred_adapters": [],
        "proof_ceiling": "Synthetic admission fixture only.",
    }
    base.update(overrides)
    return base


class StaticAdapter:
    def __init__(self, profile: dict):
        self._profile = profile
        self.adapter_id = profile["adapter_id"]

    def probe(self) -> dict:
        return dict(self._profile)


class AgentRuntimeFabricTests(unittest.TestCase):
    def test_host_wall_clock_is_independent_from_token_limit(self) -> None:
        profile = load("cursor-like-hook.synthetic.v1.json")
        req = requirement(
            required_capabilities=["before_submit_hook"],
            expected_usage={"wall_clock_ms": 9500, "model_tokens": 999999},
        )
        decision = fabric.assess(profile, req)
        self.assertFalse(decision.allowed)
        self.assertIn(9000.0, decision.effective_limits.values())
        self.assertTrue(
            any(
                reason.startswith("HARD_LIMIT_EXCEEDED:wall_clock_ms")
                for reason in decision.reasons
            )
        )
        self.assertFalse(
            any("model_tokens" in reason for reason in decision.reasons)
        )

    def test_capped_cloud_modality_falls_back_without_disabling_agent_class(self) -> None:
        cloud = load("cloud-capped-executor.synthetic.v1.json")
        local = {
            **cloud,
            "adapter_id": "synthetic-local-executor",
            "harness_family": "local-cli",
            "quotas": {},
            "dispatch_costs": {},
        }
        registry = fabric.AdapterRegistry()
        registry.register(StaticAdapter(cloud))
        registry.register(StaticAdapter(local))
        result = registry.route(
            requirement(
                preferred_adapters=[cloud["adapter_id"], local["adapter_id"]]
            )
        )
        self.assertEqual(result["state"], "SELECTED")
        self.assertEqual(result["selected_adapter_id"], local["adapter_id"])
        first = result["evaluations"][0]["admission"]
        self.assertFalse(first["allowed"])
        self.assertTrue(
            any(
                reason.startswith("QUOTA_EXHAUSTED:cloud_agent_launches")
                for reason in first["reasons"]
            )
        )

    def test_execution_only_agent_stays_eligible_but_not_for_judgment_lane(self) -> None:
        profile = load("cloud-capped-executor.synthetic.v1.json")
        profile["quotas"]["cloud_agent_launches"]["remaining"] = 10
        decision = fabric.assess(
            profile,
            requirement(required_role="JUDGMENT_OWNER"),
        )
        self.assertFalse(decision.allowed)
        self.assertIn("ROLE_NOT_ADMITTED:JUDGMENT_OWNER", decision.reasons)

    def test_machine_capacity_axis_can_reject_one_adapter_and_select_another(self) -> None:
        base = load("cloud-capped-executor.synthetic.v1.json")
        base["quotas"]["cloud_agent_launches"]["remaining"] = 10
        small = {
            **base,
            "adapter_id": "small-machine",
            "hard_limits": {**base["hard_limits"], "memory_mib": 4096},
        }
        large = {
            **base,
            "adapter_id": "large-machine",
            "hard_limits": {**base["hard_limits"], "memory_mib": 32768},
        }
        registry = fabric.AdapterRegistry()
        registry.register(StaticAdapter(small))
        registry.register(StaticAdapter(large))
        result = registry.route(
            requirement(
                expected_usage={"wall_clock_ms": 5000, "memory_mib": 8192},
                preferred_adapters=["small-machine", "large-machine"],
            )
        )
        self.assertEqual(result["selected_adapter_id"], "large-machine")

    def test_unknown_quota_fails_closed(self) -> None:
        profile = load("cloud-capped-executor.synthetic.v1.json")
        profile["quotas"]["cloud_agent_launches"] = {
            "state": "UNKNOWN",
            "unit": "launch",
        }
        decision = fabric.assess(profile, requirement())
        self.assertFalse(decision.allowed)
        self.assertIn("QUOTA_UNKNOWN:cloud_agent_launches", decision.reasons)

    def test_runtime_and_schema_strictness_reject_unknown_fields(self) -> None:
        profile = load("cloud-capped-executor.synthetic.v1.json")
        profile["unexpected"] = True
        with self.assertRaises(fabric.RuntimeFabricError):
            fabric.validate_profile(profile)

        req = requirement()
        req["unexpected"] = True
        with self.assertRaises(fabric.RuntimeFabricError):
            fabric.validate_requirement(req)

    def test_quota_objects_reject_unknown_fields(self) -> None:
        profile = load("cloud-capped-executor.synthetic.v1.json")
        profile["quotas"]["cloud_agent_launches"]["unexpected"] = 1
        with self.assertRaises(fabric.RuntimeFabricError):
            fabric.validate_profile(profile)

    def test_route_schema_binds_state_and_evidence_shapes(self) -> None:
        schema = json.loads(
            (SCHEMAS / "route-decision.v1.json").read_text(encoding="utf-8")
        )
        evaluation = schema["properties"]["evaluations"]["items"]
        self.assertEqual(
            evaluation["properties"]["profile"]["$ref"],
            "runtime-profile.v1.json",
        )
        self.assertFalse(evaluation["properties"]["admission"]["$ref"] == "")
        self.assertGreaterEqual(len(schema["allOf"]), 2)

    def test_duplicate_adapter_registration_fails_closed(self) -> None:
        profile = load("cloud-capped-executor.synthetic.v1.json")
        registry = fabric.AdapterRegistry()
        registry.register(StaticAdapter(profile))
        with self.assertRaises(fabric.DuplicateAdapterError):
            registry.register(StaticAdapter(profile))

    def test_no_adapter_for_required_role_returns_blocked_matrix(self) -> None:
        profile = load("cloud-capped-executor.synthetic.v1.json")
        profile["quotas"]["cloud_agent_launches"]["remaining"] = 10
        registry = fabric.AdapterRegistry()
        registry.register(StaticAdapter(profile))
        result = registry.route(requirement(required_role="JUDGMENT_OWNER"))
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIsNone(result["selected_adapter_id"])
        self.assertEqual(len(result["evaluations"]), 1)


if __name__ == "__main__":
    unittest.main()
