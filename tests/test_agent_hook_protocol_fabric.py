from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAP = ROOT / "capabilities" / "agent-hook-runtime"
CORE = CAP / "core" / "protocol_fabric.py"
REGISTRY = CAP / "profiles" / "current.v1.json"

SPEC = importlib.util.spec_from_file_location("automation_hook_protocol_fabric", CORE)
assert SPEC is not None and SPEC.loader is not None
FABRIC = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = FABRIC
SPEC.loader.exec_module(FABRIC)

HookDecision = FABRIC.HookDecision
ProtocolFabricError = FABRIC.ProtocolFabricError
encode_decision = FABRIC.encode_decision
load_profiles = FABRIC.load_profiles
negotiate = FABRIC.negotiate
observe_shape = FABRIC.observe_shape
render_config = FABRIC.render_config
shape_fingerprint = FABRIC.shape_fingerprint
validate_lifecycle = FABRIC.validate_lifecycle
max_routing_eligibility = FABRIC.max_routing_eligibility


def registry_value() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def profiles() -> list[dict]:
    return load_profiles(registry_value())


class HookProtocolFabricTests(unittest.TestCase):
    def test_legacy_cursor_shape_selects_minimal_profile(self) -> None:
        route = negotiate(
            profiles(),
            host_family="cursor",
            canonical_event="prompt.submit",
            host_event="beforeSubmitPrompt",
            payload={"prompt": "hello", "attachments": []},
        )
        self.assertEqual(route["state"], "MATCHED")
        self.assertEqual(route["selected"]["profile_id"], "cursor-native-minimal-v1")
        self.assertEqual(route["selected"]["response_shape"], "cursor.native.prompt.v1")

    def test_current_cursor_common_envelope_selects_specific_profile_and_binds_version(self) -> None:
        payload = {
            "prompt": "hello",
            "attachments": [],
            "hook_event_name": "beforeSubmitPrompt",
            "cursor_version": "9.99.1",
            "workspace_roots": ["C:/repo"],
            "conversation_id": "conversation-secret",
            "generation_id": "generation-secret",
        }
        route = negotiate(
            profiles(),
            host_family="cursor",
            canonical_event="prompt.submit",
            host_event="beforeSubmitPrompt",
            payload=payload,
        )
        self.assertEqual(route["state"], "MATCHED")
        self.assertEqual(
            route["selected"]["profile_id"],
            "cursor-native-common-envelope-v2",
        )
        self.assertEqual(route["host_version"], "9.99.1")
        self.assertEqual(route["version_binding"]["host_version"], "9.99.1")
        serialized = json.dumps(route)
        self.assertNotIn("conversation-secret", serialized)
        self.assertNotIn("generation-secret", serialized)

    def test_unknown_additive_cursor_fields_do_not_break_negotiation(self) -> None:
        payload = {
            "prompt": "hello",
            "hook_event_name": "beforeSubmitPrompt",
            "cursor_version": "10.0.0",
            "workspace_roots": ["/repo"],
            "new_future_field": {"shape": "ignored"},
        }
        route = negotiate(
            profiles(),
            host_family="cursor",
            canonical_event="prompt.submit",
            host_event="beforeSubmitPrompt",
            payload=payload,
        )
        self.assertEqual(route["state"], "MATCHED")
        self.assertEqual(
            route["selected"]["profile_id"],
            "cursor-native-common-envelope-v2",
        )
        self.assertIn("new_future_field:object", route["observation"]["fingerprint"]["field_types"])

    def test_breaking_cursor_shape_degrades_to_unknown_instead_of_inventing_policy(self) -> None:
        route = negotiate(
            profiles(),
            host_family="cursor",
            canonical_event="prompt.submit",
            host_event="beforeSubmitPrompt",
            payload={
                "hook_event_name": "beforeSubmitPrompt",
                "cursor_version": "11.0.0",
                "workspace_roots": ["/repo"],
                "text": "host renamed prompt unexpectedly",
            },
        )
        self.assertEqual(route["state"], "UNKNOWN_SHAPE")
        self.assertIsNone(route["selected"])
        self.assertEqual(route["safety"]["policy_decision"], "DEFER_TO_CONSUMER")
        self.assertFalse(route["observation"]["content_persisted"])

    def test_self_described_cursor_event_mismatch_cannot_fall_back_to_minimal_profile(self) -> None:
        route = negotiate(
            profiles(),
            host_family="cursor",
            canonical_event="prompt.submit",
            host_event="beforeSubmitPrompt",
            payload={
                "prompt": "hello",
                "hook_event_name": "stop",
                "cursor_version": "10.0.0",
                "workspace_roots": ["/repo"],
            },
        )
        self.assertEqual(route["state"], "UNKNOWN_SHAPE")
        self.assertEqual(route["reason"], "SELF_DESCRIBED_EVENT_MISMATCH")
        self.assertEqual(route["mismatch_fields"], ["hook_event_name"])
        self.assertIsNone(route["selected"])

    def test_self_described_codex_event_mismatch_is_rejected(self) -> None:
        route = negotiate(
            profiles(),
            host_family="codex",
            canonical_event="prompt.submit",
            host_event="UserPromptSubmit",
            payload={
                "cwd": "/repo",
                "hook_event_name": "Stop",
                "model": "gpt",
                "permission_mode": "default",
                "prompt": "hello",
                "session_id": "session",
                "turn_id": "turn",
            },
        )
        self.assertEqual(route["state"], "UNKNOWN_SHAPE")
        self.assertEqual(route["reason"], "SELF_DESCRIBED_EVENT_MISMATCH")

    def test_cursor_stop_can_fallback_to_documented_claude_flat_shape(self) -> None:
        payload = {
            "status": "completed",
            "loop_count": 0,
            "hook_event_name": "stop",
            "cursor_version": "9.99.1",
            "workspace_roots": ["/repo"],
        }
        route = negotiate(
            profiles(),
            host_family="cursor",
            canonical_event="session.stop",
            host_event="stop",
            payload=payload,
            failed_response_shapes=["cursor.native.stop.v1"],
        )
        self.assertEqual(route["state"], "HYBRIDIZED")
        self.assertEqual(route["selected"]["response_shape"], "claude.flat.stop.v1")
        encoded = encode_decision(
            profiles(),
            profile_id=route["selected"]["profile_id"],
            response_shape=route["selected"]["response_shape"],
            canonical_event="session.stop",
            decision=HookDecision(action="FOLLOW_UP", message="Continue the required work."),
        )
        self.assertEqual(
            encoded,
            {"decision": "block", "reason": "Continue the required work."},
        )

    def test_cursor_stop_can_choose_nested_compatibility_shape_without_schema_union(self) -> None:
        payload = {
            "status": "completed",
            "loop_count": 1,
            "hook_event_name": "stop",
            "cursor_version": "9.99.1",
            "workspace_roots": ["/repo"],
        }
        route = negotiate(
            profiles(),
            host_family="cursor",
            canonical_event="session.stop",
            host_event="stop",
            payload=payload,
            preferred_response_shapes=["claude.nested.stop.v1"],
        )
        self.assertEqual(route["state"], "HYBRIDIZED")
        self.assertEqual(route["selected"]["response_shape"], "claude.nested.stop.v1")
        encoded = encode_decision(
            profiles(),
            profile_id=route["selected"]["profile_id"],
            response_shape="claude.nested.stop.v1",
            canonical_event="session.stop",
            decision=HookDecision(action="FOLLOW_UP", message="Need another pass."),
        )
        self.assertEqual(
            encoded,
            {
                "hookSpecificOutput": {
                    "decision": "block",
                    "reason": "Need another pass.",
                }
            },
        )

    def test_codex_user_prompt_uses_codex_profile_and_block_shape(self) -> None:
        route = negotiate(
            profiles(),
            host_family="codex",
            canonical_event="prompt.submit",
            host_event="UserPromptSubmit",
            payload={
                "cwd": "/repo",
                "hook_event_name": "UserPromptSubmit",
                "model": "gpt",
                "permission_mode": "default",
                "prompt": "deploy",
                "session_id": "session-secret",
                "turn_id": "turn-secret",
            },
            host_version="synthetic-codex-1",
        )
        self.assertEqual(route["state"], "MATCHED")
        self.assertEqual(route["selected"]["profile_id"], "codex-lifecycle-user-prompt-v1")
        response = encode_decision(
            profiles(),
            profile_id=route["selected"]["profile_id"],
            response_shape=route["selected"]["response_shape"],
            canonical_event="prompt.submit",
            decision=HookDecision(action="BLOCK", message="Need approval."),
        )
        self.assertEqual(response, {"decision": "block", "reason": "Need approval."})

    def test_shape_observation_persists_structure_not_values(self) -> None:
        receipt = observe_shape(
            host_family="cursor",
            host_event="beforeSubmitPrompt",
            host_version="1.2.3",
            payload={
                "prompt": "super secret prompt",
                "conversation_id": "private-id",
                "attachments": [{"path": "private.txt"}],
            },
        )
        serialized = json.dumps(receipt)
        self.assertNotIn("super secret prompt", serialized)
        self.assertNotIn("private-id", serialized)
        self.assertNotIn("private.txt", serialized)
        self.assertIn("prompt:string", receipt["fingerprint"]["field_types"])
        self.assertFalse(receipt["content_persisted"])

    def test_config_renderer_switches_between_cursor_and_claude_codex_shapes(self) -> None:
        bindings = [
            {
                "canonical_event": "prompt.submit",
                "command": "python hooks/prompt.py",
                "timeout": 7,
                "fail_closed": False,
            },
            {
                "canonical_event": "session.stop",
                "command": "python hooks/stop.py",
                "timeout": 9,
                "fail_closed": True,
            },
        ]
        cursor = render_config(config_shape="cursor-native-config-v1", bindings=bindings)
        self.assertEqual(cursor["version"], 1)
        self.assertEqual(
            cursor["hooks"]["beforeSubmitPrompt"][0]["failClosed"],
            False,
        )
        self.assertEqual(cursor["hooks"]["stop"][0]["failClosed"], True)

        compatible = render_config(
            config_shape="claude-codex-group-config-v1",
            bindings=bindings,
        )
        self.assertIn("UserPromptSubmit", compatible["hooks"])
        self.assertIn("Stop", compatible["hooks"])
        self.assertEqual(
            compatible["hooks"]["UserPromptSubmit"][0]["hooks"][0]["type"],
            "command",
        )

    def test_host_families_do_not_cross_match(self) -> None:
        route = negotiate(
            profiles(),
            host_family="codex",
            canonical_event="prompt.submit",
            host_event="beforeSubmitPrompt",
            payload={"prompt": "hello"},
        )
        self.assertEqual(route["state"], "UNKNOWN_SHAPE")

    def test_unadmitted_response_shape_fails_closed(self) -> None:
        with self.assertRaises(ProtocolFabricError):
            encode_decision(
                profiles(),
                profile_id="cursor-native-common-envelope-v2",
                response_shape="totally-unknown",
                canonical_event="session.stop",
                decision=HookDecision(action="ALLOW"),
            )

    def test_shape_fingerprint_is_deterministic_by_key_and_type_only(self) -> None:
        left = shape_fingerprint({"a": "one", "b": 1})
        right = shape_fingerprint({"b": 999, "a": "two"})
        self.assertEqual(left["shape_sha256"], right["shape_sha256"])
        self.assertEqual(left["field_types"], ["a:string", "b:integer"])


