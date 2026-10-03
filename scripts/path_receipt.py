#!/usr/bin/env python3
"""Emit a P92-style canonical path and execution-context receipt.

The script proves only what the current runtime can observe. It never invents a
checkout, production path, shell, deployment state, or user-specific literal.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "harness" / "contracts" / "canonical-path.v1.json"


class PathReceiptError(RuntimeError):
    pass


GitRunner = Callable[[Path, list[str]], tuple[int, str, str]]


def run_git(root: Path, args: list[str]) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "", str(exc)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def normalize_repo_identity(remote: str | None) -> str | None:
    if not remote:
        return None
    value = remote.strip().rstrip("/")
    patterns = (
        r"^https?://github\.com/([^/]+/[^/]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/([^/]+/[^/]+?)(?:\.git)?$",
        r"^git@github\.com:([^/]+/[^/]+?)(?:\.git)?$",
        r"^git://github\.com/([^/]+/[^/]+?)(?:\.git)?$",
    )
    for pattern in patterns:
        match = re.match(pattern, value, re.IGNORECASE)
        if match:
            return re.sub(r"\.git$", "", match.group(1), flags=re.IGNORECASE)
    return None


def _load_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PathReceiptError(f"cannot read canonical path contract {path}: {exc}") from exc
    if payload.get("schema_version") != "automation-canonical-path/v1":
        raise PathReceiptError("unsupported canonical path contract schema")
    return payload


def _git_value(root: Path, args: list[str], git_runner: GitRunner) -> dict[str, Any]:
    rc, stdout, stderr = git_runner(root, args)
    return {
        "state": "OBSERVED" if rc == 0 and stdout else "UNKNOWN",
        "value": stdout or None,
        "return_code": rc,
        "error": stderr or None,
    }


def _execution_target(env: Mapping[str, str]) -> str:
    if env.get("CI"):
        return "CI"
    if env.get("WSL_DISTRO_NAME"):
        return "WSL"
    if Path("/.dockerenv").exists() or env.get("CONTAINER"):
        return "CONTAINER"
    return "LOCAL"


def build_receipt(
    repo_root: Path,
    contract: dict[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    git_runner: GitRunner = run_git,
) -> dict[str, Any]:
    env = env or os.environ
    repo_root = repo_root.resolve()
    profile = contract["profiles"]["default"]
    dev_contract = profile["development_checkout"]
    prod_contract = profile["production_use"]

    top = _git_value(repo_root, ["rev-parse", "--show-toplevel"], git_runner)
    origin = _git_value(repo_root, ["config", "--get", "remote.origin.url"], git_runner)
    head = _git_value(repo_root, ["rev-parse", "HEAD"], git_runner)

    observed_root = Path(top["value"]).resolve() if top["value"] else None
    observed_identity = normalize_repo_identity(origin["value"])
    expected_identity = str(dev_contract["required_remote_identity"])
    configured_dev_raw = env.get(str(dev_contract["environment_variable"]))
    configured_dev = Path(configured_dev_raw).expanduser().resolve() if configured_dev_raw else None

    dev_reasons: list[str] = []
    if observed_root is None:
        dev_state = "UNKNOWN"
        dev_reasons.append("Git did not prove a repository top-level directory.")
    elif observed_identity is None:
        dev_state = "UNKNOWN"
        dev_reasons.append("Git remote.origin.url did not resolve to a supported repository identity.")
    elif observed_identity.lower() != expected_identity.lower():
        dev_state = "CONFLICT"
        dev_reasons.append(
            f"Observed remote identity {observed_identity!r} does not match {expected_identity!r}."
        )
    elif configured_dev is not None and configured_dev != observed_root:
        dev_state = "CONFLICT"
        dev_reasons.append(
            "AUTOMATION_DEV_ROOT conflicts with the verified current checkout root."
        )
    else:
        dev_state = "CANONICAL_PROVED"
        dev_reasons.append("Current checkout root and remote identity satisfy the tracked default profile.")

    worktree_raw = env.get(str(profile["worktree_root"]["environment_variable"]))
    worktree_root = str(Path(worktree_raw).expanduser().resolve()) if worktree_raw else None

    prod_raw = env.get(str(prod_contract["environment_variable"]))
    prod_path = Path(prod_raw).expanduser().resolve() if prod_raw else None
    raw_prod_state = env.get(str(prod_contract["state_environment_variable"]), "UNKNOWN").upper()
    allowed_states = set(prod_contract["allowed_use_states"])
    prod_state = raw_prod_state if raw_prod_state in allowed_states else "UNKNOWN"
    prod_mutation_allowed = bool(prod_path and prod_state in {"QUIESCED", "OFFLINE"})

    if observed_root is None or prod_path is None:
        path_relation = "UNKNOWN"
    elif observed_root == prod_path:
        path_relation = "SAME_PHYSICAL_PATH_PRODUCTION_IMPACTING"
        prod_mutation_allowed = False if prod_state in {"ACTIVE", "UNKNOWN"} else prod_mutation_allowed
    else:
        path_relation = "SEPARATE_PATHS"

    shell = env.get("SHELL") or env.get("COMSPEC")
    execution_context_state = "OBSERVED_PARTIAL" if shell else "UNKNOWN"

    if dev_state == "CANONICAL_PROVED":
        next_action = "Use this verified checkout for development mutation or an explicitly approved worktree."
    elif dev_state == "CONFLICT":
        next_action = "Do not mutate or create another clone until the checkout/profile conflict is reconciled."
    else:
        next_action = "Set/verify the canonical development checkout; UNKNOWN does not authorize a new clone."

    return {
        "schema_version": "automation-path-input-receipt/v1",
        "contract_id": contract["contract_id"],
        "repository": contract["repository"],
        "profile": "default",
        "path_input_receipt": {
            "requested_repo_root": str(repo_root),
            "git_top_level": top,
            "origin": origin,
            "normalized_origin_identity": observed_identity,
            "expected_origin_identity": expected_identity,
            "configured_development_root": str(configured_dev) if configured_dev else None,
            "development_state": dev_state,
            "development_reasons": dev_reasons,
            "worktree_root": worktree_root,
            "production_use_path": str(prod_path) if prod_path else None,
            "production_use_state": prod_state,
            "production_mutation_allowed": prod_mutation_allowed,
            "path_relation": path_relation,
        },
        "execution_context_receipt": {
            "state": execution_context_state,
            "execution_target": _execution_target(env),
            "platform_system": platform.system(),
            "platform_release": platform.release(),
            "python_executable": sys.executable,
            "shell_or_interpreter_host": shell,
            "terminal_program": env.get("TERM_PROGRAM"),
            "wsl_distribution": env.get("WSL_DISTRO_NAME"),
        },
        "version_receipt": {
            "head": head,
            "REMOTE_INTEGRATED": "UNKNOWN",
            "DEV_CHECKOUT_CURRENT": "IDENTITY_PROVED_VERSION_FRESHNESS_UNPROVEN"
            if dev_state == "CANONICAL_PROVED"
            else "UNKNOWN",
            "PROD_PATH_CURRENT": "UNKNOWN",
            "ENTRYPOINT_PROVED": "UNKNOWN",
        },
        "safe_next_action": next_action,
        "proof_ceiling": (
            "This receipt proves only locally observed checkout identity/path inputs and execution context. "
            "It does not prove remote ancestry, production deployment, production freshness, or entrypoint behavior."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT), help="Existing checkout to inspect")
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT), help="Canonical path contract JSON")
    parser.add_argument("--output", help="Optional JSON receipt output path")
    args = parser.parse_args(argv)

    try:
        contract = _load_contract(Path(args.contract))
        receipt = build_receipt(Path(args.repo_root), contract)
    except PathReceiptError as exc:
        print(f"path-receipt error: {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(receipt, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")

    state = receipt["path_input_receipt"]["development_state"]
    return 0 if state == "CANONICAL_PROVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
