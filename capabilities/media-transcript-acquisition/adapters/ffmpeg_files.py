"""FFmpeg operations for video analysis with stdout or image files as the only outputs."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


class VideoToolError(ValueError):
    """A file-processing operation could not complete."""


class VideoToolUnavailable(VideoToolError):
    """The required file-processing executable is missing."""


def _run(tool: str, args: list[str], timeout: int, *, cwd: Path | None = None) -> str:
    executable = shutil.which(tool)
    if executable is None:
        raise VideoToolUnavailable(f"{tool} is required on PATH.")
    # CREATE_NO_WINDOW only controls presentation. The commands below control
    # audio output by never selecting a playback program or device.
    windows = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    try:
        result = subprocess.run(
            [executable, *args], stdin=subprocess.DEVNULL, capture_output=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False, cwd=cwd,
            **windows,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise VideoToolError(f"{tool} could not complete video processing.") from None
    if result.returncode:
        # Native diagnostics can include the private source path.
        raise VideoToolError(f"{tool} could not process the recording.")
    return result.stdout


def probe_video(media: Path) -> str:
    return _run("ffprobe", [
        "-v", "error", "-protocol_whitelist", "file", "-select_streams", "v:0",
        "-show_entries", "format=duration:stream=width,height", "-of", "json",
        str(media.resolve()),
    ], timeout=30)


def _write_images(media: Path, output: Path, options: list[str], *,
                  seek: list[str], timeout: int) -> None:
    # Keep percent signs in parent directories out of the image sequence pattern.
    _run("ffmpeg", [
        "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-protocol_whitelist", "file", *seek, "-i", str(media.resolve()),
        "-map", "0:v:0", "-an", *options, "-f", "image2", "./" + output.name,
    ], timeout, cwd=output.parent.resolve())


def extract_frame(media: Path, output: Path, seconds: float) -> None:
    _write_images(media, output, [
        "-frames:v", "1", "-threads", "1", "-update", "1",
    ], seek=["-ss", f"{seconds:.6f}"], timeout=45)


def sample_preview_frames(media: Path, directory: Path, limit: int) -> None:
    _write_images(media, directory / "frame-%03d.jpg", [
        "-vf", "fps=1/8,scale=640:-2", "-frames:v", str(limit),
    ], seek=[], timeout=90)
