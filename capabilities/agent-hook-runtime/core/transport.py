from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "agent-hook-transport-receipt/v1"


def _base_receipt(raw: bytes) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "byte_length": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "content_persisted": False,
        "payload_keys": [],
    }


def _detect_encoding(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return "utf-16"
    return "utf-8"


def parse_json_object(raw: bytes) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Parse one JSON object from hook stdin without persisting payload content.

    The receipt intentionally records only transport metadata and top-level keys.
    Prompt values, attachments, session identifiers, and other payload values are
    never copied into the transport receipt.
    """

    receipt = _base_receipt(raw)
    if not raw:
        receipt.update({"state": "EMPTY_INPUT", "encoding": None})
        return None, receipt

    encoding = _detect_encoding(raw)
    receipt["encoding"] = encoding
    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError as exc:
        receipt.update(
            {
                "state": "DECODE_ERROR",
                "error_type": type(exc).__name__,
                "error_offset": exc.start,
            }
        )
        return None, receipt

    if not text.strip():
        receipt["state"] = "EMPTY_INPUT"
        return None, receipt

    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        receipt.update(
            {
                "state": "INVALID_JSON",
                "error_type": type(exc).__name__,
                "error_offset": exc.pos,
            }
        )
        return None, receipt

    if not isinstance(value, dict):
        receipt.update(
            {
                "state": "NON_OBJECT_JSON",
                "json_type": type(value).__name__,
            }
        )
        return None, receipt

    receipt.update(
        {
            "state": "PARSED",
            "payload_keys": sorted(str(key) for key in value.keys()),
        }
    )
    return value, receipt
