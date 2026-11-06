"""Ingest Signal Desktop Save-As / folder exports without screenshot dependency."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .media_policy import assert_media_source_allowed


class ExportIngestError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TEXT_SUFFIXES = {".txt", ".md", ".html", ".htm"}
SIGNAL_EXPORT_RE = re.compile(
    r"^(?P<base>signal-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-\d+)(?:_(?P<seq>\d+))?\.(?P<ext>png|jpe?g|webp|gif)$",
    re.IGNORECASE,
)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _attachment_files(export_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    for folder_name in ("attachments", "media", "images", "Attachments"):
        folder = export_dir / folder_name
        if folder.is_dir():
            candidates.extend(
                path
                for path in sorted(folder.iterdir())
                if path.is_file() and not path.is_symlink() and path.suffix.lower() in IMAGE_SUFFIXES
            )
    if candidates:
        return candidates
    return [
        path
        for path in sorted(export_dir.iterdir())
        if path.is_file() and not path.is_symlink() and path.suffix.lower() in IMAGE_SUFFIXES
    ]


def _message_files(export_dir: Path) -> list[Path]:
    preferred = sorted(export_dir.glob("message-*.md")) + sorted(export_dir.glob("message-*.txt"))
    if preferred:
        return preferred
    nested: list[Path] = []
    for sub in ("messages", "Messages", "text"):
        folder = export_dir / sub
        if folder.is_dir():
            nested.extend(sorted(folder.glob("*.md")))
            nested.extend(sorted(folder.glob("*.txt")))
    if nested:
        return nested
    return [
        path
        for path in sorted(export_dir.iterdir())
        if path.is_file()
        and path.suffix.lower() in TEXT_SUFFIXES
        and path.name.lower() not in {"readme.md", "index.md", "00-index.md"}
    ]


def group_signal_save_as_images(export_dir: Path) -> list[dict[str, Any]]:
    """Group flat Signal Save-As PNGs by timestamp stem.

    Example names:
      signal-2026-11-05-16-06-42-485.png
      signal-2026-11-05-16-06-42-485_002.png
    """
    groups: dict[str, list[tuple[int, Path]]] = {}
    for path in _attachment_files(export_dir):
        match = SIGNAL_EXPORT_RE.match(path.name)
        if not match:
            continue
        base = match.group("base")
        seq = match.group("seq")
        order = 1 if seq is None else int(seq)
        groups.setdefault(base, []).append((order, path))
    if not groups:
        return []
    messages: list[dict[str, Any]] = []
    for index, base in enumerate(sorted(groups), start=1):
        files = [path for _, path in sorted(groups[base], key=lambda item: item[0])]
        image_meta = []
        saved = []
        for att_index, path in enumerate(files):
            meta = {
                "file": path.name,
                "contentType": f"image/{path.suffix.lstrip('.').lower()}",
                "bytes": path.stat().st_size,
                "order": att_index,
                "absolutePath": str(path.resolve()),
            }
            image_meta.append(meta)
            saved.append(
                {
                    "file": path.name,
                    "path": str(path.resolve()),
                    "bytes": path.stat().st_size,
                    "order": att_index,
                }
            )
        sent_at_iso = None
        stamp = re.match(
            r"signal-(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d+)$", base
        )
        if stamp:
            y, mo, d, h, mi, s, ms = stamp.groups()
            sent_at_iso = f"{y}-{mo}-{d}T{h}:{mi}:{s}.{ms.zfill(3)}Z"
        messages.append(
            {
                "ordinal": index,
                "id": f"export-{base}",
                "exportGroup": base,
                "sent_at": None,
                "sent_at_iso": sent_at_iso,
                "body": "",
                "hasAttachments": True,
                "attachments": [{"fileName": item["file"], "path": item["path"]} for item in saved],
                "imageMeta": image_meta,
                "attachmentsSaved": saved,
                "matchMode": "signal-save-as-export",
            }
        )
    assert_media_source_allowed("signal-save-as-export")
    return messages


def _split_single_export(text: str) -> list[dict[str, Any]]:
    blocks = re.split(r"\n(?=\d{4}-\d{2}-\d{2}[ T]|\[\d{1,2}/\d{1,2}/\d{2,4})", text)
    messages: list[dict[str, Any]] = []
    for raw in blocks:
        chunk = raw.strip()
        if not chunk:
            continue
        messages.append({"body": chunk, "hasAttachments": False, "attachments": []})
    if not messages and text.strip():
        messages.append({"body": text.strip(), "hasAttachments": False, "attachments": []})
    return messages


def ingest_export_dir(
    export_dir: Path,
    *,
    expected_count: int | None = None,
    expected_media_groups: int | None = None,
) -> dict[str, Any]:
    """Normalize a Save-As / folder export into matched-message shape.

    Screenshot capture is never used. Flat Signal Save-As image folders are
    first-class (group by timestamp stem).
    """
    if export_dir.is_symlink() or not export_dir.is_dir():
        raise ExportIngestError("EXPORT_DIR_MISSING", "export directory missing or invalid")

    manifest_candidates = [
        export_dir / "export.json",
        export_dir / "selected-export.json",
        export_dir / "doc-payload.json",
        export_dir / "messages.json",
    ]
    for manifest_path in manifest_candidates:
        if manifest_path.is_file() and not manifest_path.is_symlink():
            payload = json.loads(_read_text(manifest_path))
            messages = payload.get("messages")
            if not isinstance(messages, list) or not messages:
                raise ExportIngestError("EXPORT_MANIFEST_EMPTY", f"{manifest_path.name} has no messages")
            normalized = []
            for index, message in enumerate(messages, start=1):
                if not isinstance(message, dict):
                    raise ExportIngestError("EXPORT_MANIFEST_SHAPE", f"messages[{index-1}] invalid")
                ordinal = int(message.get("ordinal") or index)
                normalized.append(
                    {
                        "ordinal": ordinal,
                        "id": message.get("id") or f"export-{ordinal}",
                        "sent_at": message.get("sent_at"),
                        "sent_at_iso": message.get("sent_at_iso"),
                        "body": message.get("body") or "",
                        "hasAttachments": bool(
                            message.get("hasAttachments")
                            or message.get("attachments")
                            or message.get("imageMeta")
                        ),
                        "attachments": list(message.get("attachments") or []),
                        "imageMeta": list(message.get("imageMeta") or []),
                        "attachmentsSaved": list(message.get("attachmentsSaved") or []),
                        "matchMode": "export-manifest",
                    }
                )
            if expected_count is not None and len(normalized) != expected_count:
                raise ExportIngestError(
                    "EXPORT_COUNT",
                    f"export count {len(normalized)} != expected {expected_count}",
                )
            return {
                "contract": "automation.signal-drive-transfer.export/v1",
                "status": "INGESTED",
                "source": "signal-save-as-export",
                "ingestMode": "manifest",
                "exportDirName": export_dir.name,
                "selectedCount": len(normalized),
                "messages": sorted(normalized, key=lambda item: int(item["ordinal"])),
                "attachmentFiles": [path.name for path in _attachment_files(export_dir)],
            }

    signal_groups = group_signal_save_as_images(export_dir)
    if signal_groups:
        if expected_media_groups is not None and len(signal_groups) != expected_media_groups:
            raise ExportIngestError(
                "EXPORT_MEDIA_GROUP_COUNT",
                f"media groups {len(signal_groups)} != expected {expected_media_groups}",
            )
        if expected_count is not None and len(signal_groups) != expected_count:
            # Attachment-only Save-As often covers a subset of selected messages.
            # Callers that need exact nine must merge with selection bodies.
            pass
        return {
            "contract": "automation.signal-drive-transfer.export/v1",
            "status": "INGESTED",
            "source": "signal-save-as-export",
            "ingestMode": "signal-flat-images",
            "exportDirName": export_dir.name,
            "selectedCount": len(signal_groups),
            "mediaGroupCount": len(signal_groups),
            "attachmentCount": sum(len(item["attachmentsSaved"]) for item in signal_groups),
            "messages": signal_groups,
            "attachmentFiles": [path.name for path in _attachment_files(export_dir)],
            "proofCeiling": "EXPORT_MEDIA_GROUPS_ONLY",
            "notes": [
                "Flat Save-As image export grouped by Signal timestamp stem.",
                "Text bodies are absent unless merged from selection/DB package.",
                "Print-screen/screenshot capture is banned.",
            ],
        }

    files = _message_files(export_dir)
    attachments = _attachment_files(export_dir)
    messages: list[dict[str, Any]] = []

    if len(files) == 1 and files[0].suffix.lower() in {".txt", ".html", ".htm"} and not list(
        export_dir.glob("message-*")
    ):
        for index, block in enumerate(_split_single_export(_read_text(files[0])), start=1):
            messages.append(
                {
                    "ordinal": index,
                    "id": f"export-{index}",
                    "sent_at": None,
                    "sent_at_iso": None,
                    "body": block["body"],
                    "hasAttachments": False,
                    "attachments": [],
                    "imageMeta": [],
                    "attachmentsSaved": [],
                    "matchMode": "export-text-split",
                }
            )
    else:
        for index, path in enumerate(files, start=1):
            ordinal_match = re.search(r"(\d+)", path.stem)
            ordinal = int(ordinal_match.group(1)) if ordinal_match else index
            body = re.sub(r"^# .*\n+", "", _read_text(path)).strip()
            related = [
                att
                for att in attachments
                if f"msg-{ordinal:02d}" in att.name
                or f"message-{ordinal:02d}" in att.name
                or f"_{ordinal}." in att.name
            ]
            messages.append(
                {
                    "ordinal": ordinal,
                    "id": f"export-{ordinal}",
                    "sent_at": None,
                    "sent_at_iso": None,
                    "body": body,
                    "hasAttachments": bool(related),
                    "attachments": [{"path": str(att.name), "fileName": att.name} for att in related],
                    "imageMeta": [
                        {
                            "file": att.name,
                            "contentType": f"image/{att.suffix.lstrip('.').lower()}",
                            "bytes": att.stat().st_size,
                        }
                        for att in related
                    ],
                    "attachmentsSaved": [
                        {"path": str(att), "file": att.name, "bytes": att.stat().st_size}
                        for att in related
                    ],
                    "matchMode": "export-files",
                }
            )

    if not messages:
        raise ExportIngestError("EXPORT_EMPTY", "no message or Signal image files found in export directory")
    if expected_count is not None and len(messages) != expected_count:
        raise ExportIngestError(
            "EXPORT_COUNT",
            f"export count {len(messages)} != expected {expected_count}",
        )
    return {
        "contract": "automation.signal-drive-transfer.export/v1",
        "status": "INGESTED",
        "source": "signal-save-as-export",
        "ingestMode": "files",
        "exportDirName": export_dir.name,
        "selectedCount": len(messages),
        "messages": sorted(messages, key=lambda item: int(item["ordinal"])),
        "attachmentFiles": [path.name for path in attachments],
    }


def merge_selection_with_export_media(
    selection_messages: list[dict[str, Any]],
    export_media_messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach export media groups onto selection rows that need attachments.

    Mapping is deterministic by ordered attachment-bearing selection messages
    ↔ ordered export media groups. No relevance judgment.
    """
    need_media = [
        message
        for message in sorted(selection_messages, key=lambda item: int(item["ordinal"]))
        if bool(message.get("hasAttachmentDownload") or message.get("hasAttachments"))
    ]
    media = sorted(export_media_messages, key=lambda item: int(item["ordinal"]))
    if len(need_media) != len(media):
        raise ExportIngestError(
            "EXPORT_MEDIA_ALIGN",
            f"attachment-bearing selection={len(need_media)} media groups={len(media)}",
        )
    by_ordinal = {
        int(message["ordinal"]): dict(message) for message in selection_messages
    }
    for selection_row, media_row in zip(need_media, media):
        ordinal = int(selection_row["ordinal"])
        merged = by_ordinal[ordinal]
        merged.update(
            {
                "id": media_row.get("id") or merged.get("id") or f"merged-{ordinal}",
                "hasAttachments": True,
                "attachments": media_row.get("attachments") or [],
                "imageMeta": media_row.get("imageMeta") or [],
                "attachmentsSaved": media_row.get("attachmentsSaved") or [],
                "exportGroup": media_row.get("exportGroup"),
                "sent_at_iso": media_row.get("sent_at_iso") or merged.get("sent_at_iso"),
                "matchMode": "selection+signal-save-as-export",
            }
        )
        if not (merged.get("body") or "").strip():
            merged["body"] = media_row.get("body") or ""
        by_ordinal[ordinal] = merged
    # Ensure non-media selection rows still present.
    for message in selection_messages:
        ordinal = int(message["ordinal"])
        if ordinal not in by_ordinal:
            by_ordinal[ordinal] = dict(message)
        else:
            row = by_ordinal[ordinal]
            if not row.get("body"):
                row["body"] = message.get("body") or ""
            if "hasAttachmentDownload" in message and "hasAttachments" not in row:
                row["hasAttachments"] = bool(message.get("hasAttachmentDownload"))
    return [by_ordinal[key] for key in sorted(by_ordinal)]
