from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

INTENT_SCHEMA = "social-publication-intent/v1"
RECEIPT_SCHEMA = "social-publication-receipt/v1"
_ALLOWED_INTENT_FIELDS = {
    "schema_version",
    "request_id",
    "provider",
    "content",
    "visibility",
}
_ALLOWED_CONTENT_FIELDS = {"type", "text"}
_PROVIDER_OUTCOME_TO_STATE = {
    "PUBLISHED": "PUBLISHED",
    "AUTHORIZATION_FAILED": "PROVIDER_AUTHORIZATION_FAILED",
    "INCOMPLETE": "PROVIDER_RESPONSE_INCOMPLETE",
    "REJECTED": "PROVIDER_REJECTED",
}


def validate_intent(intent: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(intent, dict):
        return ["intent root must be an object"]

    unexpected = sorted(set(intent) - _ALLOWED_INTENT_FIELDS)
    if unexpected:
        errors.append("unexpected intent fields: " + ", ".join(unexpected))

    if intent.get("schema_version") != INTENT_SCHEMA:
        errors.append(f"schema_version must be {INTENT_SCHEMA!r}")

    for field in ("request_id", "provider", "visibility"):
        value = intent.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string")

    if intent.get("visibility") != "PUBLIC":
        errors.append("visibility must be 'PUBLIC' in v1")

    content = intent.get("content")
    if not isinstance(content, dict):
        errors.append("content must be an object")
        return errors

    unexpected_content = sorted(set(content) - _ALLOWED_CONTENT_FIELDS)
    if unexpected_content:
        errors.append("unexpected content fields: " + ", ".join(unexpected_content))

    if content.get("type") != "text":
        errors.append("content.type must be 'text' in v1")

    text = content.get("text")
    if not isinstance(text, str) or not text.strip():
        errors.append("content.text must be a non-empty string")

    return errors


def _publishable_projection(intent: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": intent["provider"],
        "visibility": intent["visibility"],
        "content": {
            "type": intent["content"]["type"],
            "text": intent["content"]["text"],
        },
    }


def content_sha256(intent: dict[str, Any]) -> str:
    errors = validate_intent(intent)
    if errors:
        raise ValueError("; ".join(errors))
    canonical = json.dumps(
        _publishable_projection(intent),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _receipt(
    intent: dict[str, Any],
    *,
    state: str,
    provider_request_state: str,
    provider_post_id: str | None = None,
    provider_status_code: int | None = None,
    error_class: str | None = None,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "request_id": intent["request_id"],
        "provider": intent["provider"],
        "state": state,
        "content_sha256": content_sha256(intent),
        "provider_request_state": provider_request_state,
        "provider_post_id": provider_post_id,
    }
    if provider_status_code is not None:
        receipt["provider_status_code"] = provider_status_code
    if error_class is not None:
        receipt["error_class"] = error_class
    return receipt


def prepare_preview(intent: dict[str, Any]) -> dict[str, Any]:
    errors = validate_intent(intent)
    if errors:
        raise ValueError("; ".join(errors))
    return _receipt(
        intent,
        state="PREVIEW_READY",
        provider_request_state="NOT_EMITTED",
    )


def _receipt_from_provider_result(
    intent: dict[str, Any],
    provider_result: Any,
) -> dict[str, Any]:
    if not isinstance(provider_result, dict):
        return _receipt(
            intent,
            state="PROVIDER_RESPONSE_INCOMPLETE",
            provider_request_state="EMITTED",
            error_class="INVALID_PROVIDER_RESULT",
        )

    outcome = provider_result.get("outcome")
    state = _PROVIDER_OUTCOME_TO_STATE.get(outcome)
    if state is None:
        return _receipt(
            intent,
            state="PROVIDER_RESPONSE_INCOMPLETE",
            provider_request_state="EMITTED",
            error_class="INVALID_PROVIDER_RESULT",
        )

    post_id = provider_result.get("provider_post_id")
    status_code = provider_result.get("provider_status_code")
    error_class = provider_result.get("error_class")

    if state == "PUBLISHED":
        if not isinstance(post_id, str) or not post_id.strip():
            return _receipt(
                intent,
                state="PROVIDER_RESPONSE_INCOMPLETE",
                provider_request_state="EMITTED",
                provider_status_code=status_code if isinstance(status_code, int) else None,
                error_class="MISSING_PROVIDER_POST_ID",
            )
        error_class = None
    else:
        post_id = None
        if not isinstance(error_class, str) or not error_class.strip():
            error_class = "PROVIDER_RESULT_FAILURE"

    return _receipt(
        intent,
        state=state,
        provider_request_state="EMITTED",
        provider_post_id=post_id,
        provider_status_code=status_code if isinstance(status_code, int) else None,
        error_class=error_class,
    )


def execute_approved_publication(
    intent: dict[str, Any],
    *,
    approved_content_sha256: str | None,
    build_provider_request: Callable[[dict[str, Any]], dict[str, Any]],
    send_provider_request: Callable[[dict[str, Any]], Any],
    translate_provider_response: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    errors = validate_intent(intent)
    if errors:
        raise ValueError("; ".join(errors))

    current_hash = content_sha256(intent)
    if not approved_content_sha256:
        return _receipt(
            intent,
            state="BLOCKED_APPROVAL_REQUIRED",
            provider_request_state="NOT_EMITTED",
        )
    if approved_content_sha256 != current_hash:
        return _receipt(
            intent,
            state="BLOCKED_STALE_APPROVAL",
            provider_request_state="NOT_EMITTED",
        )

    try:
        request = build_provider_request(intent)
    except Exception:
        return _receipt(
            intent,
            state="PROVIDER_REQUEST_BUILD_FAILED",
            provider_request_state="NOT_EMITTED",
            error_class="PROVIDER_REQUEST_BUILD",
        )

    try:
        response = send_provider_request(request)
    except Exception:
        return _receipt(
            intent,
            state="PROVIDER_TRANSPORT_FAILED",
            provider_request_state="UNKNOWN",
            error_class="PROVIDER_TRANSPORT",
        )

    try:
        provider_result = translate_provider_response(response)
    except Exception:
        return _receipt(
            intent,
            state="PROVIDER_RESPONSE_INCOMPLETE",
            provider_request_state="EMITTED",
            error_class="PROVIDER_RESPONSE_TRANSLATION",
        )

    return _receipt_from_provider_result(intent, provider_result)
