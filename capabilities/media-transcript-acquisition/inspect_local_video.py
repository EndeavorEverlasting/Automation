#!/usr/bin/env python3
"""Fingerprint a local installer recording and extract selected review frames."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile

from social_insights import sha256_file


REPOSITORY = Path(__file__).resolve().parents[2]
MAX_FRAMES = 24


def run_tool(name: str, arguments: list[str], timeout: int) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise ValueError(f"{name} is required on PATH.")
    try:
        result = subprocess.run(
            [executable, *arguments], capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError(f"{name} could not finish within the local review run.") from error
    if result.returncode:
        # Native stderr can contain the private source path.
        raise ValueError(f"{name} could not process the recording.")
    return result.stdout


def inspect(source: Path, output: Path, timestamps: list[float]) -> None:
    source = source.resolve()
    output = output.resolve()
    if not source.is_file() or source.suffix.lower() not in {".mp4", ".mov", ".m4v"}:
        raise ValueError("Provide a readable local MP4, MOV, or M4V recording.")
    if output.is_relative_to(REPOSITORY) or output.exists():
        raise ValueError("Choose a new evidence directory outside the Automation checkout.")
    if len(timestamps) > MAX_FRAMES or any(not math.isfinite(ts) or ts < 0 for ts in timestamps):
        raise ValueError("Specify up to 24 finite, non-negative timestamps.")

    original = source.stat()
    digest = sha256_file(source)
    probe = json.loads(run_tool("ffprobe", [
        "-v", "error", "-protocol_whitelist", "file", "-select_streams", "v:0",
        "-show_entries", "format=duration:stream=width,height", "-of", "json", str(source),
    ], timeout=30))
    try:
        duration = float(probe["format"]["duration"])
        video = probe["streams"][0]
        width, height = video["width"], video["height"]
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ValueError("No finite-duration video stream was found.") from error
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("No finite-duration video stream was found.")
    if any(ts >= duration for ts in timestamps):
        raise ValueError("Each timestamp must be earlier than the end of the recording.")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".video-review-", dir=output.parent) as temp:
        stage = Path(temp) / "evidence"
        stage.mkdir()
        frames = []
        for index, seconds in enumerate(sorted(set(timestamps)), 1):
            frame = stage / f"frame-{index:02}.png"
            run_tool("ffmpeg", [
                "-nostdin", "-hide_banner", "-loglevel", "error", "-protocol_whitelist", "file",
                "-ss", f"{seconds:.6f}", "-i", str(source), "-map", "0:v:0",
                "-frames:v", "1", "-threads", "1", "-update", "1", str(frame),
            ], timeout=45)
            if not frame.is_file() or not frame.stat().st_size:
                raise ValueError(f"No frame was decoded near {seconds:g} seconds.")
            frames.append({"requested_seconds": seconds, "file": frame.name, "sha256": sha256_file(frame)})
        current = source.stat()
        if (original.st_size, original.st_mtime_ns) != (current.st_size, current.st_mtime_ns):
            raise ValueError("The source changed during inspection. Retry against a stable copy.")
        packet = {
            "schema": "automation.local-video-review/v1",
            "source": {"bytes": original.st_size, "sha256": digest, "duration_seconds": duration,
                       "width": width, "height": height},
            "frames": frames,
            "proof": "MEDIA_FINGERPRINT_AND_REQUESTED_FRAMES_ONLY",
        }
        (stage / "source.json").write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
        stage.rename(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True, help="New private directory outside the checkout")
    parser.add_argument("--at", type=float, action="append", default=[], help="Frame seek in seconds. Repeat as needed.")
    args = parser.parse_args()
    try:
        inspect(args.input, args.out_dir, args.at)
    except ValueError as error:
        parser.exit(2, f"Video review unavailable: {error}\n")
    except OSError:
        parser.exit(2, "Video review unavailable: could not read source or write private evidence.\n")
    print("Private video evidence written. Full playback and decision mapping remain separate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
