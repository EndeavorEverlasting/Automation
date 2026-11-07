"""Attach uploaded Drive media links into document markdown."""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence


class MediaAttachError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def index_uploads_by_title(uploads: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for item in uploads:
        if not isinstance(item, Mapping):
            raise MediaAttachError("UPLOAD_SHAPE", "upload entries must be objects")
        title = item.get("title") or item.get("file") or item.get("name")
        link = item.get("webViewLink") or item.get("link")
        if not isinstance(title, str) or not title.strip():
            raise MediaAttachError("UPLOAD_TITLE", "upload title required")
        if not isinstance(link, str) or not link.startswith("https://"):
            raise MediaAttachError("UPLOAD_LINK", f"upload link missing for {title}")
        indexed[title.strip()] = item
    return indexed


def attach_drive_links_to_markdown(
    markdown: str,
    uploads: Sequence[Mapping[str, Any]],
    *,
    media_folder_link: str | None = None,
) -> dict[str, Any]:
    """Replace backtick attachment filenames with Drive links when uploads exist.

    Leaves unmatched filenames untouched. Does not invent links.
    """
    if not isinstance(markdown, str) or not markdown.strip():
        raise MediaAttachError("MARKDOWN_EMPTY", "markdown required")
    indexed = index_uploads_by_title(uploads)
    attached = 0
    missing: list[str] = []

    def replacer(match: re.Match[str]) -> str:
        nonlocal attached
        name = match.group(1)
        item = indexed.get(name)
        if not item:
            if name not in missing:
                missing.append(name)
            return match.group(0)
        link = item.get("webViewLink") or item.get("link")
        attached += 1
        return f"[{name}]({link})"

    # Match `- `file.png`` or bare `file.png` attachment bullets.
    updated = re.sub(r"`([^`\n]+\.(?:png|jpe?g|webp|gif))`", replacer, markdown)
    if media_folder_link and "Media folder:" not in updated:
        header = f"Media folder: {media_folder_link}\n\n"
        updated = header + updated
    return {
        "contract": "automation.signal-drive-transfer.media-attach/v1",
        "status": "ATTACHED" if attached else "NO_MATCHES",
        "attachedCount": attached,
        "uploadCount": len(indexed),
        "missingFilenames": missing,
        "markdown": updated,
    }


def merge_upload_receipts(
    *receipts: Sequence[Mapping[str, Any]] | Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Flatten DRIVE-PNG-RECEIPT style lists or {images:{}} maps into one list."""
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for receipt in receipts:
        items: Sequence[Any]
        if isinstance(receipt, Mapping) and "images" in receipt:
            raw = receipt.get("images")
            if isinstance(raw, Mapping):
                items = list(raw.values())
            elif isinstance(raw, list):
                items = raw
            else:
                items = []
        elif isinstance(receipt, list):
            items = receipt
        elif isinstance(receipt, Mapping):
            items = [receipt]
        else:
            continue
        for item in items:
            if not isinstance(item, Mapping):
                continue
            title = str(item.get("title") or item.get("file") or item.get("name") or "")
            if not title or title in seen:
                continue
            seen.add(title)
            merged.append(dict(item))
    return merged
