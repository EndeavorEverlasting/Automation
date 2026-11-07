"""Drive/Docs publish adapter with drive.file fallback.

Transport is injected (token/MCP/callback). This module never embeds private
Drive file IDs in repository fixtures. When reconcile/original write returns
appNotAuthorizedToFile, fall back to a connector-writable sibling/working Doc.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from core.media_attach import attach_drive_links_to_markdown


class DriveAdapterError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


Transport = Callable[[str, Mapping[str, Any]], Mapping[str, Any]]


def classify_drive_error(message: str) -> str:
    text = (message or "").lower()
    if "appnotauthorizedtofile" in text or "app not authorized" in text:
        return "AWAITING_GRANT"
    if "access_token_scope_insufficient" in text or "insufficient authentication scopes" in text:
        return "ACCESS_SCOPE_INSUFFICIENT"
    if "403" in text or "permission" in text:
        return "PERMISSION_DENIED"
    return "DRIVE_ERROR"


def _safe_call(transport: Transport, op: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    try:
        result = transport(op, payload)
        return {"ok": True, "op": op, "result": dict(result), "code": None, "error": None}
    except Exception as exc:  # noqa: BLE001 - classify provider failures
        code = classify_drive_error(str(exc))
        return {
            "ok": False,
            "op": op,
            "result": None,
            "code": code,
            "error": str(exc)[:400],
        }


def publish_bundle(
    packet: Mapping[str, Any],
    *,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """Publish markdown/images through an injected transport.

    Without transport, returns a dry structured plan result only.
    """
    if transport is None:
        plan = packet.get("plan") or {}
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
            "fallback": {"enabled": True, "rule": "drive.file-sibling-on-awaiting-grant"},
        }
    return publish_with_drive_file_fallback(packet, transport=transport)


def publish_with_drive_file_fallback(
    packet: Mapping[str, Any],
    *,
    transport: Transport,
) -> dict[str, Any]:
    """Upload media, attach links, upsert working Doc, reconcile with sibling fallback.

    Proven FIOS pattern under drive.file:
    1) upload images into media folder
    2) rewrite markdown bullets to Drive links
    3) upsert working/sibling Doc (connector-writable)
    4) attempt original reconcile; on AWAITING_GRANT keep sibling as source of truth
    """
    bundle = packet.get("bundle") or {}
    plan = packet.get("plan") or {}
    profile = packet.get("profile") or {}
    markdown = str(bundle.get("docCleanMarkdown") or "")
    title = (plan.get("workingDoc") or {}).get("title") or profile.get("title") or "Signal import"

    results: dict[str, Any] = {
        "status": "PUBLISHED",
        "ops": [],
        "failures": [],
        "uploads": [],
        "fallback": {"triggered": False, "reason": None},
        "sourceOfTruth": "working-doc",
    }

    # 1) Media uploads first so Docs can embed links.
    for image in plan.get("imageUploads") or []:
        file_name = image.get("file")
        absolute = image.get("absolutePath") or image.get("path")
        call = _safe_call(
            transport,
            "upload_image",
            {
                "file": file_name,
                "path": absolute,
                "ordinal": image.get("ordinal"),
                "semanticFolder": plan.get("mediaFolderSemantic"),
            },
        )
        if call["ok"]:
            results["ops"].append(call)
            uploaded = dict(call["result"] or {})
            if "title" not in uploaded and file_name:
                uploaded["title"] = file_name
            results["uploads"].append(uploaded)
        else:
            results["failures"].append(call)
            if call["code"] == "AWAITING_GRANT":
                results["status"] = "PARTIAL_AWAITING_GRANT"
            else:
                results["status"] = "PARTIAL_FAILURE"

    # 2) Attach links when uploads returned view links.
    folder_link = None
    for uploaded in results["uploads"]:
        if uploaded.get("folderWebViewLink"):
            folder_link = uploaded.get("folderWebViewLink")
            break
    attach = attach_drive_links_to_markdown(
        markdown,
        results["uploads"],
        media_folder_link=folder_link if isinstance(folder_link, str) else None,
    )
    linked_markdown = attach["markdown"]
    results["mediaAttach"] = {
        "status": attach["status"],
        "attachedCount": attach["attachedCount"],
        "missingFilenames": attach["missingFilenames"],
    }

    # 3) Upsert working / sibling Doc (drive.file writable surface).
    working = _safe_call(
        transport,
        "upsert_doc",
        {
            "semantic": (plan.get("workingDoc") or {}).get("semanticTarget") or "working-doc",
            "title": title,
            "markdown": linked_markdown,
            "role": "working",
        },
    )
    results["ops"].append(working)
    if not working["ok"]:
        # Explicit sibling create fallback when working upsert itself is blocked.
        sibling = _safe_call(
            transport,
            "create_sibling_doc",
            {
                "semantic": profile.get("siblingDocSemantic") or "sibling-doc",
                "title": f"{title} — connector package",
                "markdown": linked_markdown,
            },
        )
        results["ops"].append(sibling)
        results["fallback"] = {
            "triggered": True,
            "reason": working.get("code") or "WORKING_UPSERT_FAILED",
        }
        if sibling["ok"]:
            results["status"] = "SIBLING_DOC_SOURCE_OF_TRUTH"
            results["sourceOfTruth"] = "sibling-doc"
            results["linkedMarkdownBytes"] = len(linked_markdown.encode("utf-8"))
        else:
            results["status"] = "FAILED"
            results["failures"].append(working)
            results["failures"].append(sibling)
            return results
    else:
        results["linkedMarkdownBytes"] = len(linked_markdown.encode("utf-8"))

    # Optional index doc.
    if plan.get("indexDoc"):
        index_md = bundle.get("indexMarkdown") or ""
        index_call = _safe_call(
            transport,
            "upsert_doc",
            {
                "semantic": (plan.get("indexDoc") or {}).get("semanticTarget") or "index-doc",
                "title": (plan.get("indexDoc") or {}).get("title"),
                "markdown": index_md,
                "role": "index",
            },
        )
        results["ops"].append(index_call)
        if not index_call["ok"]:
            results["failures"].append(index_call)

    # 4) Reconcile original; drive.file 403 → keep working/sibling SoT.
    reconcile_semantic = plan.get("reconcileDocSemantic")
    if reconcile_semantic:
        reconcile = _safe_call(
            transport,
            "reconcile_doc",
            {
                "semantic": reconcile_semantic,
                "markdown": linked_markdown,
            },
        )
        results["ops"].append(reconcile)
        results["reconcile"] = {
            "status": "OK" if reconcile["ok"] else reconcile.get("code"),
            "error": reconcile.get("error"),
        }
        if not reconcile["ok"]:
            code = reconcile.get("code")
            results["fallback"] = {
                "triggered": True,
                "reason": code,
                "rule": "drive.file-sibling-on-awaiting-grant",
            }
            if code == "AWAITING_GRANT":
                # Ensure a sibling package exists even if working upsert already succeeded.
                sibling = _safe_call(
                    transport,
                    "create_sibling_doc",
                    {
                        "semantic": profile.get("siblingDocSemantic") or "sibling-doc",
                        "title": f"{title} — connector package",
                        "markdown": linked_markdown,
                    },
                )
                results["ops"].append(sibling)
                if sibling["ok"]:
                    results["status"] = "WORKING_AND_SIBLING_SOURCE_OF_TRUTH"
                    results["sourceOfTruth"] = "working-doc+sibling-doc"
                else:
                    results["status"] = "WORKING_DOC_SOURCE_OF_TRUTH"
                    results["sourceOfTruth"] = "working-doc"
            else:
                results["status"] = "PARTIAL_FAILURE"
                results["failures"].append(reconcile)
    return results
