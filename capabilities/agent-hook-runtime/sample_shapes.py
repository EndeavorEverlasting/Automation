#!/usr/bin/env python3
"""Deterministic harness-shape sampling and certification entrypoint.

Replays the tracked positive/negative shape-sampling matrix against the
canonical protocol registry and writes a typed, privacy-safe receipt.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.shape_sampler import receipt_json, run_sampling_matrix

CAP_ROOT = Path(__file__).resolve().parent
DEFAULT_REGISTRY = CAP_ROOT / "profiles" / "current.v1.json"
DEFAULT_MATRIX = CAP_ROOT / "fixtures" / "shape-sampling-matrix.synthetic.v1.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Replay the deterministic hook shape sampling/certification matrix"
    )
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--matrix", default=str(DEFAULT_MATRIX))
    parser.add_argument("--output", required=True, help="Path for the sampling receipt")
    args = parser.parse_args(argv)

    registry = json.loads(Path(args.registry).read_text(encoding="utf-8"))
    matrix = json.loads(Path(args.matrix).read_text(encoding="utf-8"))
    receipt = run_sampling_matrix(registry, matrix)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(receipt_json(receipt), encoding="utf-8")

    print(
        json.dumps(
            {
                "schema_version": receipt["schema_version"],
                "state": receipt["state"],
                "case_count": receipt["case_count"],
                "failed_case_ids": receipt["failed_case_ids"],
                "sensitivity": receipt["sensitivity"],
            },
            sort_keys=True,
        )
    )
    return 0 if receipt["state"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
