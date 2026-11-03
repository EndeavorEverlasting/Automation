#!/usr/bin/env python3
"""Pinned, non-executing upstream source provisioning for visual-state-compare.

This tool clones SOURCE ONLY into an untracked external cache. It does not install
packages, download model weights, inspect private screenshots, or run donor code.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

CATALOG_PATH = Path(__file__).with_name("upstreams.v1.json")
REPO_ROOT = Path(__file__).resolve().parents[2]
VALID_ID = re.compile(r"^[a-z][a-z0-9-]{0,40}$")
VALID_SHA = re.compile(r"^[0-9a-f]{40}$")
VALID_URL = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git$")


class VisionStackError(Exception):
    pass


def default_root() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "Automation" / "VisionUpstreams"
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "automation" / "vision-upstreams"


def safe_root(raw: str | None) -> Path:
    root = Path(raw).expanduser().resolve() if raw else default_root().resolve()
    if root == REPO_ROOT or REPO_ROOT in root.parents:
        raise VisionStackError("CHECKOUT_INSIDE_REPOSITORY: use an external local directory")
    if root.exists() and not root.is_dir():
        raise VisionStackError("INVALID_CHECKOUT_ROOT: target is not a directory")
    return root


def read_catalog(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("contract_id") != "automation.visual-upstream-catalog/v1":
        raise VisionStackError("UNKNOWN_CATALOG_CONTRACT")
    items = obj.get("upstreams")
    if not isinstance(items, list) or not items:
        raise VisionStackError("EMPTY_CATALOG")
    seen = set()
    for item in items:
        name, url, sha = item.get("id"), item.get("url"), item.get("commit")
        if not all(isinstance(v, str) for v in (name, url, sha)):
            raise VisionStackError("INVALID_CATALOG_ITEM")
        if not (VALID_ID.fullmatch(name) and VALID_URL.fullmatch(url) and VALID_SHA.fullmatch(sha)):
            raise VisionStackError("UNSAFE_SOURCE_OR_PIN: " + str(name))
        if name in seen:
            raise VisionStackError("DUPLICATE_SOURCE: " + name)
        seen.add(name)
        if not isinstance(item.get("profiles"), list) or not item["profiles"]:
            raise VisionStackError("MISSING_PROFILES: " + name)
        if not set(item["profiles"]) <= {"foundation", "ui", "advanced"}:
            raise VisionStackError("UNRECOGNIZED_PROFILE: " + name)
    return obj


def select(catalog: dict, profile: str) -> list[dict]:
    return [item for item in catalog["upstreams"]
            if profile == "all" or profile in item["profiles"]]


def git(args: list[str], *, cwd: Path | None = None, timeout: int = 240) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
            env={**os.environ, "GIT_LFS_SKIP_SMUDGE": "1", "GIT_CONFIG_NOSYSTEM": "1",
                 "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}
        )
    except FileNotFoundError as error:
        raise VisionStackError("GIT_UNAVAILABLE") from error
    except subprocess.TimeoutExpired as error:
        raise VisionStackError("GIT_TIMEOUT") from error
    if result.returncode:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "git failed"
        raise VisionStackError("GIT_FAILED: " + detail[:400])
    return result.stdout.strip()


def checkout_state(item: dict, root: Path) -> str:
    target = root / item["id"]
    if not target.exists():
        return "NOT_CLONED"
    if not target.is_dir() or not (target / ".git").exists():
        return "PATH_COLLISION"
    try:
        head = git(["rev-parse", "HEAD"], cwd=target, timeout=15)
        if head != item["commit"]:
            return "PIN_MISMATCH"
        if git(["remote", "get-url", "origin"], cwd=target, timeout=15) != item["url"]:
            return "ORIGIN_MISMATCH"
        if git(["status", "--porcelain"], cwd=target, timeout=15):
            return "DIRTY_CHECKOUT"
    except VisionStackError:
        return "UNVERIFIED_CHECKOUT"
    return "READY"


def sync_one(item: dict, root: Path) -> str:
    state = checkout_state(item, root)
    if state == "READY":
        return "READY"
    if state != "NOT_CLONED":
        return state  # fail closed; never reset user-modified or drifted clones
    root.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="." + item["id"] + "-staging-", dir=root))
    target = root / item["id"]
    try:
        git(["init", "-q", str(tmp)])
        git(["remote", "add", "origin", item["url"]], cwd=tmp)
        git(["-c", "protocol.file.allow=never", "fetch", "--no-tags",
             "--depth=1", "origin", item["commit"]], cwd=tmp)
        git(["-c", "core.hooksPath=NUL" if os.name == "nt" else "core.hooksPath=/dev/null",
             "checkout", "-q", "--detach", "FETCH_HEAD"], cwd=tmp)
        if git(["rev-parse", "HEAD"], cwd=tmp) != item["commit"]:
            raise VisionStackError("FETCHED_PIN_MISMATCH")
        if target.exists():
            raise VisionStackError("TARGET_CREATED_CONCURRENTLY")
        tmp.rename(target)
        return checkout_state(item, root)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)


def report_rows(items: list[dict], root: Path) -> list[dict]:
    return [{"id": item["id"], "pin": item["commit"], "profiles": item["profiles"],
             "status": checkout_state(item, root)} for item in items]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "sync", "doctor"])
    parser.add_argument("--profile", choices=["foundation", "ui", "advanced", "all"],
                        default="foundation")
    parser.add_argument("--root", help="Absolute external, local clone/cache directory")
    parser.add_argument("--catalog", default=str(CATALOG_PATH))
    args = parser.parse_args(argv)
    try:
        root = safe_root(args.root)
        catalog = read_catalog(Path(args.catalog))
        items = select(catalog, args.profile)
        rows = []
        for item in items:
            try:
                if args.command == "sync":
                    state = sync_one(item, root)
                else:
                    state = checkout_state(item, root)
            except VisionStackError as error:
                state = str(error)
            rows.append({"id": item["id"], "pin": item["commit"],
                         "profiles": item["profiles"], "status": state})
        payload = {
            "contract_id": "automation.visual-upstream-checkout/v1",
            "operation": args.command,
            "profile": args.profile,
            "source_catalog": catalog["contract_id"],
            "source_snapshot_date": catalog["snapshot_date"],
            "root_policy": "EXTERNAL_LOCAL_ONLY",
            "donor_code_executed": False,
            "packages_installed": False,
            "weights_installed": False,
            "engines_runtime_verified": False,
            "sources": rows
        }
        print(json.dumps(payload, indent=2))
        if args.command == "plan":
            return 0
        return 0 if all(row["status"] == "READY" for row in rows) else 2
    except (OSError, ValueError, VisionStackError, json.JSONDecodeError) as error:
        print(json.dumps({"contract_id": "automation.visual-upstream-checkout/v1",
                          "status": "BLOCKED", "error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
