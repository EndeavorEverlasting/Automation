#!/usr/bin/env python3
"""Shared helpers for normalized visual OCR observations (no donor imports)."""
from __future__ import annotations

import hashlib
import struct
import time
from pathlib import Path
from typing import Any

CONTRACT = "automation.visual-observation/v1"
MAX_PIXELS = 20_000_000


class ObservationError(Exception):
    def __init__(self, status: str, detail: str | None = None):
        self.status = status
        self.detail = detail
        super().__init__(status if detail is None else f"{status}: {detail}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as source:
        header = source.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ObservationError("INVALID_INPUT", "not a PNG")
    width, height = struct.unpack(">II", header[16:24])
    if width < 1 or height < 1 or width * height > MAX_PIXELS:
        raise ObservationError("INVALID_INPUT", "unsupported dimensions")
    return int(width), int(height)


def admit_input(path: Path) -> tuple[str, int, int]:
    if not path.is_file() or path.suffix.lower() != ".png":
        raise ObservationError("INVALID_INPUT", "PNG required")
    return sha256_file(path), *png_dimensions(path)


def admit_output(path: Path, *, allow_overwrite: bool = False) -> None:
    if path.exists() and not allow_overwrite:
        raise ObservationError("OUTPUT_DENIED", "output exists")
    if not path.parent.is_dir():
        raise ObservationError("OUTPUT_DENIED", "output directory missing")


def empty_observation(
    *,
    status: str,
    engine: str,
    engine_id: str,
    input_sha256: str = "0" * 64,
    width: int = 1,
    height: int = 1,
    dpi_scale: float = 1.0,
    privacy: str = "UNCLASSIFIED",
    errors: list[str] | None = None,
    engine_version: str | None = None,
    engine_commit: str | None = None,
    model_hash: str | None = None,
    device: str | None = None,
    latency_ms: float | None = None,
) -> dict[str, Any]:
    proof = "OCR_INFERENCE_SMOKE" if status in {"OK", "NO_TEXT"} else (
        "OCR_ENGINE_UNAVAILABLE" if status == "ENGINE_UNAVAILABLE" else "OCR_NO_PROOF"
    )
    return {
        "contract": CONTRACT,
        "status": status,
        "engine": engine if engine in {"tesseract", "paddle", "auto"} else "auto",
        "engine_id": engine_id,
        "engine_version": engine_version,
        "engine_commit": engine_commit,
        "model_hash": model_hash,
        "device": device,
        "input_sha256": input_sha256,
        "width": width,
        "height": height,
        "coordinate_space": "screenshot_pixels",
        "dpi_scale": dpi_scale,
        "privacy_classification": privacy,
        "regions": [],
        "full_text": None,
        "latency_ms": latency_ms,
        "errors": list(errors or ([status] if status not in {"OK", "NO_TEXT"} else [])),
        "semantic_verdict": "NOT_EVALUATED",
        "action_authority": "NONE",
        "proof_ceiling": proof,
    }


def finalize_observation(
    base: dict[str, Any],
    regions: list[dict[str, Any]],
    *,
    started: float,
) -> dict[str, Any]:
    receipt = dict(base)
    cleaned = []
    texts = []
    for region in regions:
        text = str(region.get("text", "")).strip()
        bbox = region["bbox"]
        if not text or bbox["width"] < 1 or bbox["height"] < 1:
            continue
        cleaned.append({
            "text": text,
            "confidence": max(0.0, min(1.0, float(region["confidence"]))),
            "bbox": {
                "x": int(bbox["x"]),
                "y": int(bbox["y"]),
                "width": int(bbox["width"]),
                "height": int(bbox["height"]),
            },
            "provenance": str(region["provenance"]),
        })
        texts.append(text)
    receipt["regions"] = cleaned
    receipt["full_text"] = "\n".join(texts) if texts else None
    receipt["latency_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
    if cleaned:
        receipt["status"] = "OK"
        receipt["errors"] = []
        receipt["proof_ceiling"] = "OCR_INFERENCE_SMOKE"
    else:
        receipt["status"] = "NO_TEXT"
        receipt["errors"] = []
        receipt["proof_ceiling"] = "OCR_INFERENCE_SMOKE"
    return receipt


def character_error_rate(reference: str, hypothesis: str) -> float:
    """Levenshtein CER over unicode code points; empty reference → 0 iff hypothesis empty else 1."""
    ref = list(reference)
    hyp = list(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r_ch in enumerate(ref, start=1):
        curr = [i]
        for j, h_ch in enumerate(hyp, start=1):
            cost = 0 if r_ch == h_ch else 1
            curr.append(min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1] / len(ref)
