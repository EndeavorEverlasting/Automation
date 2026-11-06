#!/usr/bin/env python3
"""Deliver authorized social-media video/audio artifacts to a local host directory.

A provider URL is untrusted input. No cookies, login, DRM bypass, remote API
upload, scheduler mutation or shell invocation is performed by this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from acquire import AcquisitionError
from social_insights import normalize_source, sha256_file

CONTRACT = "automation.media-artifact-delivery/v1"
MEDIA_EXTENSIONS = frozenset({".mp4", ".webm", ".mkv", ".mov", ".m4a", ".mp3", ".opus", ".ogg"})
VIDEO_EXTENSIONS = frozenset({".mp4", ".webm", ".mkv", ".mov"})
AUDIO_EXTENSIONS = frozenset({".mp3", ".m4a", ".opus", ".ogg"})
MAX_MB_LIMIT = 2048


class DeliveryError(Exception):
    def __init__(self, status: str):
        self.status = status
        super().__init__(status)


def checked_root(path: Path) -> Path:
    """Do not place downloaded/untrusted media or private receipts in public Git."""
    resolved = path.expanduser().resolve()
    repo_root = Path(__file__).resolve().parents[2]
    if resolved == repo_root or resolved.is_relative_to(repo_root):
        raise DeliveryError("OUTPUT_INSIDE_REPOSITORY")
    if resolved.exists() and not resolved.is_dir():
        raise DeliveryError("INVALID_OUTPUT_DIRECTORY")
    return resolved


def run_process(argv: list[str], timeout: int) -> None:
    """No shell, stdin or inherited console; discard untrusted provider output."""
    opts = {}
    if os.name == "nt":
        opts["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        info.wShowWindow = subprocess.SW_HIDE
        opts["startupinfo"] = info
    try:
        p = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, shell=False, timeout=timeout,
                           check=False, **opts)
    except subprocess.TimeoutExpired:
        raise DeliveryError("PROCESS_TIMEOUT") from None
    except OSError:
        raise DeliveryError("PROCESS_LAUNCH_FAILED") from None
    if p.returncode != 0:
        raise DeliveryError("PROVIDER_OR_PROCESS_ERROR")


def find_media(folder: Path, extensions: frozenset[str]) -> Path:
    # Downloader must not be able to redirect the delivered artifact via a symlink.
    matches = [p for p in folder.iterdir()
               if p.is_file() and not p.is_symlink() and p.name.startswith("source.")
               and p.suffix.lower() in extensions]
    if len(matches) != 1:
        raise DeliveryError("MEDIA_NOT_PRODUCED")
    return matches[0]


def describe_file(path: Path, role: str, max_bytes: int) -> dict:
    if path.is_symlink() or not path.is_file():
        raise DeliveryError("INVALID_ARTIFACT")
    size = path.stat().st_size
    if size == 0:
        raise DeliveryError("EMPTY_ARTIFACT")
    if size > max_bytes:
        raise DeliveryError("ARTIFACT_TOO_LARGE")
    return {"role": role, "file": path.name, "bytes": size, "sha256": sha256_file(path)}


def private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try:
            path.chmod(0o700)
        except OSError:
            pass


def write_receipt(path: Path, packet: dict) -> None:
    # Write before success publication; avoid leaving a partially written receipt.
    tmp = path.with_name("." + path.name + ".tmp")
    try:
        tmp.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def capture(url: str, mode: str, output_dir: Path, max_mb: int = 500,
            timeout: int = 300) -> tuple[dict, Path]:
    if mode not in {"video", "audio", "hybrid"}:
        raise DeliveryError("INVALID_MODE")
    if not 1 <= max_mb <= MAX_MB_LIMIT or not 10 <= timeout <= 900:
        raise DeliveryError("INVALID_LIMIT")
    try:
        provider, canonical_url = normalize_source(url)
    except AcquisitionError as exc:
        raise DeliveryError(exc.status) from None
    root = checked_root(output_dir)
    delivery_id = uuid.uuid4().hex
    source_id = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:16]
    tool = shutil.which("yt-dlp")
    # Even video-only output can need FFmpeg to merge separately streamed audio/video.
    ffmpeg = shutil.which("ffmpeg")
    private_directory(root)
    packet = {"contract": CONTRACT,
              "status": "BLOCKED",
              "delivery_id": delivery_id,
              "source": {"provider": provider, "url": canonical_url, "id_sha256_prefix": source_id},
              "mode": mode, "artifacts": [], "failure": None,
              "proof_ceiling": "NO_ARTIFACT_DELIVERED"}
    failpath = root / ("failed-" + delivery_id + ".receipt.json")
    if not tool:
        packet["failure"] = "YTDLP_UNAVAILABLE"
        write_receipt(failpath, packet)
        return packet, failpath
    if not ffmpeg:
        packet["failure"] = "FFMPEG_UNAVAILABLE"
        write_receipt(failpath, packet)
        return packet, failpath

    stage = Path(tempfile.mkdtemp(prefix=".media-acquire-", dir=root))
    try:
        private_directory(stage)
        command = [
            tool, "--ignore-config", "--no-playlist", "--no-progress", "--no-warnings",
            "--no-remote-components", "--no-part", "--no-overwrites", "--restrict-filenames",
            "--retries", "1", "--fragment-retries", "1", "--socket-timeout", "15",
            "--max-filesize", str(max_mb) + "M",
            "-o", str(stage / "source.%(ext)s"),
        ]
        if mode == "audio":
            command += ["-x", "--audio-format", "mp3", "-f", "bestaudio/best"]
        else:
            command += ["-f", "bv*+ba/b", "--merge-output-format", "mp4"]
        # Final argument is the strictly normalized, allowlisted HTTPS URL.
        command.append(canonical_url)
        run_process(command, timeout)
        max_bytes = max_mb * 1024 * 1024
        if mode == "audio":
            source = find_media(stage, AUDIO_EXTENSIONS)
            target = stage / ("audio" + source.suffix.lower())
            source.rename(target)
            packet["artifacts"].append(describe_file(target, "audio", max_bytes))
        else:
            source = find_media(stage, VIDEO_EXTENSIONS)
            target = stage / ("video" + source.suffix.lower())
            source.rename(target)
            packet["artifacts"].append(describe_file(target, "video", max_bytes))
            if mode == "hybrid":
                audio = stage / "audio.mp3"
                try:
                    run_process([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                                 "-y", "-i", str(target), "-vn", "-codec:a",
                                 "libmp3lame", "-q:a", "2", str(audio)], timeout)
                except DeliveryError as exc:
                    raise DeliveryError("AUDIO_EXTRACTION_FAILED") from exc
                packet["artifacts"].append(describe_file(audio, "audio", max_bytes))
        packet["status"] = "DELIVERED"
        packet["proof_ceiling"] = "LOCAL_FILES_HASHED_NOT_PROVIDER_CERTIFIED"
        packet["failure"] = None
        write_receipt(stage / "receipt.json", packet)
        destination = root / ("media-" + source_id + "-" + delivery_id[:8])
        os.replace(stage, destination)
        return packet, destination / "receipt.json"
    except DeliveryError as exc:
        packet.update(status="BLOCKED", failure=exc.status,
                      artifacts=[], proof_ceiling="NO_ARTIFACT_DELIVERED")
        write_receipt(failpath, packet)
        return packet, failpath
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Authorized public HTTPS social-media URL")
    parser.add_argument("--mode", choices=["video", "audio", "hybrid"], default="video")
    parser.add_argument("--output-dir", required=True, type=Path,
                        help="Private host directory OUTSIDE any source repository")
    parser.add_argument("--max-mb", type=int, default=500)
    parser.add_argument("--timeout", type=int, default=300, help="Seconds, 10-900")
    a = parser.parse_args(argv)
    try:
        packet, receipt = capture(a.url, a.mode, a.output_dir, a.max_mb, a.timeout)
    except DeliveryError as exc:
        print(json.dumps({"status": "BLOCKED", "failure": exc.status}))
        return 2
    print(json.dumps({"status": packet["status"], "failure": packet["failure"],
                      "receipt": str(receipt)}))
    return 0 if packet["status"] == "DELIVERED" else 2


if __name__ == "__main__":
    sys.exit(main())
