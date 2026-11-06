"""Drive/Docs publish adapter.

Transport is injected (token/MCP/callback). This module plans typed outcomes
and never embeds private Drive file IDs in repository fixtures.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping


class DriveAdapterError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def classify_drive_error(message: str) -> str:
    text = (message or "").lower()
    if "appnotauthorizedtofile" in text or "app not authorized" in text:
        return "AWAITING_GRANT"
    if "access_token_scope_insufficient" in text or "insufficient authentication scopes" in text:
        return "ACCESS_SCOPE_INSUFFICIENT"
    if "403" in text or "permission" in text:
        return "PERMISSION_DENIED"
    return "DRIVE_ERROR"


def publish_bundle(
    packet: Mapping[str, Any],
    *,
    transport: Callable[[str, Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Publish markdown/images through an injected transport.

    Without transport, returns a dry structured plan result only.
    """
    bundle = packet.get("bundle") or {}
    plan = packet.get("plan") or {}
    if transport is None:
        return {
            "status": "PLANNED_NO_TRANSPORT",
            "workingDoc": plan.get("workingDoc"),
            "imageUploadCount": len(plan.get("imageUploads") or []),
            "perMessageCount": len(plan.get("perMessageDocs") or []),
            "reconcile": {
                "semantic": plan.get("reconcileDocSemantic"),
                "rule": plan.get("reconcileRule"),
                "status": "NOT_ATTEMPTED",
            },
        }

    results: dict[str, Any] = {"status": "PUBLISHED", "ops": [], "failures": []}
    try:
        working = transport(
            "upsert_doc",
            {
                "semantic": (plan.get("workingDoc") or {}).get("semanticTarget"),
                "title": (plan.get("workingDoc") or {}).get("title"),
                "markdown": bundle.get("docCleanMarkdown"),
            },
        )
        results["ops"].append({"op": "upsert_doc", "result": working})
    except Exception as exc:  # noqa: BLE001 - classify provider failures
        code = classify_drive_error(str(exc))
        results["failures"].append({"op": "upsert_doc", "code": code, "error": str(exc)[:300]})
        if code == "AWAITING_GRANT":
            results["status"] = "AWAITING_GRANT"
        else:
            results["status"] = "FAILED"
            return results

    for image in plan.get("imageUploads") or []:
        try:
            uploaded = transport(
                "upload_image",
                {
                    "file": image.get("file"),
                    "ordinal": image.get("ordinal"),
                    "semanticFolder": plan.get("mediaFolderSemantic"),
                },
            )
            results["ops"].append({"op": "upload_image", "result": uploaded})
        except Exception as exc:  # noqa: BLE001
            code = classify_drive_error(str(exc))
            results["failures"].append(
                {"op": "upload_image", "code": code, "file": image.get("file"), "error": str(exc)[:300]}
            )
            if code == "AWAITING_GRANT":
                results["status"] = "PARTIAL_AWAITING_GRANT"
            else:
                results["status"] = "PARTIAL_FAILURE"

    reconcile_semantic = plan.get("reconcileDocSemantic")
    if reconcile_semantic:
        try:
            reconcile = transport(
                "reconcile_doc",
                {
                    "semantic": reconcile_semantic,
                    "markdown": bundle.get("docCleanMarkdown"),
                },
            )
            results["ops"].append({"op": "reconcile_doc", "result": reconcile})
        except Exception as exc:  # noqa: BLE001
            code = classify_drive_error(str(exc))
            results["reconcile"] = {"status": code, "error": str(exc)[:300]}
            if code == "AWAITING_GRANT":
                results["status"] = "WORKING_DOC_SOURCE_OF_TRUTH"
            else:
                results["status"] = "PARTIAL_FAILURE"
    return results
