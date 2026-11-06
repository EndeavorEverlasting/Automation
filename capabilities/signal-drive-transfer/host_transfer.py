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

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.drive import publish_bundle  # noqa: E402
from core.export_ingest import ingest_export_dir  # noqa: E402
from core.media_policy import admit_media_plan, assert_media_source_allowed  # noqa: E402
from core.selection import load_selection  # noqa: E402
from core.transfer import CONTRACT, run_transfer_plan, write_receipt  # noqa: E402


def cmd_doctor(_: argparse.Namespace) -> int:
    payload = {
        "contract": "automation.signal-drive-transfer.host/v1",
        "status": "READY",
        "python": ".".join(map(str, sys.version_info[:3])),
        "platform": sys.platform,
        "mediaAllowed": ["signal-save-as-export", "uia-clipboard-image"],
        "mediaBanned": ["printscreen", "screenshot", "snip", "bitblt"],
        "entrypoint": "capabilities/signal-drive-transfer/host_transfer.py",
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_ingest_export(args: argparse.Namespace) -> int:
    result = ingest_export_dir(
        Path(args.export_dir),
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


def cmd_plan(args: argparse.Namespace) -> int:
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    selection = load_selection(Path(args.selection)) if args.selection else None
    receipt = run_transfer_plan(
        profile,
        selection=selection,
        export_dir=Path(args.export_dir) if args.export_dir else None,
        dry_run=not args.publish,
        drive_publish=(None if not args.publish else (lambda packet: publish_bundle(packet))),
    )
    if args.receipt:
        write_receipt(Path(args.receipt), receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt.get("status") in {"PLANNED", "PUBLISHED", "WORKING_DOC_SOURCE_OF_TRUTH", "PLANNED_NO_TRANSPORT"} else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Host readiness / media policy summary")
    doctor.set_defaults(func=cmd_doctor)

    ingest = sub.add_parser("ingest-export", help="Ingest Signal Save-As export directory")
    ingest.add_argument("--export-dir", required=True)
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

    plan = sub.add_parser("plan", help="Build transfer receipt from export and/or selection")
    plan.add_argument("--profile", required=True, help="Transfer profile JSON")
    plan.add_argument("--export-dir", help="Signal Save-As export directory")
    plan.add_argument("--selection", help="selected-messages.json from UIA")
    plan.add_argument("--receipt", help="Optional receipt output path (outside Git recommended)")
    plan.add_argument(
        "--publish",
        action="store_true",
        help="Attempt Drive publish via injected/no-op transport (default: dry-run plan)",
    )
    plan.set_defaults(func=cmd_plan)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        code = getattr(exc, "code", "HOST_ERROR")
        print(json.dumps({"contract": CONTRACT, "status": "FAILED", "code": code, "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
