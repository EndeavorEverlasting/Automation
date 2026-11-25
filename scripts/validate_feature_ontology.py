"""Fail-closed exact-file ownership and feature-map projection validation."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import quote

ONTOLOGY = "harness/contracts/feature-ontology.v1.json"
PROJECTION = "FEATURE_MAP.md"
ROLES = {"source", "adapter", "test", "contract", "fixture", "workflow", "vendor", "documentation"}
SOURCE_SUFFIXES = {".py", ".pyi", ".mjs", ".cjs", ".js", ".jsx", ".ts", ".tsx", ".ps1", ".psm1",
                   ".sh", ".bash", ".cmd", ".bat", ".gs", ".rb", ".go", ".rs", ".java", ".kt",
                   ".c", ".h", ".cpp", ".hpp", ".cs", ".php", ".lua", ".sql", ".swift", ".html", ".css"}


def expected_role(path):
    parts = PurePosixPath(path).parts
    suffix = PurePosixPath(path).suffix.lower()
    if path.startswith(".github/workflows/"):
        return "workflow"
    if parts[0] == "vendor":
        return "vendor"
    if "fixtures" in parts or "examples" in parts or "evidence" in parts:
        return "fixture"
    if "tests" in parts:
        return "test"
    if suffix in SOURCE_SUFFIXES:
        return "adapter" if "adapters" in parts else "source"
    if suffix == ".json":
        return "contract"
    return "documentation"


def untracked_source_paths(root):
    raw = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=root)
    return sorted(p for p in raw.decode("utf-8").split("\\0")
                  if p and PurePosixPath(p).suffix.lower() in SOURCE_SUFFIXES)


def link(path):
    return f"[`{path}`]({quote(path, safe='/')})"


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
        if not isinstance(feature, dict) or set(feature) != {"id", "summary", "files", "entrypoints"}:
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
            if role != expected_role(path):
                raise ValueError(f"role mismatch: {path}: expected {expected_role(path)}, got {role}")
            parts = PurePosixPath(path).parts
            if parts[0] == "capabilities" and (len(parts) < 3 or parts[1] != ident):
                raise ValueError(f"capability owner mismatch: {path}: {ident}")
            if path in owners:
                raise ValueError(f"duplicate owner for {path}: {owners[path]}, {ident}")
            owners[path] = ident
        entries = feature["entrypoints"]
        if not isinstance(entries, list) or any(not isinstance(p, str) for p in entries):
            raise ValueError(f"invalid entrypoints: {ident}")
        if len(set(entries)) != len(entries):
            raise ValueError(f"duplicate entrypoints: {ident}")
        eligible = {item["path"] for item in files if item["role"] in {"source", "adapter"}}
        if not set(entries) <= eligible:
            raise ValueError(f"entrypoint lacks matching owned source: {ident}")
        if eligible and not entries:
            raise ValueError(f"feature with executable source has no entrypoint: {ident}")
    return {"features": len(ids), "tracked": len(actual), "mapped": len(owners),
            "unmapped": sorted(actual - owners.keys()),
            "stale": sorted(owners.keys() - actual)}


def check_capability_contracts(root, ontology, actual):
    features = {feature["id"]: feature for feature in ontology["features"]}
    for path in sorted(actual):
        parts = PurePosixPath(path).parts
        if len(parts) != 3 or parts[0] != "capabilities" or parts[-1] != "capability.v1.json":
            continue
        ident = parts[1]
        contract = json.loads((root / path).read_text(encoding="utf-8"),
                              object_pairs_hook=reject_duplicate_keys)
        if not isinstance(contract, dict) or contract.get("capability_id") != ident:
            raise ValueError(f"capability contract identity mismatch: {path}")
        entries = contract.get("entrypoints", {})
        if not isinstance(entries, dict):
            raise ValueError(f"invalid capability entrypoints: {path}")
        declared = [contract[key] for key in ("entrypoint", "validator") if key in contract]
        declared.extend(entries.values())
        if any(not isinstance(value, str) or not value.strip() for value in declared):
            raise ValueError(f"invalid capability entrypoint value: {path}")
        declared_paths = {re.split(r"[\\s#]", value.strip(), maxsplit=1)[0] for value in declared}
        if declared_paths != set(features[ident]["entrypoints"]):
            raise ValueError(f"capability entrypoint drift: {path}: expected {sorted(declared_paths)}")


def render(ontology):
    features = sorted(ontology["features"], key=lambda f: f["id"])
    lines = ["# Automation feature map", "",
             "Generated from `harness/contracts/feature-ontology.v1.json`. Do not edit this projection manually.", "",
             "Every tracked path has exactly one primary feature owner. This includes implementation, adapters, tests, contracts, fixtures, workflows, vendor files and documentation. No wildcard ownership or catch-all exclusions. Capability directory ownership, file roles and declared entrypoints are checked against existing repository contracts.", "",
             "Validate locally: `python scripts/validate_feature_ontology.py`", "",
             "When adding, deleting, renaming or moving files, update the ontology, stage the affected paths, and regenerate this map in the same change: `python scripts/validate_feature_ontology.py --render` (redirect to FEATURE_MAP.md using UTF-8). The repository test suite checks both coverage and projection parity. The local validator also rejects non-ignored, unstaged source files.", "",
             f"**{len(features)} features; {sum(len(f['files']) for f in features)} mapped paths.**", ""]
    for feature in features:
        lines.extend([f"## {feature['id']}", "", feature["summary"], ""])
        if feature["entrypoints"]:
            lines.append("Entrypoints:")
            lines.extend(f"- {link(path)}" for path in sorted(feature["entrypoints"]))
            lines.append("")
        for entry in sorted(feature["files"], key=lambda e: e["path"]):
            path = entry["path"]
            lines.append(f"- `{entry['role']}` — {link(path)}")
        lines.append("")
    return "\n".join(lines) + "\n"


def validate(root):
    ontology = load(root)
    actual = indexed_paths(root)
    result = inspect(ontology, actual)
    check_capability_contracts(root, ontology, actual)
    result["untracked_source"] = untracked_source_paths(root)
    result["missing_worktree_paths"] = sorted(
        p for p in actual if not (root / p).exists() and not (root / p).is_symlink())
    result["projection_matches"] = ((root / PROJECTION).read_text(encoding="utf-8") == render(ontology))
    result["ok"] = (not result["unmapped"] and not result["stale"]
                    and not result["missing_worktree_paths"] and not result["untracked_source"]
                    and result["projection_matches"])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--render", action="store_true", help="print deterministic Markdown projection")
    args = parser.parse_args(argv)
    try:
        if args.render:
            ontology = load(args.root)
            actual = indexed_paths(args.root)
            coverage = inspect(ontology, actual)
            check_capability_contracts(args.root, ontology, actual)
            if coverage["unmapped"] or coverage["stale"] or untracked_source_paths(args.root):
                raise ValueError("resolve and stage all mappings before rendering")
            sys.stdout.buffer.write(render(ontology).encode("utf-8"))
            return 0
        result = validate(args.root)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True), file=sys.stderr if args.render else sys.stdout)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
