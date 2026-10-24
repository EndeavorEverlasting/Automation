"""Synthetic tick script referenced by fixtures/registry.synthetic.v1.json."""
from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.parse_args()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
