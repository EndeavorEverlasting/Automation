"""UIA → clipboard image acquisition (no print-screen).

This adapter defines the executable seam for copying an already-rendered
Signal attachment via clipboard. It does not capture the screen.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Mapping

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.media_policy import MediaPolicyError, admit_media_plan, assert_media_source_allowed


def plan_clipboard_copy_for_message(
    *,
    ordinal: int,
    attachment_index: int = 0,
) -> dict[str, Any]:
    plan = {
        "source": "uia-clipboard-image",
        "actions": [
            {
                "kind": "uia-focus-attachment",
                "ordinal": ordinal,
                "attachmentIndex": attachment_index,
            },
            {"kind": "clipboard-copy"},
            {"kind": "clipboard-read-image"},
            {"kind": "docs-paste-image", "ordinal": ordinal},
        ],
    }
    return admit_media_plan(plan)


def execute_clipboard_copy(
    plan: Mapping[str, Any],
    *,
    uia_focus: Callable[[int, int], None],
    clipboard_copy: Callable[[], None],
    clipboard_read_image: Callable[[], bytes],
) -> dict[str, Any]:
    """Run an admitted clipboard plan with injected OS hooks.

    Injected hooks must not implement print-screen. Callers that pass a
    screenshot function should be rejected by media policy before reaching here.
    """
    admitted = admit_media_plan(plan)
    assert_media_source_allowed(admitted["source"])
    focus = next(action for action in admitted["actions"] if action["kind"] == "uia-focus-attachment")
    ordinal = int(focus["ordinal"])
    attachment_index = int(focus.get("attachmentIndex") or 0)
    uia_focus(ordinal, attachment_index)
    clipboard_copy()
    payload = clipboard_read_image()
    if not isinstance(payload, (bytes, bytearray)) or len(payload) < 8:
        raise MediaPolicyError("CLIPBOARD_EMPTY", "clipboard did not contain an image")
    # PNG magic or JPEG SOI are acceptable; reject empty/non-image.
    header = bytes(payload[:8])
    if not (header.startswith(b"\x89PNG\r\n\x1a\n") or header.startswith(b"\xff\xd8")):
        raise MediaPolicyError("CLIPBOARD_NOT_IMAGE", "clipboard payload is not PNG/JPEG")
    return {
        "contract": "automation.signal-drive-transfer.clipboard-media/v1",
        "status": "COPIED",
        "ordinal": ordinal,
        "attachmentIndex": attachment_index,
        "bytes": len(payload),
        "source": "uia-clipboard-image",
    }
