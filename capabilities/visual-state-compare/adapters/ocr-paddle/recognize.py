#!/usr/bin/env python3
"""PaddleOCR adapter: optional isolated runtime → normalized observation regions.

Does not download weights. Network is disabled for ordinary inference when the
library honors the offline flags set here. ENGINE_UNAVAILABLE when PaddleOCR
is not installed in the active interpreter.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

# Capability root for shared helpers (consumer uses vision_cli, not this module).
import sys

_CAP_ROOT = Path(__file__).resolve().parents[2]
if str(_CAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_CAP_ROOT))

from ocr_common import ObservationError, admit_input, empty_observation, finalize_observation

ENGINE = "paddle"
ENGINE_ID = "paddleocr-ppocr/v1"


def _offline_env() -> None:
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    os.environ.setdefault("FLAGS_use_mkldnn", "0")
    # Discourage silent hub downloads in common paddle stacks.
    os.environ.setdefault("HUB_HOME", os.environ.get("AUTOMATION_PADDLE_HUB", ""))


def _load_engine():
    _offline_env()
    try:
        from paddleocr import PaddleOCR  # type: ignore
    except ImportError as error:
        raise ObservationError(
            "ENGINE_UNAVAILABLE",
            f"paddleocr import failed: {error}",
        ) from error
    return PaddleOCR


def _normalize_result(raw) -> list[dict]:
    """Accept classic PaddleOCR list[[[box], (text, conf)], ...] layouts."""
    regions = []
    if raw is None:
        return regions
    pages = raw if isinstance(raw, list) else [raw]
    for page in pages:
        if not page:
            continue
        lines = page if isinstance(page, list) else getattr(page, "ocr", None) or []
        if isinstance(page, dict) and "ocr" in page:
            lines = page["ocr"]
        for item in lines or []:
            try:
                if isinstance(item, dict):
                    text = str(item.get("text") or item.get("transcription") or "")
                    conf = float(item.get("confidence") or item.get("score") or 0.0)
                    box = item.get("box") or item.get("bbox") or item.get("points")
                else:
                    box, payload = item[0], item[1]
                    if isinstance(payload, (list, tuple)):
                        text, conf = str(payload[0]), float(payload[1])
                    else:
                        text, conf = str(payload), 0.0
                if not text.strip() or box is None:
                    continue
                xs = [float(pt[0]) for pt in box]
                ys = [float(pt[1]) for pt in box]
                left, top = int(min(xs)), int(min(ys))
                right, bottom = int(max(xs)), int(max(ys))
                width, height = max(1, right - left), max(1, bottom - top)
                # Paddle conf is often already 0..1; clamp if given as percent.
                if conf > 1.0:
                    conf = conf / 100.0
                regions.append({
                    "text": text,
                    "confidence": max(0.0, min(1.0, conf)),
                    "bbox": {"x": left, "y": top, "width": width, "height": height},
                    "provenance": ENGINE_ID,
                })
            except (TypeError, ValueError, IndexError, KeyError):
                continue
    return regions


def recognize_via_interpreter(
    image: Path,
    python_exe: Path,
    *,
    lang: str = "en",
    timeout_sec: float = 120.0,
    dpi_scale: float = 1.0,
    privacy: str = "UNCLASSIFIED",
    device: str = "cpu",
) -> dict:
    """Run paddle recognition inside an isolated interpreter (separate venv)."""
    import json
    import subprocess
    import tempfile

    started = time.perf_counter()
    digest, width, height = admit_input(image)
    worker = Path(__file__).with_name("worker.py")
    if not python_exe.is_file() or not worker.is_file():
        return empty_observation(
            status="ENGINE_UNAVAILABLE",
            engine=ENGINE,
            engine_id=ENGINE_ID,
            input_sha256=digest,
            width=width,
            height=height,
            dpi_scale=dpi_scale,
            privacy=privacy,
            device=device,
            errors=["paddle interpreter or worker missing"],
        )
    with tempfile.TemporaryDirectory(prefix="automation-paddle-") as tmp:
        out = Path(tmp) / "observation.json"
        try:
            proc = subprocess.run(
                [
                    str(python_exe), str(worker),
                    "--input", str(image),
                    "--output", str(out),
                    "--lang", lang,
                    "--timeout-sec", str(timeout_sec),
                    "--dpi-scale", str(dpi_scale),
                    "--privacy", privacy,
                    "--device", device,
                ],
                check=False, text=True, capture_output=True, timeout=timeout_sec + 30,
                env={**os.environ, "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "True"},
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
                device=device,
                errors=["paddle worker timeout"],
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
                device=device,
                errors=[f"paddle worker launch failed: {error}"],
            )
        if not out.is_file():
            detail = (proc.stderr or proc.stdout or "no receipt").strip().splitlines()
            return empty_observation(
                status="OCR_FAILED" if proc.returncode else "ENGINE_UNAVAILABLE",
                engine=ENGINE,
                engine_id=ENGINE_ID,
                input_sha256=digest,
                width=width,
                height=height,
                dpi_scale=dpi_scale,
                privacy=privacy,
                device=device,
                errors=[detail[-1][:400] if detail else "paddle worker produced no receipt"],
                latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
            )
        return json.loads(out.read_text(encoding="utf-8"))


def recognize(
    image: Path,
    *,
    lang: str = "en",
    timeout_sec: float = 120.0,
    dpi_scale: float = 1.0,
    privacy: str = "UNCLASSIFIED",
    device: str = "cpu",
    python_exe: str | None = None,
) -> dict:
    started = time.perf_counter()
    digest, width, height = admit_input(image)
    isolated = python_exe or os.environ.get("AUTOMATION_PADDLE_PYTHON")
    if isolated:
        return recognize_via_interpreter(
            image,
            Path(isolated),
            lang=lang,
            timeout_sec=timeout_sec,
            dpi_scale=dpi_scale,
            privacy=privacy,
            device=device,
        )
    try:
        paddle_cls = _load_engine()
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
            device=device,
            errors=[str(error)],
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
        device=device,
        engine_version=getattr(paddle_cls, "__module__", "paddleocr"),
    )
    # Soft timeout: PaddleOCR has no native timeout; bound wall clock after call.
    try:
        # Prefer modern API kwargs; fall back for older pins.
        try:
            engine = paddle_cls(lang=lang, use_angle_cls=True, show_log=False)
        except TypeError:
            engine = paddle_cls(lang=lang)
        raw = engine.ocr(str(image))
    except Exception as error:  # donor stack raises many types
        elapsed = time.perf_counter() - started
        status = "TIMEOUT" if elapsed >= timeout_sec else "OCR_FAILED"
        return empty_observation(
            status=status,
            engine=ENGINE,
            engine_id=ENGINE_ID,
            input_sha256=digest,
            width=width,
            height=height,
            dpi_scale=dpi_scale,
            privacy=privacy,
            device=device,
            errors=[f"{type(error).__name__}: {error}"[:400]],
            latency_ms=round(elapsed * 1000.0, 3),
        )
    elapsed = time.perf_counter() - started
    if elapsed > timeout_sec:
        return empty_observation(
            status="TIMEOUT",
            engine=ENGINE,
            engine_id=ENGINE_ID,
            input_sha256=digest,
            width=width,
            height=height,
            dpi_scale=dpi_scale,
            privacy=privacy,
            device=device,
            errors=["paddle ocr exceeded timeout"],
            latency_ms=round(elapsed * 1000.0, 3),
        )
    return finalize_observation(base, _normalize_result(raw), started=started)
