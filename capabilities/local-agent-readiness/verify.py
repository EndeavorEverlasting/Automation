#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.readiness import (  # noqa: E402
    GATE_ORDER,
    ReadinessError,
    agent_profile_digest,
    assess_readiness,
    load_profile,
)


def _parse_required_gates(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        for item in value.split(","):
            item = item.strip()
            if not item:
                continue
            if item not in GATE_ORDER:
                raise ReadinessError(f"unsupported required gate: {item}")
            if item not in result:
                result.append(item)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assess repository-local agent readiness without repairing configuration."
    )
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument(
        "--refresh-remote",
        action="store_true",
        help="Fetch the configured baseline ref; does not alter the working tree.",
    )
    parser.add_argument("--runtime-observation", type=Path)
    parser.add_argument(
        "--probe-remote-write",
        action="store_true",
        help="Run git push --dry-run only; never creates or updates a ref.",
    )
    parser.add_argument(
        "--actual-push-ref",
        help="Explicit refs/heads/* branch to verify by read-only remote readback.",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit nonzero unless every gate required by the selected agent profile is PASS.",
    )
    parser.add_argument(
        "--require-gate",
        action="append",
        default=[],
        help="Exit nonzero unless this gate is PASS; may be repeated or comma-separated.",
    )
    parser.add_argument(
        "--print-agent-profile-sha256",
        action="store_true",
        help="Print the selected normalized agent-profile digest and exit.",
    )
    args = parser.parse_args(argv)

    try:
        profile = load_profile(args.profile.expanduser().resolve())
        if args.print_agent_profile_sha256:
            print(agent_profile_digest(profile, args.agent))
            return 0

        receipt = assess_readiness(
            args.repo_root,
            profile,
            agent_id=args.agent,
            refresh_remote=args.refresh_remote,
            runtime_observation=args.runtime_observation,
            probe_remote_write=args.probe_remote_write,
            actual_push_ref=args.actual_push_ref,
        )
        required = _parse_required_gates(args.require_gate)
    except ReadinessError as exc:
        print(
            json.dumps(
                {
                    "schema_version": "local-agent-readiness-error/v1",
                    "state": "ERROR",
                    "error": str(exc),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")

    failures = [gate for gate in required if receipt["gates"][gate]["state"] != "PASS"]
    if failures:
        return 1
    if args.require_ready and receipt["state"] != "READY":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
