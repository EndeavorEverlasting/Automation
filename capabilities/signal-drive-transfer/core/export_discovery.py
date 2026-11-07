"""Deterministic discovery of Signal Save-As export directories."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class ExportDiscoveryError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


EXPORT_DIR_RE = re.compile(r"^export-\d{8}-\d{6}$")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _is_export_dir(path: Path) -> bool:
    if not path.is_dir() or path.is_symlink():
        return False
    if EXPORT_DIR_RE.match(path.name):
        return True
    # Also accept a directory that already contains Signal Save-As PNGs.
    images = [
        child
        for child in path.iterdir()
        if child.is_file()
        and not child.is_symlink()
        and child.suffix.lower() in IMAGE_SUFFIXES
        and child.name.lower().startswith("signal-")
    ]
    return len(images) > 0


def list_export_dirs(root: Path) -> list[Path]:
    if root.is_symlink() or not root.is_dir():
        raise ExportDiscoveryError("EXPORT_ROOT_MISSING", f"export root missing: {root}")
    found: list[Path] = []
    for child in root.iterdir():
        if _is_export_dir(child):
            found.append(child.resolve())
    # Prefer timestamped names; fall back to mtime.
    def sort_key(path: Path) -> tuple[int, str, float]:
        match = EXPORT_DIR_RE.match(path.name)
        if match:
            return (0, path.name, path.stat().st_mtime)
        return (1, path.name, path.stat().st_mtime)

    return sorted(found, key=sort_key)


def discover_latest_export_dir(
    root: Path,
    *,
    prefer_name: str | None = None,
) -> dict[str, Any]:
    """Pick the latest export directory under root.

    Deterministic order:
    1. Exact prefer_name when present
    2. Highest export-YYYYMMDD-HHMMSS name
    3. Otherwise newest mtime among Signal-image folders
    """
    exports = list_export_dirs(root)
    if not exports:
        raise ExportDiscoveryError(
            "EXPORT_NONE",
            f"no export-* or Signal-image folders under {root.name}",
        )
    selected: Path | None = None
    if prefer_name:
        for path in exports:
            if path.name == prefer_name:
                selected = path
                break
        if selected is None:
            raise ExportDiscoveryError(
                "EXPORT_PREFERRED_MISSING",
                f"preferred export {prefer_name!r} not found under {root.name}",
            )
    else:
        selected = exports[-1]
    image_count = sum(
        1
        for child in selected.iterdir()
        if child.is_file()
        and not child.is_symlink()
        and child.suffix.lower() in IMAGE_SUFFIXES
    )
    return {
        "contract": "automation.signal-drive-transfer.export-discovery/v1",
        "status": "FOUND",
        "root": str(root.resolve()),
        "exportDir": str(selected),
        "exportDirName": selected.name,
        "candidates": [path.name for path in exports],
        "imageCount": image_count,
        "selectionRule": "prefer_name" if prefer_name else "latest_timestamp_or_mtime",
    }
