"""Fail-closed exact-file ownership and feature-map projection validation."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ONTOLOGY = "harness/contracts/feature-ontology.v1.json"
PROJECTION = "FEATURE_MAP.md"
ROLES = {"source", "adapter", "test", "contract", "fixture", "workflow", "vendor", "documentation"}


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(root):
    return json.loads((root / ONTOLOGY).read_text(encoding="utf-8"),
                      object_pairs_hook=reject_duplicate_keys)


def indexed_paths(root):
    actual = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=root,
                                     text=True).strip()
    if Path(actual).resolve() != root.resolve():
        raise ValueError("validator must run against the repository root")
    raw = subprocess.check_output(["git", "ls-files", "--cached", "-z"], cwd=root)
    return set(raw.decode("utf-8").split("\0")) - {""}


def inspect(ontology, actual):
    if not isinstance(ontology, dict) or set(ontology) != {"schema_version", "coverage", "features"}:
        raise ValueError("invalid ontology shape")
    if ontology["schema_version"] != "feature-ontology/v1" or ontology["coverage"] != "all-git-index-paths":
        raise ValueError("unknown schema or coverage policy")
    features = ontology["features"]
    if not isinstance(features, list) or not features:
        raise ValueError("features must be a nonempty list")
    owners = {}
    ids = set()
    for feature in features:
        if not isinstance(feature, dict) or set(feature) != {"id", "summary", "files"}:
            raise ValueError("invalid feature shape")
        ident, summary, files = feature["id"], feature["summary"], feature["files"]
        if not isinstance(ident, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", ident) or ident in ids:
            raise ValueError(f"invalid or duplicate feature ID: {ident}")
        ids.add(ident)
        if not isinstance(summary, str) or not summary.strip() or "\n" in summary or "\r" in summary:
            raise ValueError(f"invalid feature summary: {ident}")
        if not isinstance(files, list) or not files:
            raise ValueError(f"empty feature: {ident}")
        for item in files:
            if not isinstance(item, dict) or set(item) != {"path", "role"}:
                raise ValueError(f"invalid file record: {ident}")
            path, role = item["path"], item["role"]
            if not isinstance(path, str) or not path or path.startswith("/") or any(c in path for c in "\\*?[]\r\n\0`") or any(p in ("", ".", "..") for p in path.split("/")) or PurePosixPath(path).as_posix() != path:
                raise ValueError(f"not an exact repository path: {path!r}")
            if not isinstance(role, str) or role not in ROLES:
                raise ValueError(f"invalid role: {path}")
            if path in owners:
                raise ValueError(f"duplicate owner for {path}: {owners[path]}, {ident}")
            owners[path] = ident
    return {"features": len(ids), "tracked": len(actual), "mapped": len(owners),
            "unmapped": sorted(actual - owners.keys()),
            "stale": sorted(owners.keys() - actual)}


def render(ontology):
    features = sorted(ontology["features"], key=lambda f: f["id"])
    lines = ["# Automation feature map", "",
             "Generated from `harness/contracts/feature-ontology.v1.json`. Do not edit this projection manually.", "",
             "Every tracked path has exactly one primary feature owner. This includes implementation, adapters, tests, contracts, fixtures, workflows, vendor files and documentation. No wildcard ownership or catch-all exclusions.", "",
             "Validate locally: `python scripts/validate_feature_ontology.py`", "",
             "When adding, deleting, renaming or moving files, update the ontology and regenerate this map in the same change: `python scripts/validate_feature_ontology.py --render` (redirect to FEATURE_MAP.md using UTF-8). The repository test suite checks both coverage and projection parity.", "",
             f"**{len(features)} features; {sum(len(f['files']) for f in features)} mapped paths.**", ""]
    for feature in features:
        lines.extend([f"## {feature['id']}", "", feature["summary"], ""])
        for entry in sorted(feature["files"], key=lambda e: e["path"]):
            path = entry["path"]
            lines.append(f"- `{entry['role']}` — [`{path}`]({path})")
        lines.append("")
    return "\n".join(lines) + "\n"


def validate(root):
    ontology = load(root)
    actual = indexed_paths(root)
    result = inspect(ontology, actual)
    result["missing_worktree_paths"] = sorted(
        p for p in actual if not (root / p).exists() and not (root / p).is_symlink())
    result["projection_matches"] = ((root / PROJECTION).read_text(encoding="utf-8") == render(ontology))
    result["ok"] = (not result["unmapped"] and not result["stale"]
                    and not result["missing_worktree_paths"] and result["projection_matches"])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--render", action="store_true", help="print deterministic Markdown projection")
    args = parser.parse_args(argv)
    try:
        if args.render:
            ontology = load(args.root)
            inspect(ontology, indexed_paths(args.root))
            sys.stdout.buffer.write(render(ontology).encode("utf-8"))
            return 0
        result = validate(args.root)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