class ShapeLifecycleContractTests(unittest.TestCase):
    def _profile(self, profile_id: str) -> dict:
        return next(
            item for item in load_profiles(registry_value()) if item["profile_id"] == profile_id
        )

    def test_registry_lifecycle_model_matches_owner_vocabulary(self) -> None:
        model = registry_value()["lifecycle_model"]
        self.assertTrue(model["dimensions_are_orthogonal"])
        self.assertEqual(model["catalog_states"], list(FABRIC.CATALOG_STATES))
        self.assertEqual(model["validation_states"], list(FABRIC.VALIDATION_STATES))
        self.assertEqual(model["proof_classes"], list(FABRIC.PROOF_CLASSES))
        self.assertEqual(
            model["routing_eligibilities"], list(FABRIC.ROUTING_ELIGIBILITIES)
        )
        self.assertEqual(model["rollout_stages"], list(FABRIC.ROLLOUT_STAGES))

    def test_every_tracked_profile_declares_a_valid_lifecycle(self) -> None:
        for profile in load_profiles(registry_value()):
            lifecycle = profile["lifecycle"]
            self.assertEqual(lifecycle["catalog_state"] in FABRIC.CATALOG_STATES, True)
            self.assertEqual(
                lifecycle["routing_eligibility"],
                validate_lifecycle(lifecycle)["routing_eligibility"],
            )
            self.assertNotIn("payload", lifecycle)

    def test_profile_without_lifecycle_is_rejected(self) -> None:
        profile = dict(self._profile("cursor-native-common-envelope-v2"))
        profile.pop("lifecycle")
        with self.assertRaises(ProtocolFabricError):
            FABRIC.validate_profile(profile)

    def test_prospective_synthetic_pass_stays_prospective(self) -> None:
        lifecycle = self._profile("cursor-native-common-envelope-v3-prospective")["lifecycle"]
        self.assertEqual(lifecycle["catalog_state"], "PROSPECTIVE")
        self.assertEqual(lifecycle["validation_state"], "PASS")
        self.assertEqual(lifecycle["proof_class"], "SYNTHETIC")
        self.assertEqual(lifecycle["routing_eligibility"], "CANARY_ELIGIBLE")
        self.assertEqual(lifecycle["max_routing_eligibility"], "CANARY_ELIGIBLE")
        self.assertNotEqual(lifecycle["routing_eligibility"], "AUTO_SWITCH_ELIGIBLE")

    def test_prospective_candidate_never_displaces_a_viable_active_shape(self) -> None:
        route = negotiate(
            load_profiles(registry_value()),
            host_family="cursor",
            canonical_event="prompt.submit",
            host_event="beforeSubmitPrompt",
            payload={
                "prompt": "hello",
                "hook_event_name": "beforeSubmitPrompt",
                "cursor_version": "13.0.0",
                "workspace_roots": ["/repo"],
                "agent_protocol_version": "3",
            },
        )
        self.assertEqual(route["state"], "MATCHED")
        self.assertEqual(route["selected"]["profile_id"], "cursor-native-common-envelope-v2")
        self.assertEqual(route["selection_basis"], "ACTIVE_PREFERRED")
        viable = [
            item["profile_id"]
            for item in route["candidates"]
            if not item["missing_required"]
        ]
        self.assertIn("cursor-native-common-envelope-v3-prospective", viable)

    def test_rejected_prospective_candidate_is_retained_observe_only(self) -> None:
        lifecycle = self._profile("cursor-native-prompt-rename-v0-prospective")["lifecycle"]
        self.assertEqual(lifecycle["catalog_state"], "PROSPECTIVE")
        self.assertEqual(lifecycle["validation_state"], "FAIL")
        self.assertTrue(lifecycle["retained_negative_evidence"])
        self.assertEqual(lifecycle["routing_eligibility"], "OBSERVE_ONLY")
        self.assertEqual(lifecycle["max_routing_eligibility"], "OBSERVE_ONLY")

    def test_active_regression_degrades_without_silent_prospective_fallback(self) -> None:
        route = negotiate(
            load_profiles(registry_value()),
            host_family="cursor",
            canonical_event="prompt.submit",
            host_event="beforeSubmitPrompt",
            payload={
                "text": "renamed prompt",
                "hook_event_name": "beforeSubmitPrompt",
                "cursor_version": "13.0.0",
                "workspace_roots": ["/repo"],
            },
        )
        self.assertEqual(route["state"], "UNKNOWN_SHAPE")
        self.assertEqual(route["reason"], "ACTIVE_SHAPE_REGRESSION")
        self.assertIsNone(route["selected"])
        self.assertTrue(route["lifecycle_safety"]["degraded"])
        self.assertEqual(route["lifecycle_safety"]["prospective_fallback"], "NOT_PERFORMED")
        self.assertEqual(
            route["lifecycle_safety"]["active_profiles_regressed"],
            ["cursor-native-common-envelope-v2"],
        )
        self.assertEqual(route["safety"]["policy_decision"], "DEFER_TO_CONSUMER")

    def test_legacy_fallback_requires_explicitly_admitted_compatibility(self) -> None:
        route = negotiate(
            load_profiles(registry_value()),
            host_family="cursor",
            canonical_event="session.stop",
            host_event="legacyStop",
            payload={"status": "completed", "legacy_loop": 0},
        )
        self.assertEqual(route["state"], "OBSERVE_ONLY_SHAPE")
        self.assertIsNone(route["selected"])
        observed = [item["profile_id"] for item in route["observed_profiles"]]
        self.assertEqual(observed, ["cursor-native-legacy-stop-v0"])
        self.assertEqual(route["lifecycle_safety"]["prospective_fallback"], "NOT_PERFORMED")

    def test_legacy_shape_with_admitted_compatibility_is_a_marked_fallback(self) -> None:
        route = negotiate(
            load_profiles(registry_value()),
            host_family="cursor",
            canonical_event="prompt.submit",
            host_event="beforeSubmitPrompt",
            payload={"prompt": "hello"},
        )
        self.assertEqual(route["state"], "MATCHED")
        self.assertEqual(route["selected"]["profile_id"], "cursor-native-minimal-v1")
        self.assertEqual(route["selection_basis"], "COMPATIBILITY_FALLBACK")
        self.assertEqual(route["lifecycle"]["catalog_state"], "LEGACY")

    def test_prospective_only_shape_is_routable_with_an_explicit_canary_marker(self) -> None:
        route = negotiate(
            load_profiles(registry_value()),
            host_family="cursor",
            canonical_event="prompt.submit",
            host_event="promptSubmittedFuture",
            payload={
                "prompt": "hello",
                "hook_event_name": "promptSubmittedFuture",
                "cursor_version": "13.0.0",
                "agent_protocol_version": "3",
            },
        )
        self.assertEqual(route["state"], "MATCHED")
        self.assertEqual(
            route["selected"]["profile_id"],
            "cursor-native-common-envelope-v3-prospective",
        )
        self.assertEqual(route["selection_basis"], "PROSPECTIVE_CANDIDATE")
        self.assertTrue(route["canary_confirmation_required"])

    def test_documentation_cannot_prove_validation_pass(self) -> None:
        with self.assertRaises(ProtocolFabricError):
            validate_lifecycle(
                {
                    "catalog_state": "ACTIVE",
                    "validation_state": "PASS",
                    "proof_class": "DOCUMENTED",
                    "routing_eligibility": "OBSERVE_ONLY",
                    "rollout_stage": "PROFILED",
                    "compatibility_admitted": False,
                }
            )

    def test_synthetic_proof_cannot_claim_auto_switch_eligibility(self) -> None:
        with self.assertRaises(ProtocolFabricError):
            validate_lifecycle(
                {
                    "catalog_state": "ACTIVE",
                    "validation_state": "PASS",
                    "proof_class": "SYNTHETIC",
                    "routing_eligibility": "AUTO_SWITCH_ELIGIBLE",
                    "rollout_stage": "SYNTHETIC_PROVEN",
                    "compatibility_admitted": False,
                }
            )

    def test_active_failure_requires_explicit_quarantine(self) -> None:
        declaration = {
            "catalog_state": "ACTIVE",
            "validation_state": "FAIL",
            "proof_class": "SYNTHETIC",
            "routing_eligibility": "OBSERVE_ONLY",
            "rollout_stage": "PROFILED",
            "compatibility_admitted": False,
            "quarantined": False,
        }
        with self.assertRaises(ProtocolFabricError):
            validate_lifecycle(declaration)
        declaration["quarantined"] = True
        normalized = validate_lifecycle(declaration)
        self.assertTrue(normalized["degraded"])
        self.assertEqual(normalized["routing_eligibility"], "OBSERVE_ONLY")

    def test_max_routing_ceiling_is_monotone_across_dimensions(self) -> None:
        base = {
            "catalog_state": "ACTIVE",
            "validation_state": "PASS",
            "proof_class": "SYNTHETIC",
            "routing_eligibility": "CANARY_ELIGIBLE",
            "rollout_stage": "SYNTHETIC_PROVEN",
            "compatibility_admitted": False,
        }
        self.assertEqual(max_routing_eligibility(base), "CANARY_ELIGIBLE")
        self.assertEqual(
            max_routing_eligibility({**base, "proof_class": "LIVE_CANARY"}),
            "AUTO_SWITCH_ELIGIBLE",
        )
        self.assertEqual(
            max_routing_eligibility({**base, "proof_class": "DOCUMENTED"}),
            "OBSERVE_ONLY",
        )
        self.assertEqual(
            max_routing_eligibility({**base, "validation_state": "UNTESTED"}),
            "OBSERVE_ONLY",
        )
        self.assertEqual(
            max_routing_eligibility(
                {**base, "proof_class": "LIVE_CANARY", "catalog_state": "PROSPECTIVE"}
            ),
            "CANARY_ELIGIBLE",
        )
        self.assertEqual(
            max_routing_eligibility(
                {
                    **base,
                    "proof_class": "LIVE_CANARY",
                    "catalog_state": "LEGACY",
                    "compatibility_admitted": False,
                }
            ),
            "OBSERVE_ONLY",
        )


if __name__ == "__main__":
    unittest.main()
