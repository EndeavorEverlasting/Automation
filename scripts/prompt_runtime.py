#!/usr/bin/env python3
"""Thin Automation consumer of prompt-invocation-upstream/v1.

Prompt discovery, authority routing, intent semantics, and catalog shape are
upstream-owned. This wrapper only binds Automation to its pinned upstream
dependency and preserves the upstream resolution packet.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = ROOT / "vendor" / "prompt-invocation-upstream"
UPSTREAM_RESOLVER = VENDOR_ROOT / "prompt_invocation_resolver.py"
UPSTREAM_CATALOG = VENDOR_ROOT / "catalog.v1.json"
UPSTREAM_MANIFEST = VENDOR_ROOT / "manifest.v1.json"


class PromptRuntimeError(RuntimeError):
    pass


def _load_upstream():
    spec = importlib.util.spec_from_file_location(
        "automation_vendored_prompt_invocation_resolver", UPSTREAM_RESOLVER
    )
    if spec is None or spec.loader is None:
        raise PromptRuntimeError(f"cannot load upstream resolver: {UPSTREAM_RESOLVER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve(text: str) -> dict:
    upstream = _load_upstream()
    result = upstream.resolve_prompt_invocation(
        text,
        tc_root=ROOT,
        triage_root=None,
        catalog_path=UPSTREAM_CATALOG,
    )
    result["downstream_consumer"] = "EndeavorEverlasting/Automation"
    result["upstream_dependency_manifest"] = str(
        UPSTREAM_MANIFEST.relative_to(ROOT)
    ).replace("\\", "/")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True, help="Verbatim operator P-number request")
    parser.add_argument("--no-copy", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    result = resolve(args.text)
    if args.no_copy:
        for item in result.get("resolutions", []):
            item.pop("copy_content", None)

    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result.get("overall_state") == "RESOLVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
