#!/usr/bin/env python3
"""Offline-first Git repository portability, public source only (v1)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

CONTRACT = "git-portability/v1"
MARKER = "archive.manifest.json"


class PortabilityError(Exception):
    pass


def git(*args: str, cwd: Path | None = None) -> str:
    cmd = ["git", *(["-C", str(cwd)] if cwd else []), *args]
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PortabilityError(f"Git operation failed: {args[0]}") from exc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def source_check(repo: Path) -> tuple[str, dict[str, str]]:
    if not repo.is_dir():
        raise PortabilityError("SOURCE_MISSING")
    is_bare = git("rev-parse", "--is-bare-repository", cwd=repo) == "true"
    if git("rev-parse", "--is-shallow-repository", cwd=repo) != "false":
        raise PortabilityError("SHALLOW_SOURCE_UNSUPPORTED")
    if not is_bare:
        if git("status", "--porcelain", "--untracked-files=all", cwd=repo):
            raise PortabilityError("DIRTY_SOURCE_UNSUPPORTED")
        if (repo / ".gitmodules").exists():
            raise PortabilityError("SUBMODULE_CONTENT_NOT_SELF_CONTAINED")
        attributes = list(repo.rglob(".gitattributes"))
        if any("filter=lfs" in p.read_text(encoding="utf-8", errors="replace") for p in attributes if ".git" not in p.parts):
            raise PortabilityError("LFS_OBJECTS_NOT_SELF_CONTAINED")
    head = git("rev-parse", "HEAD", cwd=repo)
    refs = {}
    for line in git("show-ref", cwd=repo).splitlines():
        oid, name = line.split(" ", 1)
        if name.startswith("refs/"):
            refs[name] = oid
    if not refs:
        raise PortabilityError("NO_BRANCHES_OR_TAGS")
    return head, refs


def archive_snapshot(source: Path, output: Path, visibility: str) -> dict:
    if visibility != "public":
        raise PortabilityError("PRIVATE_ARCHIVE_REQUIRES_ENCRYPTED_ADAPTER")
    if output.exists():
        raise PortabilityError("OUTPUT_ALREADY_EXISTS")
    source = source.resolve(strict=True)
    output = output.resolve()
    if source == output or source in output.parents:
        raise PortabilityError("OUTPUT_INSIDE_SOURCE")
    head, refs = source_check(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="git-portability-", dir=output.parent) as td:
        bundle = Path(td) / "repository.bundle"
        git("bundle", "create", str(bundle), "--all", cwd=source)
        git("bundle", "verify", str(bundle), cwd=source)
        manifest = {
            "schema_version": CONTRACT,
            "source_kind": "local_git_repository",
            "visibility": "public",
            "head": head,
            "refs": refs,
            "bundle_sha256": sha256(bundle),
            "bundle_size": bundle.stat().st_size,
            "limitations": ["not Git LFS, submodule contents, issues, pull requests, releases, account metadata or CI credentials"],
        }
        staged = Path(td) / "staged.zip"
        with zipfile.ZipFile(staged, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(bundle, "repository.bundle")
            archive.writestr(MARKER, json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        verify_archive(staged)
        # Atomic, create-only publish within the destination filesystem.
        os.link(staged, output)
    return {"state": "BACKUP_CREATED", "head": head, "refs_count": len(refs), "sha256": sha256(output), "path": str(output)}


def verify_archive(path: Path) -> dict:
    with zipfile.ZipFile(path, "r") as archive:
        if sorted(archive.namelist()) != [MARKER, "repository.bundle"]:
            raise PortabilityError("ARCHIVE_LAYOUT_INVALID")
        manifest = json.loads(archive.read(MARKER))
        if manifest.get("schema_version") != CONTRACT or manifest.get("visibility") != "public":
            raise PortabilityError("ARCHIVE_CONTRACT_INVALID")
        with tempfile.TemporaryDirectory() as td:
            bundle = Path(td) / "repository.bundle"
            with bundle.open("wb") as out, archive.open("repository.bundle") as inp:
                shutil.copyfileobj(inp, out, 1024 * 1024)
            if sha256(bundle) != manifest["bundle_sha256"] or bundle.stat().st_size != manifest["bundle_size"]:
                raise PortabilityError("ARCHIVE_HASH_MISMATCH")
            # Bundle verification needs a Git repository context. A temporary repository supplies it.
            git("init", "--bare", str(Path(td) / "verify.git"))
            git("bundle", "verify", str(bundle), cwd=Path(td) / "verify.git")
    return manifest


def restore_archive(archive_path: Path, dest: Path) -> dict:
    if dest.exists():
        raise PortabilityError("RESTORE_DESTINATION_EXISTS")
    with zipfile.ZipFile(archive_path) as package:
        manifest = json.loads(package.read(MARKER))
        if manifest.get("schema_version") != CONTRACT:
            raise PortabilityError("ARCHIVE_CONTRACT_INVALID")
        with tempfile.TemporaryDirectory(prefix="git-portability-restore-") as td:
            bundle = Path(td) / "repository.bundle"
            with bundle.open("wb") as out, package.open("repository.bundle") as inp:
                shutil.copyfileobj(inp, out, 1024 * 1024)
            if sha256(bundle) != manifest["bundle_sha256"]:
                raise PortabilityError("ARCHIVE_HASH_MISMATCH")
            git("clone", "--mirror", str(bundle), str(dest))
    restored = git("rev-parse", "HEAD", cwd=dest)
    if restored != manifest["head"]:
        raise PortabilityError("RESTORED_HEAD_MISMATCH")
    for name, oid in manifest["refs"].items():
        if git("rev-parse", name, cwd=dest) != oid:
            raise PortabilityError("RESTORED_REF_MISMATCH")
    git("fsck", "--full", "--no-reflogs", cwd=dest)
    return {"state": "RESTORED_AND_VERIFIED", "head": restored, "refs_count": len(manifest["refs"]), "path": str(dest)}


def upload_to_rclone(archive: Path, remote: str) -> dict:
    if shutil.which("rclone") is None:
        raise PortabilityError("RCLONE_NOT_INSTALLED")
    if not archive.is_file():
        raise PortabilityError("ARCHIVE_NOT_FOUND")
    if ":" not in remote or remote.startswith(("http:", "https:", "/")):
        raise PortabilityError("REMOTE_MUST_BE_CONFIGURED_RCLONE_PATH")
    if len(remote) > 512 or "@" in remote.split(":", 1)[0]:
        raise PortabilityError("REMOTE_FORMAT_INVALID")
    # No auth material or local paths included in receipts; configured remote credentials remain outside Git.
    def run(*args: str, stdout=None):
        p = subprocess.run(["rclone", *args], stdout=stdout or subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode:
            raise PortabilityError("REMOTE_TRANSFER_FAILED")
        return p
    remote_dir, _, name = remote.rpartition("/")
    if not name or not remote_dir:
        raise PortabilityError("REMOTE_MUST_INCLUDE_FILENAME")
    listing = run("lsf", remote_dir).stdout.decode("utf-8", "replace").splitlines()
    if name in listing:
        raise PortabilityError("REMOTE_DESTINATION_ALREADY_EXISTS")
    run("copyto", str(archive), remote)
    proc = subprocess.Popen(["rclone", "cat", remote], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    digest = hashlib.sha256()
    for block in iter(lambda: proc.stdout.read(1024 * 1024), b""):
        digest.update(block)
    if proc.wait() != 0 or digest.hexdigest() != sha256(archive):
        raise PortabilityError("REMOTE_READBACK_HASH_MISMATCH")
    return {"state": "UPLOAD_READBACK_VERIFIED", "sha256": digest.hexdigest()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    back = sub.add_parser("backup")
    back.add_argument("--repo", type=Path, required=True)
    back.add_argument("--output", type=Path, required=True)
    back.add_argument("--visibility", choices=["public", "private"], required=True)
    chk = sub.add_parser("verify")
    chk.add_argument("--archive", type=Path, required=True)
    rest = sub.add_parser("restore")
    rest.add_argument("--archive", type=Path, required=True)
    rest.add_argument("--destination", type=Path, required=True)
    upl = sub.add_parser("upload")
    upl.add_argument("--archive", type=Path, required=True)
    upl.add_argument("--remote", required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "backup":
            result = archive_snapshot(args.repo, args.output, args.visibility)
        elif args.action == "verify":
            m = verify_archive(args.archive)
            result = {"state": "HASH_AND_BUNDLE_VERIFIED", "head": m["head"], "refs_count": len(m["refs"])}
        elif args.action == "restore":
            result = restore_archive(args.archive, args.destination)
        else:
            m = verify_archive(args.archive)
            result = upload_to_rclone(args.archive, args.remote)
            result["head"] = m["head"]
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PortabilityError, ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
        print(json.dumps({"state": "BLOCKED", "reason": str(error) if isinstance(error, PortabilityError) else "INVALID_ARCHIVE_OR_IO"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
