#!/usr/bin/env python3
"""In-process paddle worker invoked by vision_cli via an isolated interpreter."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from recognize import recognize  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lang", default="en")
    parser.add_argument("--timeout-sec", type=float, default=120.0)
    parser.add_argument("--dpi-scale", type=float, default=1.0)
    parser.add_argument("--privacy", default="UNCLASSIFIED")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args(argv)
    receipt = recognize(
        args.input,
        lang=args.lang,
        timeout_sec=args.timeout_sec,
        dpi_scale=args.dpi_scale,
        privacy=args.privacy,
        device=args.device,
    )
    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return 0 if receipt["status"] in {"OK", "NO_TEXT"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
