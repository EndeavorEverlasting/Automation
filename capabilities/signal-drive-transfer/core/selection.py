"""Validate UI-exported Signal selection JSON without judgment."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SelectionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


REQUIRED_ROOT = ("extractedAt", "source", "selectedCount", "messages")
REQUIRED_MESSAGE = ("ordinal", "body", "hasAttachmentDownload")


def load_selection(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise SelectionError("SELECTION_MISSING", f"selection file missing: {path.name}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SelectionError("SELECTION_INVALID_JSON", "selection JSON could not be parsed") from exc
    return validate_selection(payload)


def validate_selection(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SelectionError("SELECTION_SHAPE", "selection root must be an object")
    for key in REQUIRED_ROOT:
        if key not in payload:
            raise SelectionError("SELECTION_SHAPE", f"missing required field: {key}")
    count = payload["selectedCount"]
    messages = payload["messages"]
    if not isinstance(count, int) or count < 1:
        raise SelectionError("SELECTION_COUNT", "selectedCount must be a positive integer")
    if not isinstance(messages, list) or not messages:
        raise SelectionError("SELECTION_MESSAGES", "messages must be a non-empty array")
    if len(messages) != count:
        raise SelectionError(
            "SELECTION_COUNT_MISMATCH",
            f"selectedCount={count} but messages length={len(messages)}",
        )
    seen: set[int] = set()
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise SelectionError("SELECTION_MESSAGE_SHAPE", f"messages[{index}] must be an object")
        for key in REQUIRED_MESSAGE:
            if key not in message:
                raise SelectionError(
                    "SELECTION_MESSAGE_SHAPE",
                    f"messages[{index}] missing required field: {key}",
                )
        ordinal = message["ordinal"]
        if not isinstance(ordinal, int) or ordinal < 1:
            raise SelectionError("SELECTION_ORDINAL", f"messages[{index}].ordinal invalid")
        if ordinal in seen:
            raise SelectionError("SELECTION_ORDINAL_DUP", f"duplicate ordinal {ordinal}")
        seen.add(ordinal)
        if not isinstance(message["body"], str):
            raise SelectionError("SELECTION_BODY", f"messages[{index}].body must be a string")
        if not isinstance(message["hasAttachmentDownload"], bool):
            raise SelectionError(
                "SELECTION_ATTACHMENT_FLAG",
                f"messages[{index}].hasAttachmentDownload must be boolean",
            )
        links = message.get("links", [])
        if links is not None and not isinstance(links, list):
            raise SelectionError("SELECTION_LINKS", f"messages[{index}].links must be an array")
    expected = set(range(1, count + 1))
    if seen != expected:
        raise SelectionError(
            "SELECTION_ORDINAL_GAP",
            f"ordinals {sorted(seen)} do not cover 1..{count}",
        )
    return payload
