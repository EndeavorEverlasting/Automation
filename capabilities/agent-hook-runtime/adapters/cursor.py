from __future__ import annotations

import hashlib
from typing import Any

SUPPORTED_EVENTS = {"beforeSubmitPrompt", "stop", "sessionStart"}


def _error(field: str, code: str) -> dict[str, str]:
    return {"field": field, "code": code}


def validate_event(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate only Cursor's documented fields; allow unknown fields for forward compatibility."""

    errors: list[dict[str, str]] = []
    if event not in SUPPORTED_EVENTS:
        return {
            "schema_version": "cursor-hook-schema-validation/v1",
            "event": event,
            "state": "UNSUPPORTED_EVENT",
            "errors": [_error("event", "unsupported")],
        }

    if event == "beforeSubmitPrompt":
        if not isinstance(payload.get("prompt"), str):
            errors.append(_error("prompt", "required_string"))
        attachments = payload.get("attachments")
        if attachments is not None and not isinstance(attachments, list):
            errors.append(_error("attachments", "expected_array"))

    elif event == "stop":
        if payload.get("status") not in {"completed", "aborted", "error"}:
            errors.append(_error("status", "invalid_enum"))
        loop_count = payload.get("loop_count")
        if not isinstance(loop_count, int) or isinstance(loop_count, bool) or loop_count < 0:
            errors.append(_error("loop_count", "required_nonnegative_integer"))

    elif event == "sessionStart":
        session_id = payload.get("session_id")
        if not isinstance(session_id, str) or not session_id.strip():
            errors.append(_error("session_id", "required_nonempty_string"))
        if not isinstance(payload.get("is_background_agent"), bool):
            errors.append(_error("is_background_agent", "required_boolean"))
        composer_mode = payload.get("composer_mode")
        if composer_mode is not None and composer_mode not in {"agent", "ask", "edit"}:
            errors.append(_error("composer_mode", "invalid_enum"))

    return {
        "schema_version": "cursor-hook-schema-validation/v1",
        "event": event,
        "state": "VALID" if not errors else "INVALID_EVENT_SCHEMA",
        "errors": errors,
    }


def neutral_response(event: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if event == "beforeSubmitPrompt":
        return {"continue": True}
    if event == "stop":
        return {}
    if event == "sessionStart":
        payload = payload or {}
        session_id = payload.get("session_id")
        if isinstance(session_id, str) and session_id.strip():
            return {"env": {"AUTOMATION_CURSOR_SESSION_ID": session_id}}
        return {}
    raise ValueError(f"unsupported Cursor hook event: {event}")


def blocked_response(event: str, message: str) -> dict[str, Any]:
    if event == "beforeSubmitPrompt":
        return {"continue": False, "user_message": message}
    if event == "stop":
        return {"followup_message": message}
    if event == "sessionStart":
        # Cursor documents sessionStart as fire-and-forget; blocking is not enforced.
        return {}
    raise ValueError(f"unsupported Cursor hook event: {event}")


def session_identity_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return {"state": "UNAVAILABLE"}
    return {
        "state": "AVAILABLE",
        "session_id_sha256": hashlib.sha256(session_id.encode("utf-8")).hexdigest(),
    }
