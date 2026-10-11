#!/usr/bin/env python3
"""Local-first transcript acquisition with explicit provenance and failure ceilings."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

CONTRACT = "automation.media-transcript-evidence/v1"
ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
TIMING = re.compile(r"^\s*((?:\d\d:)?\d\d:\d\d[,.]\d{3})\s*-->\s*((?:\d\d:)?\d\d:\d\d[,.]\d{3})(?:\s|$)")
TAG = re.compile(r"<[^>]*>")
MAX_BYTES = 8_000_000


class AcquisitionError(Exception):
    def __init__(self, status):
        self.status = status
        super().__init__(status)


def youtube_id(url: str) -> str:
    """Only explicit YouTube watch/short/live/share URLs; never arbitrary hosts."""
    parsed = urlparse(url)
    try:
        invalid_authority = parsed.username or parsed.password or parsed.port
    except ValueError:
        raise AcquisitionError("INVALID_SOURCE") from None
    if parsed.scheme != "https" or invalid_authority:
        raise AcquisitionError("INVALID_SOURCE")
    host = (parsed.hostname or "").lower()
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            candidates = parse_qs(parsed.query).get("v", [])
            video_id = candidates[0] if len(candidates) == 1 else ""
        else:
            components = parsed.path.strip("/").split("/")
            video_id = components[1] if len(components) == 2 and components[0] in {"shorts", "live", "embed"} else ""
    elif host == "youtu.be":
        pieces = parsed.path.strip("/").split("/")
        video_id = pieces[0] if len(pieces) == 1 else ""
    else:
        raise AcquisitionError("INVALID_SOURCE")
    if not ID.fullmatch(video_id):
        raise AcquisitionError("INVALID_SOURCE")
    return video_id


def _ms(value: str) -> int:
    parts = value.replace(",", ".").split(":")
    try:
        seconds = float(parts[-1])
        minutes = int(parts[-2])
        hours = int(parts[-3]) if len(parts) == 3 else 0
        return round((hours * 3600 + minutes * 60 + seconds) * 1000)
    except (IndexError, ValueError):
        raise AcquisitionError("INVALID_CAPTIONS") from None


def parse_cues(body: str) -> list[dict]:
    """Parse basic VTT/SRT cues; reject unparseable input, never invent text."""
    body = body.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", body)
    cues = []
    for block in blocks:
        lines = block.strip().splitlines()
        if not lines or lines[0].strip().startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        idx = next((i for i, line in enumerate(lines[:3]) if "-->" in line), -1)
        if idx < 0:
            continue
        match = TIMING.match(lines[idx])
        if not match:
            raise AcquisitionError("INVALID_CAPTIONS")
        start, end = _ms(match.group(1)), _ms(match.group(2))
        if end <= start:
            raise AcquisitionError("INVALID_CAPTIONS")
        caption = html.unescape(TAG.sub("", " ".join(lines[idx + 1:]))).strip()
        caption = " ".join(caption.split())
        if not caption:
            continue
        if cues and cues[-1]["text"] == caption and start >= cues[-1]["start_ms"]:
            cues[-1]["end_ms"] = max(cues[-1]["end_ms"], end)
        else:
            cues.append({"start_ms": start, "end_ms": end, "text": caption})
    if not cues:
        raise AcquisitionError("INVALID_CAPTIONS")
    return cues


def from_file(path: Path) -> tuple[list[dict], str]:
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise AcquisitionError("INVALID_CAPTIONS")
    try:
        raw = path.read_bytes()
        cues = parse_cues(raw.decode("utf-8-sig"))
    except (UnicodeError, OSError):
        raise AcquisitionError("INVALID_CAPTIONS") from None
    return cues, hashlib.sha256(raw).hexdigest()


def from_transcript_api(video_id: str) -> list[dict]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        raise AcquisitionError("ADAPTER_UNAVAILABLE") from None
    try:
        raw = YouTubeTranscriptApi().fetch(video_id, languages=["en"])
        cues = []
        for item in raw:
            start = round(float(item.start) * 1000)
            end = round((float(item.start) + float(item.duration)) * 1000)
            if end > start and str(item.text).strip():
                cues.append({"start_ms": start, "end_ms": end, "text": " ".join(str(item.text).split())})
        if not cues:
            raise AcquisitionError("CAPTIONS_UNAVAILABLE")
        return cues
    except AcquisitionError:
        raise
    except Exception as exc:
        # Untrusted upstream errors may contain credentials or account identifiers.
        name = type(exc).__name__
        if name in {"RequestBlocked", "IpBlocked", "TooManyRequests"}:
            raise AcquisitionError("PROVIDER_BLOCKED") from None
        if name in {"NoTranscriptFound", "TranscriptsDisabled", "VideoUnavailable"}:
            raise AcquisitionError("CAPTIONS_UNAVAILABLE") from None
        raise AcquisitionError("PROVIDER_ERROR") from None


def from_ytdlp(video_id: str) -> tuple[list[dict], str]:
    binary = shutil.which("yt-dlp")
    if not binary:
        raise AcquisitionError("ADAPTER_UNAVAILABLE")
    with tempfile.TemporaryDirectory(prefix="transcript-acquire-") as temp:
        template = str(Path(temp) / "%(id)s.%(ext)s")
        command = [binary, "--ignore-config", "--no-playlist", "--skip-download",
                   "--write-subs", "--write-auto-subs", "--sub-langs", "en",
                   "--sub-format", "vtt/srt", "--no-progress", "--retries", "1",
                   "--socket-timeout", "12", "-o", template,
                   "https://www.youtube.com/watch?v=" + video_id]
        try:
            process = subprocess.run(command, capture_output=True, text=True,
                                     timeout=60, check=False)
        except subprocess.TimeoutExpired:
            raise AcquisitionError("PROVIDER_TIMEOUT") from None
        if process.returncode != 0:
            raise AcquisitionError("PROVIDER_ERROR")
        files = sorted(Path(temp).glob(video_id + ".*.vtt")) + sorted(Path(temp).glob(video_id + ".*.srt"))
        if not files:
            raise AcquisitionError("CAPTIONS_UNAVAILABLE")
        return from_file(files[0])


def acquire(url: str, captions_file: Path | None, strategy: str) -> dict:
    video_id = youtube_id(url)
    attempts = []
    if captions_file:
        cues, digest = from_file(captions_file)
        return {"video_id": video_id, "cues": cues, "method": "provided_captions",
                "input_sha256": digest, "attempts": attempts}
    if strategy == "offline":
        raise AcquisitionError("SOURCE_NOT_ATTACHED")
    for name, action in (("youtube_transcript_api", from_transcript_api), ("yt_dlp", from_ytdlp)):
        try:
            data = action(video_id)
            if name == "yt_dlp":
                cues, digest = data
            else:
                cues, digest = data, None
            attempts.append({"adapter": name, "status": "SUCCESS"})
            return {"video_id": video_id, "cues": cues, "method": name,
                    "input_sha256": digest, "attempts": attempts}
        except AcquisitionError as exc:
            attempts.append({"adapter": name, "status": exc.status})
    # A blocked host cannot prove captions do not exist.
    return {"video_id": video_id, "cues": [], "method": None, "input_sha256": None,
            "attempts": attempts, "failure": "UNRESOLVED_SOURCE_ACCESS"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--captions-file", type=Path)
    parser.add_argument("--strategy", choices=["auto", "offline"], default="auto")
    parser.add_argument("--out", required=True, type=Path,
                        help="Local JSON output; never check into public Git")
    args = parser.parse_args(argv)
    try:
        result = acquire(args.url, args.captions_file, args.strategy)
        success = bool(result.get("cues"))
        packet = {"contract": CONTRACT,
                  "source": {"provider": "youtube", "video_id": result["video_id"]},
                  "status": "TRANSCRIPT_ACQUIRED" if success else result["failure"],
                  "method": result["method"], "attempts": result["attempts"],
                  "cues": result["cues"], "input_sha256": result["input_sha256"],
                  "proof_ceiling": "SOURCE_TEXT_ACQUIRED" if success else "NO_SOURCE_TEXT"}
    except AcquisitionError as exc:
        packet = {"contract": CONTRACT, "status": exc.status,
                  "proof_ceiling": "NO_SOURCE_TEXT", "method": None,
                  "attempts": [], "cues": []}
        success = False
    args.out.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": packet["status"], "receipt": "WRITTEN"}))
    return 0 if success else 2


if __name__ == "__main__":
    sys.exit(main())
