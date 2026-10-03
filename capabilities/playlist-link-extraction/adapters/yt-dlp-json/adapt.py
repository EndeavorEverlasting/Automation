#!/usr/bin/env python3
"""CLI for the offline yt-dlp-json playlist adapter.

Reads a captured/synthetic yt-dlp playlist JSON payload and emits a
playlist-link-observation-batch/v1 file for the reusable core.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _ensure_local_import_path() -> None:
    root = Path(__file__).resolve().parent
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)


_ensure_local_import_path()

from convert import convert_playlist_payload, validate_provider_payload  # noqa: E402


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Convert offline yt-dlp-style playlist JSON into a "
            "playlist-link-observation-batch/v1 payload."
        )
    )
    parser.add_argument(
        "--payload",
        required=True,
        help="Path to a yt-dlp playlist JSON payload",
    )
    parser.add_argument(
        "--target-id",
        required=True,
        help="Stable target_id for the observation batch",
    )
    parser.add_argument(
        "--source-ref",
        help="Optional explicit source_ref; defaults to payload webpage_url/url",
    )
    parser.add_argument(
        "--label",
        help="Optional target label; defaults to payload title when present",
    )
    parser.add_argument(
        "--output-batch",
        required=True,
        help="Path for the emitted observation-batch JSON",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the provider payload and exit without writing output",
    )
    args = parser.parse_args(argv)

    payload_path = Path(args.payload)
    if not payload_path.is_file():
        print(f"payload file not found: {payload_path}", file=sys.stderr)
        return 2

    payload = _load_json(payload_path)
    errors = validate_provider_payload(payload)
    if errors:
        for error in errors:
            print(f"validation error: {error}", file=sys.stderr)
        return 1

    if args.validate_only:
        print("OK")
        return 0

    assert isinstance(payload, dict)
    try:
        batch = convert_playlist_payload(
            payload,
            target_id=args.target_id,
            source_ref=args.source_ref,
            label=args.label,
        )
    except ValueError as exc:
        print(f"convert error: {exc}", file=sys.stderr)
        return 1

    output = Path(args.output_batch)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(batch, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(
        "OK "
        f"targets={len(batch['targets'])} "
        f"observations={len(batch['observations'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
