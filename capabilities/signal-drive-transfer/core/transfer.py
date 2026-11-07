"""Plan and receipt orchestration for Signal → Drive transfers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from .accept import evaluate_acceptance
from .document import build_document_bundle
from .export_ingest import ingest_export_dir, merge_selection_with_export_media
from .match import match_messages
from .media_policy import admit_media_plan
from .selection import validate_selection

CONTRACT = "automation.signal-drive-transfer/v1"


class TransferError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run_transfer_plan(
    profile: Mapping[str, Any],
    *,
    selection: Mapping[str, Any] | None = None,
    db_rows: list[Mapping[str, Any]] | None = None,
    export_dir: Path | None = None,
    drive_publish: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Execute deterministic transfer planning.

    Media intake is Save-As export and/or UIA clipboard only.
    Print-screen / screenshot capture is banned by media policy.
    """
    if not isinstance(profile, Mapping):
        raise TransferError("PROFILE_SHAPE", "transfer profile must be an object")
    expected = profile.get("expectedCount")
    if not isinstance(expected, int) or expected < 1:
        raise TransferError("PROFILE_EXPECTED_COUNT", "expectedCount must be a positive integer")
    title = profile.get("title") or "Signal import"
    if not isinstance(title, str) or not title.strip():
        raise TransferError("PROFILE_TITLE", "title must be a non-empty string")

    media_source = str(profile.get("mediaSource") or "signal-save-as-export")
    media_admission = admit_media_plan(
        {
            "source": media_source,
            "actions": list(profile.get("mediaActions") or [{"kind": "read-export-file"}]),
        }
    )

    source = "unknown"
    matched: dict[str, Any]
    conversation_title = None
    export_meta: dict[str, Any] | None = None

    if export_dir is not None:
        ingested = ingest_export_dir(
            export_dir,
            expected_media_groups=profile.get("expectedMediaGroups"),
        )
        export_meta = {
            "ingestMode": ingested.get("ingestMode"),
            "mediaGroupCount": ingested.get("mediaGroupCount") or ingested.get("selectedCount"),
            "attachmentCount": ingested.get("attachmentCount"),
            "exportDirName": ingested.get("exportDirName"),
        }
        if selection is not None:
            validated = validate_selection(selection)
            conversation_title = validated.get("conversationTitle")
            merged = merge_selection_with_export_media(
                list(validated["messages"]),
                list(ingested["messages"]),
            )
            if len(merged) != expected:
                raise TransferError(
                    "MERGE_COUNT",
                    f"merged message count {len(merged)} != expected {expected}",
                )
            matched = {
                "contract": "automation.signal-drive-transfer.match/v1",
                "status": "MATCHED",
                "selectedCount": len(merged),
                "messages": merged,
            }
            source = "selection+signal-save-as-export"
        else:
            matched = {
                "contract": "automation.signal-drive-transfer.match/v1",
                "status": "MATCHED",
                "selectedCount": ingested["selectedCount"],
                "messages": ingested["messages"],
            }
            source = f"export:{ingested.get('ingestMode')}"
            if matched["selectedCount"] != expected and profile.get("allowMediaOnlySubset"):
                # Media-only package for attachment-bearing subset.
                expected = matched["selectedCount"]
            elif matched["selectedCount"] != expected:
                raise TransferError(
                    "EXPORT_COUNT",
                    f"export messages={matched['selectedCount']} expected={expected}; "
                    "provide selection JSON to merge, or set allowMediaOnlySubset",
                )
    else:
        if selection is None or db_rows is None:
            raise TransferError(
                "INPUT_REQUIRED",
                "provide export_dir (preferred) or both selection + db_rows",
            )
        validated = validate_selection(selection)
        conversation_title = validated.get("conversationTitle")
        match_profile = profile.get("matchProfile") or {"matchSpecs": profile.get("matchSpecs")}
        matched = match_messages(db_rows, match_profile, expected_count=expected)
        source = "selection+db"

    acceptance = evaluate_acceptance(
        selection_count=int(matched["selectedCount"]),
        matched_messages=matched["messages"],
        expected_count=expected,
        require_attachments_for=list(profile.get("requireAttachmentsFor") or []),
    )
    bundle = build_document_bundle(
        matched["messages"],
        title=title.strip(),
        conversation_title=conversation_title,
    )
    acceptance = evaluate_acceptance(
        selection_count=int(matched["selectedCount"]),
        matched_messages=matched["messages"],
        document_bundle=bundle,
        expected_count=expected,
        require_attachments_for=list(profile.get("requireAttachmentsFor") or []),
    )

    image_uploads = []
    for message in matched["messages"]:
        for item in message.get("attachmentsSaved") or []:
            file_name = item.get("file") or item.get("path")
            absolute = item.get("path") or item.get("absolutePath")
            if absolute is None and export_dir is not None and isinstance(file_name, str):
                candidate = export_dir / Path(file_name).name
                if candidate.is_file():
                    absolute = str(candidate.resolve())
            image_uploads.append(
                {
                    "ordinal": int(message["ordinal"]),
                    "file": Path(str(file_name)).name if file_name else None,
                    "absolutePath": absolute,
                    "bytes": item.get("bytes"),
                    "pasteMode": "drive-upload-or-docs-clipboard-paste",
                }
            )

    publish_plan = {
        "workingDoc": {
            "mode": "update_or_create",
            "title": title.strip(),
            "semanticTarget": profile.get("workingDocSemantic") or "working-doc",
            "markdownSha256": _sha256_text(bundle["docCleanMarkdown"]),
            "bytes": len(bundle["docCleanMarkdown"].encode("utf-8")),
        },
        "indexDoc": {
            "mode": "update_or_create",
            "title": f"{title.strip()} — INDEX",
            "semanticTarget": profile.get("indexDocSemantic") or "index-doc",
            "markdownSha256": _sha256_text(bundle["indexMarkdown"]),
        },
        "perMessageDocs": [
            {
                "ordinal": item["ordinal"],
                "title": item["title"],
                "bytes": item["bytes"],
                "markdownSha256": _sha256_text(item["markdown"]),
            }
            for item in bundle["messages"]
        ],
        "imageUploads": image_uploads,
        "mediaFolderSemantic": profile.get("mediaFolderSemantic") or "media-folder",
        "reconcileDocSemantic": profile.get("reconcileDocSemantic"),
        "reconcileRule": (
            "overwrite_when_writable_else_awaiting_grant"
            if profile.get("reconcileDocSemantic")
            else "working_doc_is_source_of_truth"
        ),
        "mediaPolicy": media_admission,
    }

    drive_result: dict[str, Any] = {
        "status": "DRY_RUN",
        "attempted": False,
        "reason": "dry_run",
    }
    if not dry_run:
        if drive_publish is None:
            raise TransferError(
                "DRIVE_ADAPTER_REQUIRED",
                "drive_publish callback required when dry_run=false",
            )
        raw = drive_publish({"bundle": bundle, "plan": publish_plan, "profile": profile})
        drive_result = dict(raw)
        drive_result["attempted"] = True

    receipt = {
        "contract": CONTRACT,
        "status": "PLANNED" if dry_run else drive_result.get("status", "PUBLISHED"),
        "source": source,
        "expectedCount": expected,
        "selectedCount": matched["selectedCount"],
        "acceptance": acceptance,
        "export": export_meta,
        "document": {
            "title": bundle["title"],
            "selectedCount": bundle["selectedCount"],
            "docCleanSha256": _sha256_text(bundle["docCleanMarkdown"]),
            "indexSha256": _sha256_text(bundle["indexMarkdown"]),
            "perMessageCount": len(bundle["messages"]),
            "imageUploadCount": len(image_uploads),
        },
        "publishPlan": publish_plan,
        "drive": drive_result,
        "proofCeiling": (
            "OFFLINE_DETERMINISTIC_PACKAGE"
            if dry_run
            else "DRIVE_ADAPTER_RESULT_ONLY"
        ),
        "notes": [
            "Print-screen and screenshot capture are banned.",
            "Allowed media: Signal Save-As export files and/or UIA clipboard copy-paste.",
            "Reconcile of an externally owned Doc stays awaiting_grant on 403.",
        ],
    }
    return receipt


def write_receipt(path: Path, receipt: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
