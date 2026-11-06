#!/usr/bin/env python3
"""Portable, local-first host UI for authorized social-media artifact capture.

No installer, scheduler, login, cookie import, cloud relay, or background service.
This is an entrypoint over the existing deliver_artifact engine, not a downloader.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from deliver_artifact import CONTRACT, DeliveryError, capture, sha256_file

HOST_CONTRACT = "automation.media-host/v1"
# Receipt roles and extensions are intentionally constrained to this engine's format.
SAFE_NAME = re.compile(r"^(video\.(?:mp4|webm|mkv|mov)|audio\.(?:mp3|m4a|opus|ogg))$")
MODES = ("video", "audio", "hybrid")


def default_output() -> Path:
    """An easy-to-find per-user output location, never inside the Git checkout."""
    return Path.home() / "Downloads" / "Automation-Media"


def child_options() -> dict[str, Any]:
    options: dict[str, Any] = {}
    if sys.platform == "win32":
        options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        info.wShowWindow = subprocess.SW_HIDE
        options["startupinfo"] = info
    return options


def tool_version(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command, shell=False, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=8, check=False, **child_options()
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    # Ignore potentially untrusted stderr. Only report the first version line.
    lines = result.stdout.decode("utf-8", errors="replace").splitlines()
    return lines[0][:160].strip() if lines else None


def doctor() -> dict[str, Any]:
    yt = shutil.which("yt-dlp")
    ff = shutil.which("ffmpeg")
    version = tool_version([yt, "--version"]) if yt else None
    ffversion = tool_version([ff, "-version"]) if ff else None
    supported = sys.version_info >= (3, 11)
    available = bool(yt and version and supported)
    all_modes = bool(available and ff and ffversion)
    return {
        "contract": HOST_CONTRACT,
        "platform": "windows" if sys.platform == "win32" else (
            "linux" if sys.platform.startswith("linux") else sys.platform
        ),
        "python": ".".join(map(str, sys.version_info[:3])),
        "python_supported": supported,
        "yt_dlp": {"available": bool(yt and version), "version": version},
        "ffmpeg": {"available": bool(ff and ffversion), "version": ffversion},
        "ready_modes": list(MODES) if all_modes else (["video"] if available else []),
        "default_output": str(default_output()),
        "action": "READY" if all_modes else "DEPENDENCIES_MISSING",
    }


def verify_receipt(path: Path) -> dict[str, Any]:
    """Check local file integrity, NOT provenance, license, stream quality, or safety."""
    result: dict[str, Any] = {
        "contract": "automation.media-host-verification/v1",
        "status": "FAILED",
        "file_results": [],
        "reason": None,
        "proof_ceiling": "LOCAL_FILE_INTEGRITY_ONLY",
    }
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 64_000:
            raise ValueError("INVALID_RECEIPT")
        packet = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(packet, dict) or packet.get("contract") != CONTRACT:
            raise ValueError("INVALID_RECEIPT")
        if packet.get("status") != "DELIVERED":
            raise ValueError("NOT_A_DELIVERY")
        entries = packet.get("artifacts")
        mode = packet.get("mode")
        expected_roles = (["video"] if mode == "video" else
                          ["audio"] if mode == "audio" else
                          ["video", "audio"] if mode == "hybrid" else None)
        if not isinstance(entries, list) or expected_roles is None or len(entries) != len(expected_roles):
            raise ValueError("INVALID_ARTIFACT_LIST")
        names: set[str] = set()
        for index, (entry, role) in enumerate(zip(entries, expected_roles)):
            if not isinstance(entry, dict):
                raise ValueError("INVALID_ARTIFACT_LIST")
            filename = entry.get("file")
            size = entry.get("bytes")
            digest = entry.get("sha256")
            if (entry.get("role") != role or not isinstance(filename, str)
                or not SAFE_NAME.fullmatch(filename)
                or filename in names or not filename.startswith(role + ".")
                or type(size) is not int or size <= 0
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)):
                raise ValueError("INVALID_ARTIFACT_LIST")
            names.add(filename)
            artifact = path.parent / filename
            valid = bool(artifact.is_file() and not artifact.is_symlink()
                         and artifact.stat().st_size == size
                         and sha256_file(artifact) == digest)
            result["file_results"].append({
                "role": role, "file": filename,
                "status": "MATCH" if valid else "MISMATCH"
            })
        result["status"] = "VERIFIED" if all(
            v["status"] == "MATCH" for v in result["file_results"]) else "FAILED"
        result["reason"] = None if result["status"] == "VERIFIED" else "FILE_INTEGRITY_MISMATCH"
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        # Never echo untrusted file content or local paths in error receipts.
        result["reason"] = str(exc) if isinstance(exc, ValueError) else "RECEIPT_READ_FAILED"
    return result


def do_capture(url: str, mode: str, output: Path, max_mb: int, timeout: int) -> int:
    try:
        packet, receipt = capture(url, mode, output, max_mb=max_mb, timeout=timeout)
    except (DeliveryError, OSError) as exc:
        status = exc.status if isinstance(exc, DeliveryError) else "LOCAL_IO_ERROR"
        print(json.dumps({"contract": HOST_CONTRACT, "status": "BLOCKED", "failure": status}))
        return 2
    print(json.dumps({
        "contract": HOST_CONTRACT, "status": packet["status"],
        "failure": packet["failure"], "mode": mode, "receipt": str(receipt),
        "output_directory": str(receipt.parent),
        "artifacts": packet["artifacts"],
    }, indent=2))
    return 0 if packet["status"] == "DELIVERED" else 2


def interactive() -> int:
    print("Automation Media Delivery | Windows / Linux Mint")
    print("Save only content you are authorized to access and download.")
    print("Files stay on this computer. No logins, cookies or background jobs.")
    status = doctor()
    print("Python: " + status["python"])
    print("yt-dlp: " + (status["yt_dlp"]["version"] or "not available"))
    print("FFmpeg: " + (status["ffmpeg"]["version"] or "not available"))
    if not status["ready_modes"]:
        print("Missing prerequisites. Read HOST_SETUP.md for installation guidance.")
        return 2
    print("Available modes: " + ", ".join(status["ready_modes"]))
    print("Default output: " + status["default_output"])
    while True:
        url = input("\nEnter a video URL (blank to exit): ").strip()
        if not url:
            return 0
        mode = input("Mode [video/audio/hybrid] (default video): ").strip().lower() or "video"
        if mode not in status["ready_modes"]:
            print("Mode unavailable; check the FFmpeg installation and try again.")
            continue
        path = input("Output directory (blank for Downloads/Automation-Media): ").strip()
        destination = Path(path).expanduser() if path else default_output()
        code = do_capture(url, mode, destination, 500, 300)
        if code == 0:
            print("File saved. Run 'verify' against its receipt.json to recheck integrity.")
        else:
            print("Delivery blocked. Review the typed failure above; no access bypass attempted.")
        again = input("Capture another URL? [y/N]: ").strip().lower()
        if again not in {"y", "yes"}:
            return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command")
    check = commands.add_parser("doctor", help="Check installed tools without changing the host")
    check.add_argument("--json", action="store_true")
    take = commands.add_parser("capture", help="Download to private local host output")
    take.add_argument("--url", required=True)
    take.add_argument("--mode", choices=MODES, default="video")
    take.add_argument("--output-dir", type=Path, default=None)
    take.add_argument("--max-mb", type=int, default=500)
    take.add_argument("--timeout", type=int, default=300)
    prove = commands.add_parser("verify", help="Rehash files referenced by a receipt")
    prove.add_argument("--receipt", type=Path, required=True)
    commands.add_parser("interactive", help="Guided local capture session")
    a = parser.parse_args(argv)
    if a.command == "doctor":
        info = doctor()
        if a.json:
            print(json.dumps(info, indent=2))
        else:
            print("OS: " + info["platform"] + " | Python " + info["python"])
            print("yt-dlp: " + (info["yt_dlp"]["version"] or "MISSING"))
            print("FFmpeg: " + (info["ffmpeg"]["version"] or "MISSING"))
            print("Ready modes: " + (", ".join(info["ready_modes"]) or "none"))
            print("Output: " + info["default_output"])
            if info["action"] != "READY":
                print("Read capabilities/media-transcript-acquisition/HOST_SETUP.md for setup.")
        return 0 if info["ready_modes"] else 2
    if a.command == "capture":
        return do_capture(a.url, a.mode, a.output_dir or default_output(), a.max_mb, a.timeout)
    if a.command == "verify":
        receipt = verify_receipt(a.receipt)
        print(json.dumps(receipt, indent=2))
        return 0 if receipt["status"] == "VERIFIED" else 2
    try:
        return interactive()
    except (EOFError, KeyboardInterrupt):
        print("\nStopped without scheduling any follow-up.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
