from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAP = ROOT / "capabilities" / "social-publication"
FIXTURE = CAP / "fixtures" / "text-intent.synthetic.v1.json"
PROTOTYPE = CAP / "prototype.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CORE = load_module("automation_social_publication_core", CAP / "core" / "publication.py")
LINKEDIN = load_module(
    "automation_social_publication_linkedin",
    CAP / "adapters" / "linkedin.py",
)


class SocialPublicationP95Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.intent = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_capability_is_explicitly_p95_prototype_only(self) -> None:
        cap = json.loads((CAP / "capability.v1.json").read_text(encoding="utf-8"))
        self.assertEqual(cap["capability_id"], "social-publication")
        self.assertEqual(cap["status"], "PROGRAM_DESIGN_PROTOTYPE_PROVEN")
        self.assertEqual(cap["production_use_path"], "UNDECLARED")
        self.assertIn("Live OAuth", cap["proof_ceiling"])

    def test_content_hash_is_stable_and_changes_with_publishable_text(self) -> None:
        first = CORE.content_sha256(self.intent)
        second = CORE.content_sha256(json.loads(json.dumps(self.intent)))
        self.assertEqual(first, second)

        changed = json.loads(json.dumps(self.intent))
        changed["content"]["text"] += " changed"
        self.assertNotEqual(first, CORE.content_sha256(changed))

    def test_request_id_does_not_change_publishable_content_identity(self) -> None:
        first = CORE.content_sha256(self.intent)
        changed = json.loads(json.dumps(self.intent))
        changed["request_id"] = "different-bookkeeping-id"
        self.assertEqual(first, CORE.content_sha256(changed))

    def test_unexpected_intent_fields_fail_closed(self) -> None:
        changed = json.loads(json.dumps(self.intent))
        changed["schedule_at"] = "future"
        errors = CORE.validate_intent(changed)
        self.assertTrue(any("unexpected intent fields" in error for error in errors))

        changed = json.loads(json.dumps(self.intent))
        changed["content"]["provider_hint"] = "not-approved"
        errors = CORE.validate_intent(changed)
        self.assertTrue(any("unexpected content fields" in error for error in errors))

    def test_whitespace_only_runtime_inputs_fail_closed(self) -> None:
        for field in ("request_id", "provider"):
            with self.subTest(field=field):
                changed = json.loads(json.dumps(self.intent))
                changed[field] = "   "
                self.assertTrue(CORE.validate_intent(changed))

        changed = json.loads(json.dumps(self.intent))
        changed["content"]["text"] = "   "
        self.assertTrue(CORE.validate_intent(changed))

    def test_intent_schema_matches_runtime_non_whitespace_rule(self) -> None:
        schema = json.loads(
            (CAP / "schemas" / "publication-intent.v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["request_id"]["pattern"], r".*\S.*")
        self.assertEqual(schema["properties"]["provider"]["pattern"], r".*\S.*")
        self.assertEqual(
            schema["properties"]["content"]["properties"]["text"]["pattern"],
            r".*\S.*",
        )

    def test_stale_approval_blocks_before_provider_request(self) -> None:
        calls = []

        def build(_intent):
            calls.append("build")
            return {}

        def send(_request):
            calls.append("send")
            return {"status_code": 201, "headers": {"x-restli-id": "unexpected"}}

        receipt = CORE.execute_approved_publication(
            self.intent,
            approved_content_sha256="0" * 64,
            build_provider_request=build,
            send_provider_request=send,
        )
        self.assertEqual(receipt["state"], "BLOCKED_STALE_APPROVAL")
        self.assertEqual(receipt["provider_request_state"], "NOT_EMITTED")
        self.assertEqual(calls, [])

    def test_missing_approval_blocks_before_provider_request(self) -> None:
        calls = []

        def build(_intent):
            calls.append("build")
            return {}

        def send(_request):
            calls.append("send")
            return {"status_code": 201, "headers": {"x-restli-id": "unexpected"}}

        receipt = CORE.execute_approved_publication(
            self.intent,
            approved_content_sha256=None,
            build_provider_request=build,
            send_provider_request=send,
        )
        self.assertEqual(receipt["state"], "BLOCKED_APPROVAL_REQUIRED")
        self.assertEqual(receipt["provider_request_state"], "NOT_EMITTED")
        self.assertEqual(calls, [])

    def test_provider_request_build_exception_becomes_secret_free_receipt(self) -> None:
        approved = CORE.content_sha256(self.intent)

        def build(_intent):
            raise ValueError("Bearer secret-should-never-escape")

        receipt = CORE.execute_approved_publication(
            self.intent,
            approved_content_sha256=approved,
            build_provider_request=build,
            send_provider_request=lambda _request: {},
        )
        self.assertEqual(receipt["state"], "PROVIDER_REQUEST_BUILD_FAILED")
        self.assertEqual(receipt["provider_request_state"], "NOT_EMITTED")
        self.assertEqual(receipt["error_class"], "PROVIDER_REQUEST_BUILD")
        self.assertNotIn("secret-should-never-escape", json.dumps(receipt))

    def test_transport_exception_has_unknown_emission_state(self) -> None:
        approved = CORE.content_sha256(self.intent)

        def send(_request):
            raise TimeoutError("access_token=secret-should-never-escape")

        receipt = CORE.execute_approved_publication(
            self.intent,
            approved_content_sha256=approved,
            build_provider_request=lambda _intent: {"method": "POST"},
            send_provider_request=send,
        )
        self.assertEqual(receipt["state"], "PROVIDER_TRANSPORT_FAILED")
        self.assertEqual(receipt["provider_request_state"], "UNKNOWN")
        self.assertEqual(receipt["error_class"], "PROVIDER_TRANSPORT")
        self.assertNotIn("secret-should-never-escape", json.dumps(receipt))

    def test_linkedin_adapter_builds_current_text_post_shape_without_token(self) -> None:
        request = LINKEDIN.build_text_post_request(
            self.intent,
            author_urn="urn:li:person:synthetic-member",
            linkedin_version="202606",
        )
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["url"], "https://api.linkedin.com/rest/posts")
        self.assertEqual(request["headers"]["Linkedin-Version"], "202606")
        self.assertEqual(
            request["headers"]["X-Restli-Protocol-Version"],
            "2.0.0",
        )
        self.assertEqual(
            request["json"]["author"],
            "urn:li:person:synthetic-member",
        )
        self.assertEqual(
            request["json"]["commentary"],
            self.intent["content"]["text"],
        )
        serialized = json.dumps(request).lower()
        self.assertNotIn("authorization", serialized)
        self.assertNotIn("bearer ", serialized)
        self.assertNotIn("access_token", serialized)

    def test_success_prototype_reaches_terminal_published_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "receipt.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(PROTOTYPE),
                    "--intent",
                    str(FIXTURE),
                    "--mode",
                    "success",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            receipt = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(receipt["state"], "PUBLISHED")
            self.assertEqual(receipt["provider_request_state"], "EMITTED")
            self.assertEqual(
                receipt["provider_post_id"],
                "urn:li:share:synthetic-p95-proof",
            )
            self.assertNotIn("prototype_mode", receipt)

    def test_stale_approval_prototype_is_non_mutating_failure(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(PROTOTYPE),
                "--intent",
                str(FIXTURE),
                "--mode",
                "stale-approval",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        receipt = json.loads(proc.stdout)
        self.assertEqual(receipt["state"], "BLOCKED_STALE_APPROVAL")
        self.assertEqual(receipt["provider_request_state"], "NOT_EMITTED")

    def test_http_201_without_post_id_is_not_terminal_proof(self) -> None:
        approved = CORE.content_sha256(self.intent)
        receipt = CORE.execute_approved_publication(
            self.intent,
            approved_content_sha256=approved,
            build_provider_request=lambda _intent: {"method": "POST"},
            send_provider_request=lambda _request: {"status_code": 201, "headers": {}},
        )
        self.assertEqual(receipt["state"], "PROVIDER_RESPONSE_INCOMPLETE")
        self.assertEqual(receipt["provider_request_state"], "EMITTED")
        self.assertIsNone(receipt["provider_post_id"])
        self.assertEqual(receipt["error_class"], "MISSING_PROVIDER_POST_ID")

    def test_provider_authorization_failure_is_explicit_and_secret_free(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(PROTOTYPE),
                "--intent",
                str(FIXTURE),
                "--mode",
                "provider-auth-failure",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        receipt = json.loads(proc.stdout)
        self.assertEqual(receipt["state"], "PROVIDER_AUTHORIZATION_FAILED")
        self.assertEqual(receipt["provider_request_state"], "EMITTED")
        self.assertEqual(receipt["error_class"], "AUTHORIZATION")
        serialized = json.dumps(receipt).lower()
        self.assertNotIn("authorization:", serialized)
        self.assertNotIn("bearer ", serialized)
        self.assertNotIn("token", serialized)

    def test_non_linkedin_prototype_returns_provider_neutral_build_failure(self) -> None:
        changed = json.loads(json.dumps(self.intent))
        changed["provider"] = "other-provider"
        with tempfile.TemporaryDirectory() as tmp:
            intent_path = Path(tmp) / "intent.json"
            intent_path.write_text(json.dumps(changed), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(PROTOTYPE),
                    "--intent",
                    str(intent_path),
                    "--mode",
                    "success",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(proc.returncode, 2, proc.stderr)
        receipt = json.loads(proc.stdout)
        self.assertEqual(receipt["state"], "PROVIDER_REQUEST_BUILD_FAILED")
        self.assertEqual(receipt["provider_request_state"], "NOT_EMITTED")

    def test_receipt_schema_is_closed_and_published_requires_post_id(self) -> None:
        schema = json.loads(
            (CAP / "schemas" / "publication-receipt.v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("provider_request_state", schema["required"])
        self.assertIn("provider_post_id", schema["required"])
        self.assertEqual(
            schema["properties"]["provider_request_state"]["enum"],
            ["NOT_EMITTED", "EMITTED", "UNKNOWN"],
        )
        published_rule = schema["allOf"][0]
        self.assertEqual(
            published_rule["if"]["properties"]["state"]["const"],
            "PUBLISHED",
        )
        self.assertEqual(
            published_rule["then"]["properties"]["provider_post_id"]["minLength"],
            1,
        )
        self.assertEqual(
            published_rule["then"]["properties"]["provider_request_state"]["const"],
            "EMITTED",
        )

    def test_design_doc_proves_alternatives_success_failure_and_terminal_value(self) -> None:
        doc = (ROOT / "docs" / "P95_LINKEDIN_PUBLICATION_ARCHITECTURE.md").read_text(
            encoding="utf-8"
        )
        for required in (
            "## Design alternatives",
            "## Success call stack",
            "## Failure call stack — stale approval",
            "## Failure call stack — provider authorization",
            "terminal user value",
            "## Second-pass critique",
            "## Exact implementation seam",
        ):
            self.assertIn(required, doc)

    def test_public_fixture_contains_no_private_locator_or_secret_material(self) -> None:
        serialized = FIXTURE.read_text(encoding="utf-8").lower()
        for forbidden in (
            "drive.google.com",
            "docs.google.com",
            "access_token",
            "refresh_token",
            "client_secret",
            "password",
            "cookie",
            "c:\\users\\",
            "/home/",
        ):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
