#!/usr/bin/env python3
"""Tesseract OCR adapter: subprocess TSV → normalized observation regions."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

_CAP_ROOT = Path(__file__).resolve().parents[2]
if str(_CAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_CAP_ROOT))

from ocr_common import ObservationError, admit_input, empty_observation, finalize_observation

ENGINE = "tesseract"
ENGINE_ID = "tesseract-cli-tsv/v1"
DEFAULT_BINS = (
    "tesseract",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)


def resolve_binary(explicit: str | None = None) -> Path:
    candidates = []
    if explicit:
        candidates.append(explicit)
    env = os.environ.get("AUTOMATION_TESSERACT_BIN")
    if env:
        candidates.append(env)
    which = shutil.which("tesseract")
    if which:
        candidates.append(which)
    candidates.extend(DEFAULT_BINS[1:])
    for raw in candidates:
        path = Path(raw)
        if path.is_file():
            return path
    raise ObservationError("ENGINE_UNAVAILABLE", "tesseract binary not found")


def version_of(binary: Path) -> str | None:
    try:
        proc = subprocess.run(
            [str(binary), "--version"],
            check=False, text=True, capture_output=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    line = (proc.stdout or proc.stderr or "").splitlines()
    return line[0].strip() if line else None


def parse_tsv(payload: str) -> list[dict]:
    lines = payload.splitlines()
    if not lines:
        return []
    header = lines[0].split("\t")
    required = {"level", "left", "top", "width", "height", "conf", "text"}
    if not required.issubset(set(header)):
        raise ObservationError("OCR_FAILED", "unexpected TSV header")
    index = {name: header.index(name) for name in required}
    regions = []
    for line in lines[1:]:
        if not line.strip():
            continue
        cols = line.split("\t")
        if len(cols) <= max(index.values()):
            continue
        try:
            level = int(cols[index["level"]])
            left = int(cols[index["left"]])
            top = int(cols[index["top"]])
            width = int(cols[index["width"]])
            height = int(cols[index["height"]])
            conf_raw = cols[index["conf"]]
            text = cols[index["text"]]
        except (ValueError, IndexError):
            continue
        if level != 5 or width < 1 or height < 1:
            continue
        if conf_raw in {"-1", ""}:
            continue
        conf = max(0.0, min(1.0, float(conf_raw) / 100.0))
        if not text.strip():
            continue
        regions.append({
            "text": text,
            "confidence": conf,
            "bbox": {"x": left, "y": top, "width": width, "height": height},
            "provenance": ENGINE_ID,
        })
    return regions


def recognize(
    image: Path,
    *,
    binary: str | None = None,
    lang: str = "eng",
    timeout_sec: float = 60.0,
    dpi_scale: float = 1.0,
    privacy: str = "UNCLASSIFIED",
) -> dict:
    started = time.perf_counter()
    digest, width, height = admit_input(image)
    try:
        tess = resolve_binary(binary)
    except ObservationError as error:
        return empty_observation(
            status=error.status,
            engine=ENGINE,
            engine_id=ENGINE_ID,
            input_sha256=digest,
            width=width,
            height=height,
            dpi_scale=dpi_scale,
            privacy=privacy,
            errors=[str(error)],
        )
    if not re.fullmatch(r"[A-Za-z0-9_+-]{2,32}", lang):
        return empty_observation(
            status="INVALID_INPUT",
            engine=ENGINE,
            engine_id=ENGINE_ID,
            input_sha256=digest,
            width=width,
            height=height,
            dpi_scale=dpi_scale,
            privacy=privacy,
            engine_version=version_of(tess),
            errors=["invalid language"],
        )
    base = empty_observation(
        status="OK",
        engine=ENGINE,
        engine_id=ENGINE_ID,
        input_sha256=digest,
        width=width,
        height=height,
        dpi_scale=dpi_scale,
        privacy=privacy,
        engine_version=version_of(tess),
        device="cpu",
    )
    try:
        proc = subprocess.run(
            [str(tess), str(image), "stdout", "-l", lang, "--psm", "6", "tsv"],
            check=False, text=True, capture_output=True, timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return empty_observation(
            status="TIMEOUT",
            engine=ENGINE,
            engine_id=ENGINE_ID,
            input_sha256=digest,
            width=width,
            height=height,
            dpi_scale=dpi_scale,
            privacy=privacy,
            engine_version=base["engine_version"],
            device="cpu",
            errors=["tesseract timeout"],
            latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
        )
    except OSError as error:
        return empty_observation(
            status="ENGINE_UNAVAILABLE",
            engine=ENGINE,
            engine_id=ENGINE_ID,
            input_sha256=digest,
            width=width,
            height=height,
            dpi_scale=dpi_scale,
            privacy=privacy,
            errors=[f"tesseract launch failed: {error}"],
        )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "tesseract failed").strip().splitlines()
        return empty_observation(
            status="OCR_FAILED",
            engine=ENGINE,
            engine_id=ENGINE_ID,
            input_sha256=digest,
            width=width,
            height=height,
            dpi_scale=dpi_scale,
            privacy=privacy,
            engine_version=base["engine_version"],
            device="cpu",
            errors=[detail[-1][:400] if detail else "tesseract failed"],
            latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
        )
    try:
        regions = parse_tsv(proc.stdout or "")
    except ObservationError as error:
        return empty_observation(
            status=error.status,
            engine=ENGINE,
            engine_id=ENGINE_ID,
            input_sha256=digest,
            width=width,
            height=height,
            dpi_scale=dpi_scale,
            privacy=privacy,
            engine_version=base["engine_version"],
            device="cpu",
            errors=[str(error)],
            latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
        )
    return finalize_observation(base, regions, started=started)
