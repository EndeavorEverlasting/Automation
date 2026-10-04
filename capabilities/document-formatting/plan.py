#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "document_formatting_contract",
    ROOT / "core" / "contract.py",
)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a consumer document-formatting profile and emit a portable plan."
    )
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    errors = MOD.validate_profile(profile)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2

    plan = MOD.build_plan(profile)
    rendered = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
