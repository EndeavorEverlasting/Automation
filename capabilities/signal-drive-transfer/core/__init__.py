"""Deterministic Signal selection/export → document → Drive transfer core."""

from .accept import AcceptanceError, evaluate_acceptance
from .document import build_document_bundle
from .export_discovery import ExportDiscoveryError, discover_latest_export_dir, list_export_dirs
from .export_ingest import ExportIngestError, ingest_export_dir, merge_selection_with_export_media
from .match import MatchError, match_messages
from .media_attach import MediaAttachError, attach_drive_links_to_markdown, merge_upload_receipts
from .media_policy import MediaPolicyError, admit_media_plan, assert_media_source_allowed
from .selection import SelectionError, load_selection, validate_selection
from .transfer import CONTRACT, TransferError, run_transfer_plan

__all__ = [
    "CONTRACT",
    "AcceptanceError",
    "ExportDiscoveryError",
    "ExportIngestError",
    "MatchError",
    "MediaAttachError",
    "MediaPolicyError",
    "SelectionError",
    "TransferError",
    "admit_media_plan",
    "assert_media_source_allowed",
    "attach_drive_links_to_markdown",
    "build_document_bundle",
    "discover_latest_export_dir",
    "evaluate_acceptance",
    "ingest_export_dir",
    "list_export_dirs",
    "load_selection",
    "match_messages",
    "merge_selection_with_export_media",
    "merge_upload_receipts",
    "run_transfer_plan",
    "validate_selection",
]
