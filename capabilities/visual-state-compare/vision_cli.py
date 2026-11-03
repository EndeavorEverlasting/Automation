#!/usr/bin/env python3
"""Stable Automation visual observation CLI. Consumers do not import donor OCR engines."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ocr_common import ObservationError, admit_output, empty_observation  # noqa: E402


def _load_tesseract():
    from importlib.util import module_from_spec, spec_from_file_location

    path = ROOT / "adapters" / "ocr-tesseract" / "recognize.py"
    spec = spec_from_file_location("ocr_tesseract_recognize", path)
    if spec is None or spec.loader is None:
        raise ObservationError("ENGINE_UNAVAILABLE", "tesseract adapter missing")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_paddle():
    from importlib.util import module_from_spec, spec_from_file_location

    path = ROOT / "adapters" / "ocr-paddle" / "recognize.py"
    spec = spec_from_file_location("ocr_paddle_recognize", path)
    if spec is None or spec.loader is None:
        raise ObservationError("ENGINE_UNAVAILABLE", "paddle adapter missing")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def analyze(
    image: Path,
    *,
    engine: str,
    timeout_sec: float,
    dpi_scale: float,
    privacy: str,
    tesseract_bin: str | None,
    lang: str,
    paddle_python: str | None = None,
) -> dict:
    if engine == "tesseract":
        return _load_tesseract().recognize(
            image, binary=tesseract_bin, lang=lang if lang != "auto" else "eng",
            timeout_sec=timeout_sec, dpi_scale=dpi_scale, privacy=privacy,
        )
    if engine == "paddle":
        paddle_lang = "en" if lang in {"auto", "eng"} else lang
        return _load_paddle().recognize(
            image, lang=paddle_lang, timeout_sec=timeout_sec,
            dpi_scale=dpi_scale, privacy=privacy, python_exe=paddle_python,
        )
    # auto: prefer paddle when importable or isolated interpreter configured
    paddle = _load_paddle().recognize(
        image,
        lang="en" if lang in {"auto", "eng"} else lang,
        timeout_sec=timeout_sec,
        dpi_scale=dpi_scale,
        privacy=privacy,
        python_exe=paddle_python,
    )
    if paddle["status"] != "ENGINE_UNAVAILABLE":
        paddle["engine"] = "auto"
        return paddle
    tess = _load_tesseract().recognize(
        image,
        binary=tesseract_bin,
        lang=lang if lang != "auto" else "eng",
        timeout_sec=timeout_sec,
        dpi_scale=dpi_scale,
        privacy=privacy,
    )
    tess["engine"] = "auto"
    if tess["status"] == "ENGINE_UNAVAILABLE":
        return empty_observation(
            status="ENGINE_UNAVAILABLE",
            engine="auto",
            engine_id="vision-cli-auto/v1",
            input_sha256=tess.get("input_sha256", "0" * 64),
            width=tess.get("width", 1),
            height=tess.get("height", 1),
            dpi_scale=dpi_scale,
            privacy=privacy,
            errors=["auto: paddle and tesseract unavailable"],
        )
    return tess


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Local visual OCR observation. No click/action authority."
    )
    parser.add_argument("command", choices=["analyze"], help="analyze a PNG screenshot")
    parser.add_argument("--input", required=True, type=Path, help="PNG path")
    parser.add_argument("--output", required=True, type=Path, help="observation JSON path")
    parser.add_argument("--engine", choices=["auto", "tesseract", "paddle"], default="auto")
    parser.add_argument("--timeout-sec", type=float, default=60.0)
    parser.add_argument("--dpi-scale", type=float, default=1.0)
    parser.add_argument(
        "--privacy",
        choices=["SYNTHETIC_PUBLIC", "PRIVATE_LOCAL", "UNCLASSIFIED"],
        default="UNCLASSIFIED",
    )
    parser.add_argument("--tesseract-bin", default=None)
    parser.add_argument(
        "--paddle-python",
        default=None,
        help="Isolated interpreter with paddleocr (or set AUTOMATION_PADDLE_PYTHON)",
    )
    parser.add_argument("--lang", default="auto")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.timeout_sec <= 0 or args.dpi_scale <= 0:
            raise ObservationError("INVALID_INPUT", "timeout/dpi must be positive")
        admit_output(args.output, allow_overwrite=args.overwrite)
        receipt = analyze(
            args.input.resolve(),
            engine=args.engine,
            timeout_sec=args.timeout_sec,
            dpi_scale=args.dpi_scale,
            privacy=args.privacy,
            tesseract_bin=args.tesseract_bin,
            lang=args.lang,
            paddle_python=args.paddle_python,
        )
    except ObservationError as error:
        receipt = empty_observation(
            status=error.status,
            engine=args.engine,
            engine_id="vision-cli/v1",
            errors=[str(error)],
            dpi_scale=max(args.dpi_scale, 1e-9),
            privacy=args.privacy,
        )
        try:
            admit_output(args.output, allow_overwrite=args.overwrite)
            args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        except ObservationError:
            print(json.dumps(receipt, indent=2))
            return 2
        return 2

    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"contract": receipt["contract"], "status": receipt["status"],
                      "engine_id": receipt["engine_id"], "regions": len(receipt["regions"]),
                      "output": str(args.output)}, indent=2))
    if receipt["status"] in {"OK", "NO_TEXT"}:
        return 0
    if receipt["status"] == "ENGINE_UNAVAILABLE":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
