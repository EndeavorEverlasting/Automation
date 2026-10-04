from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

CAPABILITY_DIR = Path(__file__).resolve().parent
if str(CAPABILITY_DIR) not in sys.path:
    sys.path.insert(0, str(CAPABILITY_DIR))

from adapters.linkedin import build_text_post_request, translate_post_response
from core.publication import execute_approved_publication, prepare_preview


def _load_intent(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("intent root must be an object")
    return payload


def _success_transport(_request: dict[str, Any]) -> dict[str, Any]:
    return {
        "status_code": 201,
        "headers": {"x-restli-id": "urn:li:share:synthetic-p95-proof"},
    }


def _authorization_failure_transport(_request: dict[str, Any]) -> dict[str, Any]:
    return {
        "status_code": 401,
        "headers": {},
    }


def run_prototype(
    intent: dict[str, Any],
    *,
    mode: str,
    author_urn: str,
    linkedin_version: str,
) -> dict[str, Any]:
    preview = prepare_preview(intent)
    approval_hash = preview["content_sha256"]

    if mode == "stale-approval":
        approval_hash = "0" * 64
        transport = _success_transport
    elif mode == "provider-auth-failure":
        transport = _authorization_failure_transport
    elif mode == "success":
        transport = _success_transport
    else:
        raise ValueError(f"unknown mode: {mode}")

    def build_request(payload: dict[str, Any]) -> dict[str, Any]:
        return build_text_post_request(
            payload,
            author_urn=author_urn,
            linkedin_version=linkedin_version,
        )

    receipt = execute_approved_publication(
        intent,
        approved_content_sha256=approval_hash,
        build_provider_request=build_request,
        send_provider_request=transport,
        translate_provider_response=translate_post_response,
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intent", required=True, type=Path)
    parser.add_argument(
        "--mode",
        choices=("success", "stale-approval", "provider-auth-failure"),
        default="success",
    )
    parser.add_argument(
        "--author-urn",
        default="urn:li:person:synthetic-member",
    )
    parser.add_argument(
        "--linkedin-version",
        default="202606",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    intent = _load_intent(args.intent)
    receipt = run_prototype(
        intent,
        mode=args.mode,
        author_urn=args.author_urn,
        linkedin_version=args.linkedin_version,
    )
    serialized = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        sys.stdout.write(serialized)

    return 0 if receipt["state"] == "PUBLISHED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
