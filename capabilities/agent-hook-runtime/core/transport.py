from __future__ import annotations

import hashlib
import json
from typing import Any, BinaryIO

SCHEMA_VERSION = "agent-hook-transport-receipt/v1"
MAX_HOOK_INPUT_BYTES = 8 * 1024 * 1024


def _base_receipt(raw: bytes) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "byte_length": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "content_persisted": False,
        "payload_keys": [],
        "input_complete": True,
    }


def _detect_encoding(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return "utf-16"
    return "utf-8"


def parse_json_object(raw: bytes) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Parse one JSON object without persisting payload content."""

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


def read_json_object(
    stream: BinaryIO,
    *,
    max_bytes: int = MAX_HOOK_INPUT_BYTES,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Read a bounded hook payload and parse it as a JSON object.

    Only max_bytes + 1 bytes are consumed. If the limit is exceeded, policy
    execution must not inspect a partial object. The receipt hash then covers
    only the observed prefix and input_complete is false.
    """

    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        receipt = _base_receipt(raw)
        receipt.update(
            {
                "state": "INPUT_TOO_LARGE",
                "encoding": _detect_encoding(raw),
                "input_complete": False,
                "limit_bytes": max_bytes,
            }
        )
        return None, receipt
    return parse_json_object(raw)
