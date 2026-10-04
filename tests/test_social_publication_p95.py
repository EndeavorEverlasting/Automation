from __future__ import annotations

import importlib.util
import json
import shutil
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

    def execute(self, intent, *, approved, build, send, translate=LINKEDIN.translate_post_response):
        return CORE.execute_approved_publication(
            intent,
            approved_content_sha256=approved,
            build_provider_request=build,
            send_provider_request=send,
            translate_provider_response=translate,
        )

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
        self.assertTrue(
            any(
                "unexpected intent fields" in error
                for error in CORE.validate_intent(changed)
            )
        )
        changed = json.loads(json.dumps(self.intent))
        changed["content"]["provider_hint"] = "not-approved"
        self.assertTrue(
            any(
                "unexpected content fields" in error
                for error in CORE.validate_intent(changed)
            )
        )

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
        receipt = self.execute(
            self.intent,
            approved="0" * 64,
            build=lambda _intent: calls.append("build") or {},
            send=lambda _request: calls.append("send") or {},
        )
        self.assertEqual(receipt["state"], "BLOCKED_STALE_APPROVAL")
        self.assertEqual(receipt["provider_request_state"], "NOT_EMITTED")
        self.assertEqual(calls, [])

    def test_missing_approval_blocks_before_provider_request(self) -> None:
        calls = []
        receipt = self.execute(
            self.intent,
            approved=None,
            build=lambda _intent: calls.append("build") or {},
            send=lambda _request: calls.append("send") or {},
        )
        self.assertEqual(receipt["state"], "BLOCKED_APPROVAL_REQUIRED")
        self.assertEqual(receipt["provider_request_state"], "NOT_EMITTED")
        self.assertEqual(calls, [])

    def test_provider_request_build_exception_becomes_secret_free_receipt(self) -> None:
        approved = CORE.content_sha256(self.intent)

        def build(_intent):
            raise ValueError("Bearer secret-should-never-escape")

        receipt = self.execute(
            self.intent,
            approved=approved,
            build=build,
            send=lambda _request: {},
        )
        self.assertEqual(receipt["state"], "PROVIDER_REQUEST_BUILD_FAILED")
        self.assertEqual(receipt["provider_request_state"], "NOT_EMITTED")
        self.assertEqual(receipt["error_class"], "PROVIDER_REQUEST_BUILD")
        self.assertNotIn("secret-should-never-escape", json.dumps(receipt))

    def test_transport_exception_has_unknown_emission_state(self) -> None:
        approved = CORE.content_sha256(self.intent)

        def send(_request):
            raise TimeoutError("access_token=secret-should-never-escape")

        receipt = self.execute(
            self.intent,
            approved=approved,
            build=lambda _intent: {"method": "POST"},
            send=send,
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
            request["headers"]["X-Restli-Protocol-Version"], "2.0.0"
        )
        self.assertEqual(
            request["json"]["author"], "urn:li:person:synthetic-member"
        )
        self.assertEqual(
            request["json"]["commentary"], self.intent["content"]["text"]
        )
        serialized = json.dumps(request).lower()
        self.assertNotIn("authorization", serialized)
        self.assertNotIn("bearer ", serialized)
        self.assertNotIn("access_token", serialized)

    def test_linkedin_adapter_translates_provider_response_to_neutral_result(self) -> None:
        published = LINKEDIN.translate_post_response(
            {
                "status_code": 201,
                "headers": {"x-restli-id": "urn:li:share:synthetic"},
            }
        )
        self.assertEqual(published["outcome"], "PUBLISHED")
        self.assertEqual(
            published["provider_post_id"], "urn:li:share:synthetic"
        )

        auth = LINKEDIN.translate_post_response(
            {"status_code": 401, "headers": {}}
        )
        self.assertEqual(auth["outcome"], "AUTHORIZATION_FAILED")
        self.assertEqual(auth["error_class"], "AUTHORIZATION")

    def test_linkedin_server_error_is_uncertain_not_rejected(self) -> None:
        result = LINKEDIN.translate_post_response(
            {"status_code": 503, "headers": {}}
        )
        self.assertEqual(result["outcome"], "INCOMPLETE")
        self.assertEqual(
            result["error_class"], "AMBIGUOUS_PROVIDER_RESPONSE"
        )

    def test_linkedin_explicit_client_error_is_rejected(self) -> None:
        result = LINKEDIN.translate_post_response(
            {"status_code": 400, "headers": {}}
        )
        self.assertEqual(result["outcome"], "REJECTED")
        self.assertEqual(result["error_class"], "PROVIDER_REJECTION")

    def test_core_consumes_provider_neutral_result_not_linkedin_headers(self) -> None:
        approved = CORE.content_sha256(self.intent)
        neutral_result = {
            "outcome": "PUBLISHED",
            "provider_post_id": "provider-neutral-id",
            "provider_status_code": 999,
        }
        receipt = self.execute(
            self.intent,
            approved=approved,
            build=lambda _intent: {"opaque": "request"},
            send=lambda _request: {"provider-specific": "response"},
            translate=lambda _response: neutral_result,
        )
        self.assertEqual(receipt["state"], "PUBLISHED")
        self.assertEqual(receipt["provider_post_id"], "provider-neutral-id")
        self.assertEqual(receipt["provider_status_code"], 999)

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
        receipt = self.execute(
            self.intent,
            approved=approved,
            build=lambda _intent: {"method": "POST"},
            send=lambda _request: {"status_code": 201, "headers": {}},
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

    def test_receipt_schema_is_closed_and_encodes_state_invariants(self) -> None:
        schema = json.loads(
            (CAP / "schemas" / "publication-receipt.v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("provider_request_state", schema["required"])
        self.assertIn("provider_post_id", schema["required"])
        self.assertIn("provider_status_code", schema["properties"])
        self.assertIn("error_class", schema["properties"])
        self.assertEqual(
            schema["properties"]["provider_request_state"]["enum"],
            ["NOT_EMITTED", "EMITTED", "UNKNOWN"],
        )
        serialized = json.dumps(schema)
        self.assertIn('"const": "PUBLISHED"', serialized)
        self.assertIn('"minLength": 1', serialized)
        self.assertIn('"const": "UNKNOWN"', serialized)

    def test_isolated_consumer_canary_runs_with_only_capability_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            isolated = Path(tmp) / "social-publication"
            shutil.copytree(CAP, isolated)
            isolated_fixture = (
                isolated / "fixtures" / "text-intent.synthetic.v1.json"
            )
            isolated_prototype = isolated / "prototype.py"

            success = subprocess.run(
                [
                    sys.executable,
                    str(isolated_prototype),
                    "--intent",
                    str(isolated_fixture),
                    "--mode",
                    "success",
                ],
                cwd=tmp,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(success.returncode, 0, success.stderr)
            self.assertEqual(json.loads(success.stdout)["state"], "PUBLISHED")

            stale = subprocess.run(
                [
                    sys.executable,
                    str(isolated_prototype),
                    "--intent",
                    str(isolated_fixture),
                    "--mode",
                    "stale-approval",
                ],
                cwd=tmp,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(stale.returncode, 2, stale.stderr)
            self.assertEqual(
                json.loads(stale.stdout)["state"], "BLOCKED_STALE_APPROVAL"
            )

    def test_root_wayfinding_exposes_social_publication(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            "capabilities/social-publication/CAPABILITY.md",
            readme,
        )
        self.assertIn(
            "capabilities/social-publication/prototype.py",
            readme,
        )
        self.assertIn("PROGRAM_DESIGN_PROTOTYPE_PROVEN", readme)

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
