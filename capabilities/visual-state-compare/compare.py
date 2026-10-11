#!/usr/bin/env python3
"""Deterministic, local-only visual-state comparison (no semantic or click claims)."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import warnings
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageDraw, ImageStat, UnidentifiedImageError
except ImportError:
    Image = None


CONTRACT = "automation.visual-state-comparison/v1"
ENGINE = "pillow-pixel-diff/v1"
MAX_PIXELS = 20_000_000


class ComparisonError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_mask(value: str) -> tuple[int, int, int, int]:
    try:
        parts = tuple(int(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("mask must be x,y,width,height integers") from exc
    if len(parts) != 4 or any(part < 0 for part in parts[:2]) or any(part <= 0 for part in parts[2:]):
        raise argparse.ArgumentTypeError("mask must be nonnegative x,y and positive width,height")
    return parts


def load_png(path: Path):
    if Image is None:
        raise ComparisonError("ENGINE_UNAVAILABLE")
    try:
        Image.MAX_IMAGE_PIXELS = MAX_PIXELS
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as original:
                if original.format != "PNG":
                    raise ComparisonError("INVALID_INPUT")
                original.load()
                rgba = original.convert("RGBA")
                background = Image.new("RGBA", original.size, (255, 255, 255, 255))
                return Image.alpha_composite(background, rgba).convert("RGB")
    except ComparisonError:
        raise
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ComparisonError("INVALID_INPUT") from exc


def compare(before_path: Path, after_path: Path, masks: list[tuple[int, int, int, int]],
            pixel_threshold: int, max_diff_ratio: float, diff_out: Path | None) -> dict:
    before = load_png(before_path)
    after = load_png(after_path)
    if before.size != after.size:
        raise ComparisonError("INCOMPARABLE_GEOMETRY")

    width, height = before.size
    for x, y, w, h in masks:
        if x + w > width or y + h > height:
            raise ComparisonError("INVALID_MASK")

    channels = ImageChops.difference(before, after).split()
    magnitude = ImageChops.lighter(channels[0], ImageChops.lighter(channels[1], channels[2]))
    diff = magnitude.point(lambda value: 255 if value > pixel_threshold else 0)
    coverage = Image.new("L", (width, height), 255)
    mask_draw = ImageDraw.Draw(diff)
    coverage_draw = ImageDraw.Draw(coverage)
    for x, y, w, h in masks:
        bounds = (x, y, x + w - 1, y + h - 1)
        mask_draw.rectangle(bounds, fill=0)
        coverage_draw.rectangle(bounds, fill=0)

    comparable = round(ImageStat.Stat(coverage).sum[0] / 255)
    if comparable <= 0:
        raise ComparisonError("INVALID_MASK")

    changed = round(ImageStat.Stat(diff).sum[0] / 255)
    ratio = changed / comparable
    bounds = diff.getbbox()
    changed_bbox = None
    if bounds:
        left, top, right, bottom = bounds
        changed_bbox = {"x": left, "y": top, "width": right - left, "height": bottom - top}

    if diff_out is not None:
        diff.save(diff_out, format="PNG")

    status = ("NO_CHANGE" if changed == 0 else
              "TOLERATED_CHANGE" if ratio <= max_diff_ratio else "CHANGED")
    return {
        "contract": CONTRACT,
        "engine": ENGINE,
        "status": status,
        "before_sha256": sha256_file(before_path),
        "after_sha256": sha256_file(after_path),
        "width": width,
        "height": height,
        "comparable_pixels": comparable,
        "changed_pixels": changed,
        "change_ratio": ratio,
        "changed_bbox": changed_bbox,
        "pixel_threshold": pixel_threshold,
        "max_diff_ratio": max_diff_ratio,
        "masked_regions": [
            {"x": x, "y": y, "width": w, "height": h} for x, y, w, h in masks
        ],
        "semantic_verdict": "NOT_EVALUATED",
        "capture_provenance": "NOT_PROVIDED",
        "proof_ceiling": "OFFLINE_DETERMINISTIC_PIXEL_COMPARISON",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path, help="Local JSON evidence output")
    parser.add_argument("--diff-out", type=Path, help="Optional local black/white change mask PNG")
    parser.add_argument("--mask", type=parse_mask, action="append", default=[],
                        help="Repeatable ignored rectangle x,y,width,height")
    parser.add_argument("--pixel-threshold", type=int, default=0)
    parser.add_argument("--max-diff-ratio", type=float, default=0.0)
    args = parser.parse_args(argv)
    if not 0 <= args.pixel_threshold <= 255 or not 0 <= args.max_diff_ratio <= 1:
        parser.error("threshold must be 0..255 and max-diff-ratio must be 0..1")
    try:
        receipt = compare(args.before, args.after, args.mask, args.pixel_threshold,
                          args.max_diff_ratio, args.diff_out)
    except ComparisonError as exc:
        receipt = {
            "contract": CONTRACT, "engine": ENGINE, "status": exc.code,
            "semantic_verdict": "NOT_EVALUATED", "proof_ceiling": "NO_COMPARISON_PROOF"
        }
    # Deliberately exclude local filenames, screenshot pixels and credentials.
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "receipt": "WRITTEN"}))
    return 0 if receipt["status"] in {"NO_CHANGE", "TOLERATED_CHANGE"} else (
        1 if receipt["status"] == "CHANGED" else 2
    )


if __name__ == "__main__":
    sys.exit(main())
