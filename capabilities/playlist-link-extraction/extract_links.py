#!/usr/bin/env python3
"""CLI for the playlist-link-extraction reusable core.

Consumes an adapter observation batch and emits canonical JSON plus an
optional CSV projection. This entrypoint does not perform provider
navigation or authenticated extraction.
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

from core.artifact import build_artifact, render_csv, validate_observation_batch  # noqa: E402


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build canonical playlist-link artifacts from an observation batch. "
            "Adapters produce the batch; this CLI owns core normalization only."
        )
    )
    parser.add_argument(
        "--batch",
        required=True,
        help="Path to a playlist-link-observation-batch/v1 JSON file",
    )
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path for the canonical playlist-link-artifact/v1 JSON output",
    )
    parser.add_argument(
        "--output-csv",
        help="Optional path for a CSV projection derived from the JSON artifact",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the observation batch and exit without writing artifacts",
    )
    args = parser.parse_args(argv)

    batch_path = Path(args.batch)
    if not batch_path.is_file():
        print(f"batch file not found: {batch_path}", file=sys.stderr)
        return 2

    batch = _load_json(batch_path)
    errors = validate_observation_batch(batch)
    if errors:
        for error in errors:
            print(f"validation error: {error}", file=sys.stderr)
        return 1

    if args.validate_only:
        print("OK")
        return 0

    assert isinstance(batch, dict)
    try:
        artifact = build_artifact(batch)
    except ValueError as exc:
        print(f"build error: {exc}", file=sys.stderr)
        return 1

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(artifact, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    if args.output_csv:
        output_csv = Path(args.output_csv)
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        output_csv.write_text(render_csv(artifact), encoding="utf-8")

    receipt = artifact["receipt"]
    print(
        "OK "
        f"targets={receipt['target_count']} "
        f"occurrences={receipt['occurrence_count']} "
        f"unique={receipt['unique_link_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
