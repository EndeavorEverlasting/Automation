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
