from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAP = ROOT / "capabilities" / "agent-hook-runtime"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


TRANSPORT = _load_module(
    "automation_agent_hook_transport",
    CAP / "core" / "transport.py",
)
CURSOR = _load_module(
    "automation_agent_hook_cursor_adapter",
    CAP / "adapters" / "cursor.py",
)
parse_json_object = TRANSPORT.parse_json_object
read_json_object = TRANSPORT.read_json_object
neutral_response = CURSOR.neutral_response
validate_event = CURSOR.validate_event


class AgentHookRuntimeTests(unittest.TestCase):
    def test_valid_utf8_object_parses_without_persisting_values(self) -> None:
        raw = json.dumps({"prompt": "private words", "attachments": []}).encode()
        payload, receipt = parse_json_object(raw)
        self.assertEqual(payload["prompt"], "private words")
        self.assertEqual(receipt["state"], "PARSED")
        self.assertEqual(receipt["payload_keys"], ["attachments", "prompt"])
        self.assertFalse(receipt["content_persisted"])
        self.assertTrue(receipt["input_complete"])
        self.assertNotIn("private words", json.dumps(receipt))

    def test_utf8_bom_is_normalized(self) -> None:
        raw = b"\xef\xbb\xbf" + json.dumps({"prompt": "hello"}).encode()
        payload, receipt = parse_json_object(raw)
        self.assertEqual(payload, {"prompt": "hello"})
        self.assertEqual(receipt["encoding"], "utf-8-sig")
        self.assertEqual(receipt["state"], "PARSED")

    def test_utf16_bom_is_normalized(self) -> None:
        raw = json.dumps({"status": "completed", "loop_count": 0}).encode("utf-16")
        payload, receipt = parse_json_object(raw)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(receipt["encoding"], "utf-16")
        self.assertEqual(receipt["state"], "PARSED")

    def test_invalid_json_receipt_is_privacy_safe(self) -> None:
        payload, receipt = parse_json_object(b'{"prompt":"secret",')
        self.assertIsNone(payload)
        self.assertEqual(receipt["state"], "INVALID_JSON")
        self.assertNotIn("secret", json.dumps(receipt))

    def test_stream_read_is_bounded(self) -> None:
        payload, receipt = read_json_object(io.BytesIO(b"x" * 17), max_bytes=16)
        self.assertIsNone(payload)
        self.assertEqual(receipt["state"], "INPUT_TOO_LARGE")
        self.assertFalse(receipt["input_complete"])
        self.assertEqual(receipt["limit_bytes"], 16)
        self.assertEqual(receipt["byte_length"], 17)

    def test_cursor_before_submit_uses_documented_shape_only(self) -> None:
        valid = validate_event("beforeSubmitPrompt", {"prompt": "P07", "attachments": []})
        self.assertEqual(valid["state"], "VALID")
        self.assertEqual(neutral_response("beforeSubmitPrompt"), {"continue": True})

    def test_cursor_before_submit_validates_attachment_items(self) -> None:
        invalid = validate_event(
            "beforeSubmitPrompt",
            {"prompt": "hello", "attachments": [42, {"type": "other", "file_path": ""}]},
        )
        self.assertEqual(invalid["state"], "INVALID_EVENT_SCHEMA")
        fields = {item["field"] for item in invalid["errors"]}
        self.assertIn("attachments[0]", fields)
        self.assertIn("attachments[1].type", fields)
        self.assertIn("attachments[1].file_path", fields)

    def test_cursor_before_submit_does_not_require_conversation_id(self) -> None:
        result = validate_event("beforeSubmitPrompt", {"prompt": "hello"})
        self.assertEqual(result["state"], "VALID")

    def test_cursor_stop_does_not_require_conversation_id(self) -> None:
        result = validate_event("stop", {"status": "completed", "loop_count": 0})
        self.assertEqual(result["state"], "VALID")

    def test_cursor_session_start_exports_documented_session_id(self) -> None:
        payload = {
            "session_id": "session-123",
            "is_background_agent": False,
            "composer_mode": "agent",
        }
        result = validate_event("sessionStart", payload)
        self.assertEqual(result["state"], "VALID")
        self.assertEqual(
            neutral_response("sessionStart", payload),
            {"env": {"AUTOMATION_CURSOR_SESSION_ID": "session-123"}},
        )

    def test_probe_allow_mode_never_blocks_invalid_json(self) -> None:
        script = CAP / "diagnose_cursor_hook.py"
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--event",
                    "beforeSubmitPrompt",
                    "--failure-policy",
                    "allow",
                    "--receipt-dir",
                    tmp,
                ],
                input="{invalid",
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "CURSOR_VERSION": "test-version"},
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout), {"continue": True})
            receipts = list(Path(tmp).glob("cursor-hook-beforeSubmitPrompt-*.json"))
            self.assertEqual(len(receipts), 1)
            receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
            self.assertEqual(receipt["transport"]["state"], "INVALID_JSON")
            self.assertEqual(receipt["cursor_version"], "test-version")
            self.assertFalse(receipt["transport"]["content_persisted"])

    def test_probe_allow_mode_does_not_export_invalid_session(self) -> None:
        script = CAP / "diagnose_cursor_hook.py"
        proc = subprocess.run(
            [
                sys.executable,
                str(script),
                "--event",
                "sessionStart",
                "--failure-policy",
                "allow",
            ],
            input=json.dumps({"session_id": "session-123"}),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {})

    def test_optional_receipt_io_failure_does_not_kill_hook(self) -> None:
        script = CAP / "diagnose_cursor_hook.py"
        with tempfile.TemporaryDirectory() as tmp:
            not_a_directory = Path(tmp) / "receipt-target"
            not_a_directory.write_text("occupied", encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--event",
                    "beforeSubmitPrompt",
                    "--failure-policy",
                    "allow",
                    "--receipt-dir",
                    str(not_a_directory),
                ],
                input=json.dumps({"prompt": "hello"}),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout), {"continue": True})

    def test_probe_block_mode_blocks_invalid_json(self) -> None:
        script = CAP / "diagnose_cursor_hook.py"
        proc = subprocess.run(
            [
                sys.executable,
                str(script),
                "--event",
                "beforeSubmitPrompt",
                "--failure-policy",
                "block",
            ],
            input="{invalid",
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertFalse(result["continue"])
        self.assertIn("transport/schema", result["user_message"])


if __name__ == "__main__":
    unittest.main()
