"""Acceptance gates for Signal → document packages."""
from __future__ import annotations

from typing import Any, Mapping, Sequence


class AcceptanceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def evaluate_acceptance(
    *,
    selection_count: int | None = None,
    matched_messages: Sequence[Mapping[str, Any]] | None = None,
    document_bundle: Mapping[str, Any] | None = None,
    expected_count: int,
    require_attachments_for: Sequence[int] | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            raise AcceptanceError(name, detail)

    add(
        "EXPECTED_COUNT_POSITIVE",
        isinstance(expected_count, int) and expected_count > 0,
        f"expected_count={expected_count}",
    )
    if selection_count is not None:
        add(
            "SELECTION_COUNT",
            selection_count == expected_count,
            f"selection_count={selection_count} expected={expected_count}",
        )
    if matched_messages is not None:
        ordinals = [int(item["ordinal"]) for item in matched_messages]
        add(
            "MATCH_COUNT",
            len(matched_messages) == expected_count,
            f"matched={len(matched_messages)} expected={expected_count}",
        )
        add(
            "MATCH_ORDINAL_COVERAGE",
            ordinals == list(range(1, expected_count + 1)),
            f"ordinals={ordinals}",
        )
        required = set(require_attachments_for or [])
        for ordinal in required:
            message = next(item for item in matched_messages if int(item["ordinal"]) == ordinal)
            has = bool(
                message.get("hasAttachments")
                or message.get("attachments")
                or message.get("attachmentsSaved")
                or message.get("imageMeta")
            )
            add(
                f"ATTACHMENT_PRESENT_{ordinal}",
                has,
                f"ordinal {ordinal} attachments required",
            )
    if document_bundle is not None:
        add(
            "DOCUMENT_COUNT",
            int(document_bundle.get("selectedCount") or 0) == expected_count,
            f"document selectedCount={document_bundle.get('selectedCount')}",
        )
        doc = document_bundle.get("docCleanMarkdown") or ""
        add("DOCUMENT_NONEMPTY", isinstance(doc, str) and len(doc.strip()) > 0, "doc-clean empty")
        messages = document_bundle.get("messages") or []
        add(
            "DOCUMENT_PER_MESSAGE",
            isinstance(messages, list) and len(messages) == expected_count,
            f"per-message docs={len(messages) if isinstance(messages, list) else 'invalid'}",
        )
    return {
        "contract": "automation.signal-drive-transfer.acceptance/v1",
        "status": "PASSED",
        "expectedCount": expected_count,
        "checks": checks,
    }
