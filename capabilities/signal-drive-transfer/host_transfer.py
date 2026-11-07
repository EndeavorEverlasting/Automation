#!/usr/bin/env python3
"""Host CLI for deterministic Signal → Drive transfer.

Media rules:
  ALLOWED — Signal Save-As export files; UIA select → clipboard → Docs/Drive paste
  BANNED  — print-screen and any screenshot-capture avenue
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.drive import (  # noqa: E402
    publish_bundle,
    publish_with_drive_file_fallback,
)
from core.export_discovery import discover_latest_export_dir  # noqa: E402
from core.export_ingest import ingest_export_dir  # noqa: E402
from core.media_attach import attach_drive_links_to_markdown, merge_upload_receipts  # noqa: E402
from core.media_policy import admit_media_plan, assert_media_source_allowed  # noqa: E402
from core.selection import load_selection  # noqa: E402
from core.transfer import CONTRACT, run_transfer_plan, write_receipt  # noqa: E402

# Statuses that count as a successful publish / fallback SoT for CLI exit 0.
_OK_STATUSES = {
    "PLANNED",
    "PUBLISHED",
    "PLANNED_NO_TRANSPORT",
    "WORKING_DOC_SOURCE_OF_TRUTH",
    "SIBLING_DOC_SOURCE_OF_TRUTH",
    "WORKING_AND_SIBLING_SOURCE_OF_TRUTH",
    "FOUND",
    "ATTACHED",
    "NO_MATCHES",
}


def cmd_doctor(_: argparse.Namespace) -> int:
    payload = {
        "contract": "automation.signal-drive-transfer.host/v1",
        "status": "READY",
        "python": ".".join(map(str, sys.version_info[:3])),
        "platform": sys.platform,
        "mediaAllowed": ["signal-save-as-export", "uia-clipboard-image"],
        "mediaBanned": ["printscreen", "screenshot", "snip", "bitblt"],
        "commands": [
            "doctor",
            "discover-export",
            "ingest-export",
            "admit-media",
            "attach-media",
            "plan",
            "publish",
        ],
        "entrypoint": "capabilities/signal-drive-transfer/host_transfer.py",
        "driveFileFallback": "create_sibling_doc on AWAITING_GRANT / appNotAuthorizedToFile",
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_discover_export(args: argparse.Namespace) -> int:
    result = discover_latest_export_dir(
        Path(args.export_root),
        prefer_name=args.prefer_name,
    )
    print(json.dumps(result, indent=2))
    return 0


def cmd_ingest_export(args: argparse.Namespace) -> int:
    export_dir = Path(args.export_dir) if args.export_dir else None
    if export_dir is None:
        discovered = discover_latest_export_dir(
            Path(args.export_root),
            prefer_name=args.prefer_name,
        )
        export_dir = Path(discovered["exportDir"])
        # Surface discovery metadata alongside ingest when auto-resolved.
        ingested = ingest_export_dir(
            export_dir,
            expected_count=args.expected_count,
            expected_media_groups=args.expected_media_groups,
        )
        ingested["discovery"] = discovered
        print(json.dumps(ingested, indent=2))
        return 0
    result = ingest_export_dir(
        export_dir,
        expected_count=args.expected_count,
        expected_media_groups=args.expected_media_groups,
    )
    print(json.dumps(result, indent=2))
    return 0


def cmd_admit_media(args: argparse.Namespace) -> int:
    source = assert_media_source_allowed(args.source)
    admitted = admit_media_plan(
        {
            "source": source,
            "actions": [{"kind": kind} for kind in args.action],
        }
    )
    print(json.dumps(admitted, indent=2))
    return 0


def cmd_attach_media(args: argparse.Namespace) -> int:
    markdown = Path(args.markdown).read_text(encoding="utf-8")
    uploads_raw = json.loads(Path(args.uploads).read_text(encoding="utf-8"))
    uploads = merge_upload_receipts(uploads_raw)
    result = attach_drive_links_to_markdown(
        markdown,
        uploads,
        media_folder_link=args.folder_link,
    )
    if args.out:
        Path(args.out).write_text(result["markdown"] + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "markdown"} | {
        "markdownBytes": len(result["markdown"].encode("utf-8")),
        "out": args.out,
    }, indent=2))
    return 0


def _resolve_export_dir(args: argparse.Namespace) -> Path | None:
    if getattr(args, "export_dir", None):
        return Path(args.export_dir)
    if getattr(args, "export_root", None):
        discovered = discover_latest_export_dir(
            Path(args.export_root),
            prefer_name=getattr(args, "prefer_name", None),
        )
        return Path(discovered["exportDir"])
    return None


def cmd_plan(args: argparse.Namespace) -> int:
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    selection = load_selection(Path(args.selection)) if args.selection else None
    export_dir = _resolve_export_dir(args)
    receipt = run_transfer_plan(
        profile,
        selection=selection,
        export_dir=export_dir,
        dry_run=not args.publish,
        drive_publish=(None if not args.publish else (lambda packet: publish_bundle(packet))),
    )
    if args.receipt:
        write_receipt(Path(args.receipt), receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt.get("status") in _OK_STATUSES else 2


def _load_transport_script(path: Path):
    """Load an optional private transport module exposing `transport(op, payload)`.

    Keeps Drive tokens / MCP wiring out of the public capability tree.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("signal_drive_private_transport", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load transport module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    transport = getattr(module, "transport", None)
    if not callable(transport):
        raise RuntimeError("transport module must expose callable transport(op, payload)")
    return transport


def cmd_publish(args: argparse.Namespace) -> int:
    """Plan + publish with drive.file sibling fallback.

    Without --transport, returns the deterministic dry plan (no network).
    With --transport PATH.py exposing transport(op, payload), runs the live
    upload → attach → upsert → reconcile/sibling fallback path.
    """
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    selection = load_selection(Path(args.selection)) if args.selection else None
    export_dir = _resolve_export_dir(args)

    transport = None
    if args.transport:
        transport = _load_transport_script(Path(args.transport))

    def drive_publish(packet: Mapping[str, Any]) -> Mapping[str, Any]:
        if transport is None:
            return publish_bundle(packet)
        return publish_with_drive_file_fallback(packet, transport=transport)

    receipt = run_transfer_plan(
        profile,
        selection=selection,
        export_dir=export_dir,
        dry_run=False,
        drive_publish=drive_publish,
    )
    if args.receipt:
        write_receipt(Path(args.receipt), receipt)
    print(json.dumps(receipt, indent=2))
    status = receipt.get("status")
    return 0 if status in _OK_STATUSES else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Host readiness / media policy summary")
    doctor.set_defaults(func=cmd_doctor)

    discover = sub.add_parser(
        "discover-export",
        help="Pick latest export-* (or Signal-image) directory under a root",
    )
    discover.add_argument("--export-root", required=True)
    discover.add_argument("--prefer-name", help="Exact export directory name to require")
    discover.set_defaults(func=cmd_discover_export)

    ingest = sub.add_parser("ingest-export", help="Ingest Signal Save-As export directory")
    ingest.add_argument("--export-dir", help="Exact export directory")
    ingest.add_argument(
        "--export-root",
        help="Discover latest export under this root when --export-dir omitted",
    )
    ingest.add_argument("--prefer-name", help="Preferred export directory name under --export-root")
    ingest.add_argument("--expected-count", type=int)
    ingest.add_argument("--expected-media-groups", type=int)
    ingest.set_defaults(func=cmd_ingest_export)

    media = sub.add_parser("admit-media", help="Admit or reject a media acquisition plan")
    media.add_argument("--source", required=True)
    media.add_argument(
        "--action",
        action="append",
        default=["read-export-file"],
        help="Repeatable action kind (default: read-export-file)",
    )
    media.set_defaults(func=cmd_admit_media)

    attach = sub.add_parser(
        "attach-media",
        help="Rewrite markdown attachment backticks to Drive webViewLink targets",
    )
    attach.add_argument("--markdown", required=True, help="Input markdown path")
    attach.add_argument(
        "--uploads",
        required=True,
        help="JSON upload receipt (list or {images:{}} DRIVE-PNG-RECEIPT shape)",
    )
    attach.add_argument("--folder-link", help="Optional media folder webViewLink header")
    attach.add_argument("--out", help="Write linked markdown to this path")
    attach.set_defaults(func=cmd_attach_media)

    plan = sub.add_parser("plan", help="Build transfer receipt from export and/or selection")
    plan.add_argument("--profile", required=True, help="Transfer profile JSON")
    plan.add_argument("--export-dir", help="Signal Save-As export directory")
    plan.add_argument("--export-root", help="Discover latest export under this root")
    plan.add_argument("--prefer-name", help="Preferred export directory name under --export-root")
    plan.add_argument("--selection", help="selected-messages.json from UIA")
    plan.add_argument("--receipt", help="Optional receipt output path (outside Git recommended)")
    plan.add_argument(
        "--publish",
        action="store_true",
        help="Attempt Drive publish via no-transport plan (prefer 'publish' subcommand)",
    )
    plan.set_defaults(func=cmd_plan)

    publish = sub.add_parser(
        "publish",
        help="Plan + Drive publish with drive.file sibling fallback",
    )
    publish.add_argument("--profile", required=True, help="Transfer profile JSON")
    publish.add_argument("--export-dir", help="Signal Save-As export directory")
    publish.add_argument("--export-root", help="Discover latest export under this root")
    publish.add_argument("--prefer-name", help="Preferred export directory name under --export-root")
    publish.add_argument("--selection", help="selected-messages.json from UIA")
    publish.add_argument(
        "--transport",
        help="Private Python module exposing transport(op, payload) for live Drive ops",
    )
    publish.add_argument("--receipt", help="Optional receipt output path (outside Git recommended)")
    publish.set_defaults(func=cmd_publish)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "ingest-export" and not args.export_dir and not args.export_root:
        parser.error("ingest-export requires --export-dir or --export-root")
    if args.command in {"plan", "publish"} and not args.export_dir and not args.export_root and not args.selection:
        # selection alone still needs db_rows which CLI does not supply; require export.
        parser.error(f"{args.command} requires --export-dir or --export-root")
    try:
        return int(args.func(args))
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        code = getattr(exc, "code", "HOST_ERROR")
        print(json.dumps({"contract": CONTRACT, "status": "FAILED", "code": code, "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
