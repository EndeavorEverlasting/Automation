#!/usr/bin/env python3
"""Bounded social video -> timestamped evidence -> optional local multimodal insights.

Run this file locally; do not commit generated output or source media.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlunsplit

from acquire import AcquisitionError, from_file
from adapters.yt_dlp_social import download_media
from adapters.ollama_local import infer_insights

CONTRACT = "automation.social-media-insights/v1"
PLATFORMS = {
    "instagram.com": "instagram", "www.instagram.com": "instagram",
    "youtube.com": "youtube", "www.youtube.com": "youtube", "m.youtube.com": "youtube",
    "youtu.be": "youtube", "tiktok.com": "tiktok", "www.tiktok.com": "tiktok",
    "vm.tiktok.com": "tiktok", "www.facebook.com": "facebook",
    "facebook.com": "facebook", "fb.watch": "facebook", "x.com": "x",
    "www.x.com": "x", "twitter.com": "x", "www.twitter.com": "x",
    "reddit.com": "reddit", "www.reddit.com": "reddit", "v.redd.it": "reddit",
    "vimeo.com": "vimeo", "www.vimeo.com": "vimeo",
    "linkedin.com": "linkedin", "www.linkedin.com": "linkedin",
}
MAX_LOCAL_MEDIA = 500_000_000


def normalize_source(url: str) -> tuple[str, str]:
    """Reject non-HTTPS, embedded credentials, ports, fragments and unknown authorities.

    Keep meaningful platform query parameters (for example YouTube's v=) but
    discard all query parameters for stable Instagram reel/post URLs.
    """
    try:
        u = urlsplit(url)
        if u.scheme != "https" or not u.hostname or u.username or u.password or u.port:
            raise ValueError()
    except ValueError:
        raise AcquisitionError("INVALID_SOURCE") from None
    host = u.hostname.lower()
    provider = PLATFORMS.get(host)
    if not provider or not u.path.startswith("/") or "\\" in u.path or not re.fullmatch(r"/[\w.\-/%@+~=!$&'()*,:;]*/?", u.path):
        raise AcquisitionError("UNSUPPORTED_OR_INVALID_SOURCE")
    if provider == "instagram":
        if not re.fullmatch(r"/(?:reel|p|tv)/[A-Za-z0-9_-]+/?", u.path):
            raise AcquisitionError("UNSUPPORTED_SOURCE_TYPE")
        query = ""
    elif provider == "youtube" and u.path == "/watch":
        values = parse_qs(u.query).get("v", [])
        if len(values) != 1 or not re.fullmatch(r"[A-Za-z0-9_-]{11}", values[0]):
            raise AcquisitionError("INVALID_SOURCE")
        query = "v=" + values[0]
    else:
        query = ""  # no tracking params or secrets in receipts
    return provider, urlunsplit(("https", host, u.path.rstrip("/") or "/", query, ""))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def asr_media(path: Path, model_name: str) -> list[dict]:
    """Explicit opt-in, local faster-whisper only; model install/download is operator-owned."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise AcquisitionError("ASR_ADAPTER_UNAVAILABLE") from None
    try:
        model = WhisperModel(model_name, device="cpu", compute_type="int8", local_files_only=True)
        segments, _ = model.transcribe(str(path), beam_size=5, vad_filter=True)
        cues = [{"start_ms": round(seg.start * 1000), "end_ms": round(seg.end * 1000),
                 "text": " ".join(seg.text.split())}
                for seg in segments if seg.end > seg.start and seg.text.strip()]
    except Exception:
        raise AcquisitionError("ASR_FAILED") from None
    if not cues:
        raise AcquisitionError("NO_SPEECH_DETECTED")
    return cues


def sample_frames(media: Path, directory: Path, limit: int = 12) -> list[dict]:
    """Local bounded preview frames; timestamps denote nominal sampling slots."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AcquisitionError("VIDEO_ADAPTER_UNAVAILABLE")
    directory.mkdir(parents=True, exist_ok=True)
    argv = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(media), "-vf", "fps=1/8,scale=640:-2", "-frames:v",
            str(limit), str(directory / "frame-%03d.jpg")]
    try:
        result = subprocess.run(argv, capture_output=True, timeout=90, check=False)
    except (subprocess.TimeoutExpired, OSError):
        raise AcquisitionError("VIDEO_PROCESSING_FAILED") from None
    if result.returncode != 0:
        raise AcquisitionError("VIDEO_PROCESSING_FAILED")
    frames = []
    for i, frame in enumerate(sorted(directory.glob("frame-*.jpg"))[:limit]):
        if frame.stat().st_size > 2_000_000:
            continue
        frames.append({"id": f"f{i+1:04d}", "nominal_ms": i * 8000,
                       "file": frame.name, "sha256": sha256_file(frame)})
    return frames


def source_evidence(url: str, captions: Path | None, media: Path | None,
                    strategy: str, asr_model: str | None, assets: Path) -> tuple[list[dict], list[dict], list[dict], str | None]:
    attempts = []
    cues: list[dict] = []
    frames: list[dict] = []
    if captions:
        cues, digest = from_file(captions)
        attempts.append({"adapter": "provided_caption_file", "status": "SUCCESS", "sha256": digest})
    if media:
        if not media.is_file() or not 0 < media.stat().st_size <= MAX_LOCAL_MEDIA:
            raise AcquisitionError("INVALID_MEDIA")
        attempts.append({"adapter": "provided_local_media", "status": "SUCCESS", "sha256": sha256_file(media)})
    if strategy == "offline" and not captions and not media:
        raise AcquisitionError("SOURCE_NOT_ATTACHED")
    if not media and strategy == "auto":
        # Provider and DRM/access restrictions are never bypassed here.
        try:
            media, downloaded_captions = download_media(url, assets)
            attempts.append({"adapter": "yt_dlp_social", "status": "SUCCESS"})
            if downloaded_captions and not cues:
                try:
                    cues, _ = from_file(downloaded_captions)
                except AcquisitionError:
                    attempts.append({"adapter": "yt_dlp_captions", "status": "INVALID_CAPTIONS"})
        except AcquisitionError as exc:
            attempts.append({"adapter": "yt_dlp_social", "status": exc.status})
    if media:
        if not media.is_file() or media.stat().st_size > MAX_LOCAL_MEDIA:
            raise AcquisitionError("INVALID_MEDIA")
        try:
            frames = sample_frames(media, assets)
            attempts.append({"adapter": "ffmpeg_frames", "status": "SUCCESS" if frames else "NO_FRAMES"})
        except AcquisitionError as exc:
            attempts.append({"adapter": "ffmpeg_frames", "status": exc.status})
        if not cues and asr_model:
            try:
                cues = asr_media(media, asr_model)
                attempts.append({"adapter": "faster_whisper_local", "status": "SUCCESS"})
            except AcquisitionError as exc:
                attempts.append({"adapter": "faster_whisper_local", "status": exc.status})
    if not cues and not frames:
        return [], [], attempts, "UNRESOLVED_SOURCE_ACCESS"
    return cues, frames, attempts, None


def analyze(cues: list[dict], frames: list[dict], assets: Path, model: str) -> list[dict]:
    numbered = [{"id": f"c{i+1:04d}", **cue} for i, cue in enumerate(cues)]
    raw = infer_insights(numbered, frames, assets, model)
    if not isinstance(raw, dict) or not isinstance(raw.get("insights"), list):
        raise AcquisitionError("INVALID_ANALYSIS")
    valid = {x["id"] for x in numbered} | {f["id"] for f in frames}
    clean = []
    for item in raw["insights"][:40]:
        if not isinstance(item, dict):
            continue
        evidence = item.get("evidence_ids")
        claim = item.get("claim")
        if not isinstance(claim, str) or not claim.strip() or not isinstance(evidence, list):
            continue
        if not evidence or any(not isinstance(e, str) or e not in valid for e in evidence):
            continue
        clean.append({"claim": claim.strip()[:1000], "evidence_ids": list(dict.fromkeys(evidence)),
                      "verification": "UNVERIFIED_TECHNICAL_CLAIM"})
    if not clean:
        raise AcquisitionError("NO_GROUNDED_INSIGHTS")
    return clean


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--captions-file", type=Path)
    parser.add_argument("--media-file", type=Path)
    parser.add_argument("--strategy", choices=("offline", "auto"), default="auto")
    parser.add_argument("--asr-model", help="Name of already-downloaded local faster-whisper model")
    parser.add_argument("--ollama-model", help="Opt in to localhost Ollama multimodal analysis")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    packet = {"contract": CONTRACT, "status": "UNRESOLVED_SOURCE_ACCESS",
              "source": None, "attempts": [], "cues": [], "frames": [], "insights": [],
              "proof_ceiling": "NO_SOURCE_EVIDENCE"}
    try:
        provider, url = normalize_source(args.url)
        packet["source"] = {"provider": provider, "url": url}
        assets = args.out.with_suffix(".assets")
        cues, frames, attempts, failure = source_evidence(
            url, args.captions_file, args.media_file, args.strategy, args.asr_model, assets)
        packet["attempts"] = attempts
        packet["cues"] = [{"id": f"c{i+1:04d}", **cue} for i, cue in enumerate(cues)]
        packet["frames"] = frames
        if failure:
            packet["status"] = failure
        else:
            packet["status"] = "EVIDENCE_READY"
            packet["proof_ceiling"] = "SOURCE_EVIDENCE_ACQUIRED_NOT_FACT_CHECKED"
            if args.ollama_model:
                try:
                    packet["insights"] = analyze(cues, frames, assets, args.ollama_model)
                    packet["status"] = "INSIGHTS_EXTRACTED"
                    packet["proof_ceiling"] = "GROUNDED_MODEL_OUTPUT_NOT_FACT_CHECKED"
                except AcquisitionError as exc:
                    packet["attempts"].append({"adapter": "ollama_local", "status": exc.status})
    except (AcquisitionError, OSError) as exc:
        packet["status"] = exc.status if isinstance(exc, AcquisitionError) else "LOCAL_IO_ERROR"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": packet["status"], "receipt": "WRITTEN"}))
    return 0 if packet["status"] in ("EVIDENCE_READY", "INSIGHTS_EXTRACTED") else 2


if __name__ == "__main__":
    sys.exit(main())
