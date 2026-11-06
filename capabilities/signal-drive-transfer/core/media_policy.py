"""Media acquisition policy: clipboard/export only; print-screen banned."""
from __future__ import annotations

from typing import Any, Mapping


class MediaPolicyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


ALLOWED_SOURCES = frozenset(
    {
        "signal-save-as-export",
        "uia-clipboard-image",
        "predecrypted-attachment-file",  # optional legacy adapter; not screenshot
    }
)

BANNED_SOURCES = frozenset(
    {
        "printscreen",
        "print-screen",
        "screenshot",
        "screen-capture",
        "snip",
        "snipping-tool",
        "bitblt",
        "gdi-capture",
        "dxgi-capture",
        "magnification-capture",
    }
)


def normalize_source(source: str) -> str:
    if not isinstance(source, str) or not source.strip():
        raise MediaPolicyError("MEDIA_SOURCE_MISSING", "media source required")
    return source.strip().lower().replace("_", "-")


def assert_media_source_allowed(source: str) -> str:
    normalized = normalize_source(source)
    if normalized in BANNED_SOURCES or any(banned in normalized for banned in BANNED_SOURCES):
        raise MediaPolicyError(
            "MEDIA_SOURCE_BANNED",
            f"banned media source {source!r}; use Save-As export or UIA clipboard copy only",
        )
    if normalized not in ALLOWED_SOURCES:
        raise MediaPolicyError(
            "MEDIA_SOURCE_UNKNOWN",
            f"unknown media source {source!r}; allowed={sorted(ALLOWED_SOURCES)}",
        )
    return normalized


def admit_media_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed if a transfer media plan requests screenshot capture."""
    if not isinstance(plan, Mapping):
        raise MediaPolicyError("MEDIA_PLAN_SHAPE", "media plan must be an object")
    source = assert_media_source_allowed(str(plan.get("source") or ""))
    actions = plan.get("actions") or []
    if not isinstance(actions, list):
        raise MediaPolicyError("MEDIA_PLAN_ACTIONS", "actions must be an array")
    admitted: list[dict[str, Any]] = []
    for index, action in enumerate(actions):
        if not isinstance(action, Mapping):
            raise MediaPolicyError("MEDIA_ACTION_SHAPE", f"actions[{index}] must be an object")
        kind = str(action.get("kind") or "").strip().lower().replace("_", "-")
        if kind in BANNED_SOURCES or any(banned in kind for banned in BANNED_SOURCES):
            raise MediaPolicyError(
                "MEDIA_ACTION_BANNED",
                f"actions[{index}] kind {kind!r} is banned (no print-screen/screenshot)",
            )
        if kind not in {
            "read-export-file",
            "uia-focus-attachment",
            "clipboard-copy",
            "clipboard-read-image",
            "docs-paste-image",
            "drive-upload-image",
        }:
            raise MediaPolicyError(
                "MEDIA_ACTION_UNKNOWN",
                f"actions[{index}] unsupported kind {kind!r}",
            )
        admitted.append(dict(action))
    return {
        "contract": "automation.signal-drive-transfer.media-policy/v1",
        "status": "ADMITTED",
        "source": source,
        "actions": admitted,
        "banned": sorted(BANNED_SOURCES),
        "allowed": sorted(ALLOWED_SOURCES),
    }
