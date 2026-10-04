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


def profiles() -> list[dict]:
    value = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return load_profiles(value)


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


if __name__ == "__main__":
    unittest.main()
