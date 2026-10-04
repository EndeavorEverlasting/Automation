#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "document_formatting_compiler",
    ROOT / "core" / "compiler.py",
)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _stage_text(target: Path, text: str) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
        text=True,
    )
    path = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path


def _reserve_backup(target: Path) -> Path | None:
    if not target.exists():
        return None
    fd, name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".bak",
        dir=target.parent,
    )
    os.close(fd)
    backup = Path(name)
    backup.unlink()
    os.replace(target, backup)
    return backup


def _publish_pair(
    output: Path,
    ir: dict[str, Any],
    receipt_path: Path,
    receipt: dict[str, Any],
) -> None:
    if output.resolve() == receipt_path.resolve():
        raise ValueError("output and receipt must be different paths")

    ir_text = json.dumps(ir, indent=2, sort_keys=True) + "\n"
    receipt_text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    ir_stage: Path | None = None
    receipt_stage: Path | None = None
    backups: dict[Path, Path] = {}
    published: list[Path] = []

    try:
        # Stage both complete payloads before exposing either final artifact.
        ir_stage = _stage_text(output, ir_text)
        receipt_stage = _stage_text(receipt_path, receipt_text)

        for target in (receipt_path, output):
            backup = _reserve_backup(target)
            if backup is not None:
                backups[target] = backup

        # Receipt is the commit marker. Never publish the IR first.
        os.replace(receipt_stage, receipt_path)
        receipt_stage = None
        published.append(receipt_path)

        os.replace(ir_stage, output)
        ir_stage = None
        published.append(output)
    except Exception:
        for target in reversed(published):
            target.unlink(missing_ok=True)
        for target, backup in backups.items():
            if backup.exists():
                os.replace(backup, target)
        raise
    else:
        for backup in backups.values():
            backup.unlink(missing_ok=True)
    finally:
        if ir_stage is not None:
            ir_stage.unlink(missing_ok=True)
        if receipt_stage is not None:
            receipt_stage.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile semantic document source into provider-neutral formatting IR."
    )
    parser.add_argument("--source", required=True)
    parser.add_argument("--design", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()

    try:
        source = _load(args.source)
        design = _load(args.design)
    except FileNotFoundError as exc:
        print(f"DF_INPUT_IO: file not found: {exc.filename}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError) as exc:
        print(f"DF_INPUT_IO: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(
            f"DF_INPUT_JSON: invalid JSON at line {exc.lineno} column {exc.colno}",
            file=sys.stderr,
        )
        return 2

    try:
        ir, receipt = MOD.compile_document(source, design)
    except MOD.DocumentCompileError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 2

    try:
        _publish_pair(Path(args.output), ir, Path(args.receipt), receipt)
    except ValueError as exc:
        print(f"DF_OUTPUT_PATH: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"DF_OUTPUT_IO: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
