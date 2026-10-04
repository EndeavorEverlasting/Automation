from __future__ import annotations

import re
from typing import Any

LINKEDIN_POSTS_URL = "https://api.linkedin.com/rest/posts"
RESTLI_PROTOCOL_VERSION = "2.0.0"
_VERSION_RE = re.compile(r"^\d{6}$")
_PERSON_URN_RE = re.compile(r"^urn:li:person:[A-Za-z0-9_-]+$")


def build_text_post_request(
    intent: dict[str, Any],
    *,
    author_urn: str,
    linkedin_version: str,
) -> dict[str, Any]:
    if intent.get("provider") != "linkedin":
        raise ValueError("LinkedIn adapter requires provider='linkedin'")
    content = intent.get("content")
    if not isinstance(content, dict) or content.get("type") != "text":
        raise ValueError("LinkedIn P95 adapter prototype supports text content only")
    if not _PERSON_URN_RE.fullmatch(author_urn):
        raise ValueError("author_urn must be a LinkedIn Person URN")
    if not _VERSION_RE.fullmatch(linkedin_version):
        raise ValueError("linkedin_version must use YYYYMM format")

    return {
        "method": "POST",
        "url": LINKEDIN_POSTS_URL,
        "headers": {
            "Content-Type": "application/json",
            "Linkedin-Version": linkedin_version,
            "X-Restli-Protocol-Version": RESTLI_PROTOCOL_VERSION,
        },
        "json": {
            "author": author_urn,
            "commentary": content["text"],
            "visibility": intent["visibility"],
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        },
        "runtime_secret_requirements": [
            "OAuth access token with w_member_social"
        ],
    }


def translate_post_response(response: Any) -> dict[str, Any]:
    if not isinstance(response, dict):
        return {
            "outcome": "INCOMPLETE",
            "error_class": "INVALID_PROVIDER_RESPONSE",
        }

    status_code = response.get("status_code")
    headers = response.get("headers") or {}
    if not isinstance(headers, dict):
        headers = {}

    if status_code == 201:
        post_id = headers.get("x-restli-id") or headers.get("X-RestLi-Id")
        if isinstance(post_id, str) and post_id.strip():
            return {
                "outcome": "PUBLISHED",
                "provider_post_id": post_id,
                "provider_status_code": status_code,
            }
        return {
            "outcome": "INCOMPLETE",
            "provider_status_code": status_code,
            "error_class": "MISSING_PROVIDER_POST_ID",
        }

    if status_code in (401, 403):
        return {
            "outcome": "AUTHORIZATION_FAILED",
            "provider_status_code": status_code,
            "error_class": "AUTHORIZATION",
        }

    if isinstance(status_code, int) and 400 <= status_code < 500:
        return {
            "outcome": "REJECTED",
            "provider_status_code": status_code,
            "error_class": "PROVIDER_REJECTION",
        }

    return {
        "outcome": "INCOMPLETE",
        "provider_status_code": status_code if isinstance(status_code, int) else None,
        "error_class": "AMBIGUOUS_PROVIDER_RESPONSE",
    }
