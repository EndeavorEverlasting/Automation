"""Optional yt-dlp acquisition adapter. No credentials, browser profiles or anti-bot bypass."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from acquire import AcquisitionError


def download_media(url: str, directory: Path) -> tuple[Path | None, Path | None]:
    binary = shutil.which("yt-dlp")
    if not binary:
        raise AcquisitionError("ADAPTER_UNAVAILABLE")
    directory.mkdir(parents=True, exist_ok=True)
    command = [binary, "--ignore-config", "--no-playlist", "--no-progress", "--no-warnings",
               "--retries", "1", "--fragment-retries", "1", "--socket-timeout", "15",
               "--max-filesize", "250M", "--write-subs", "--write-auto-subs",
               "--sub-langs", "en", "--sub-format", "vtt", "-f", "b[height<=720]/best",
               "-o", str(directory / "source.%(ext)s"), url]
    try:
        result = subprocess.run(command, capture_output=True, timeout=180, check=False)
    except subprocess.TimeoutExpired:
        raise AcquisitionError("PROVIDER_TIMEOUT") from None
    except OSError:
        raise AcquisitionError("ADAPTER_UNAVAILABLE") from None
    if result.returncode:
        # Do not persist or return provider stderr: it may expose private state.
        raise AcquisitionError("PROVIDER_BLOCKED_OR_ERROR")
    media = next((p for p in sorted(directory.glob("source.*")) if p.suffix.lower() in {".mp4", ".webm", ".mkv", ".mov"}), None)
    captions = next(iter(sorted(directory.glob("source.*.vtt"))), None)
    if not media and not captions:
        raise AcquisitionError("NO_MEDIA_OR_CAPTIONS")
    return media, captions
