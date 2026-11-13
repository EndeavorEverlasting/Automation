#!/usr/bin/env python3
"""Local-first, evidence-linked YouTube transcripts for research and LibreOffice.

Captions remain primary evidence. Local ASR is opt-in and never establishes
semantic accuracy by itself; audio downloads are deleted unless retained.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import html
import json
import os
import re
import shutil
import sys
import uuid
from pathlib import Path

from acquire import AcquisitionError, acquire, youtube_id
from deliver_artifact import DeliveryError, capture, checked_root, private_directory
from social_insights import asr_media

CONTRACT = "automation.research-transcript/v1"
TOKEN = re.compile(r"[\w']+", re.UNICODE)
NON_SPEECH = re.compile(r"\[(?:music|applause|laughter|inaudible|silence|noise)[^\]]*\]", re.I)
MAX_CUES = 50000
MAX_TEXT = 8_000_000
MAX_WINDOW_TOKENS = 320
MAX_COMPARISON_MINUTES = 24 * 60
MAX_WINDOW_ASSIGNMENTS = 250_000


def stamp(ms: int) -> str:
    seconds = ms // 1000
    return f"{seconds // 3600:02d}:{(seconds // 60) % 60:02d}:{seconds % 60:02d}"


def normalize(cues: list[dict]) -> list[dict]:
    if not isinstance(cues, list) or not 0 < len(cues) <= MAX_CUES:
        raise AcquisitionError("INVALID_TRANSCRIPT_CUES")
    normalized = []
    last_start = -1
    total = 0
    for i, item in enumerate(cues, 1):
        if not isinstance(item, dict):
            raise AcquisitionError("INVALID_TRANSCRIPT_CUES")
        start, end, raw = item.get("start_ms"), item.get("end_ms"), item.get("text")
        if (type(start) is not int or type(end) is not int or start < 0
                or end <= start or start < last_start or not isinstance(raw, str)):
            raise AcquisitionError("INVALID_TRANSCRIPT_CUES")
        text = " ".join(raw.split())
        if not text:
            raise AcquisitionError("INVALID_TRANSCRIPT_CUES")
        total += len(text)
        if total > MAX_TEXT:
            raise AcquisitionError("TRANSCRIPT_TOO_LARGE")
        normalized.append({"id": f"c{i:05d}", "start_ms": start, "end_ms": end, "text": text})
        last_start = start
    return normalized


def words(text: str) -> list[str]:
    return TOKEN.findall(text.casefold())


def review_flags(cues: list[dict]) -> list[dict]:
    flags = []
    if len(cues) < 3:
        flags.append({"code": "VERY_SHORT_TRANSCRIPT", "cue_id": cues[0]["id"], "start_ms": 0})
    for previous, cue in zip(cues, cues[1:]):
        if cue["start_ms"] - previous["end_ms"] >= 120000:
            flags.append({"code": "LONG_UNCAPTIONED_SPAN", "cue_id": cue["id"],
                          "start_ms": previous["end_ms"]})
        if previous["end_ms"] - cue["start_ms"] > 3000:
            flags.append({"code": "SUBSTANTIAL_CUE_OVERLAP", "cue_id": cue["id"],
                          "start_ms": cue["start_ms"]})
        if words(previous["text"]) == words(cue["text"]):
            flags.append({"code": "REPEATED_ADJACENT_CUE", "cue_id": cue["id"],
                          "start_ms": cue["start_ms"]})
    for cue in cues:
        if NON_SPEECH.search(cue["text"]):
            flags.append({"code": "NON_SPEECH_OR_INAUDIBLE", "cue_id": cue["id"],
                          "start_ms": cue["start_ms"]})
    return flags[:1000]


def _comparison_windows(cues: list[dict]) -> tuple[dict[int, list[str] | None], bool]:
    """Index cues once by minute; None marks an oversized window."""
    windows: dict[int, list[str] | None] = {}
    assigned = 0
    for cue in cues:
        first = cue["start_ms"] // 60000
        last = (cue["end_ms"] - 1) // 60000
        assigned += last - first + 1
        if assigned > MAX_WINDOW_ASSIGNMENTS:
            return {}, False
        tokens = []
        for match in TOKEN.finditer(cue["text"]):
            tokens.append(match.group().casefold())
            if len(tokens) > MAX_WINDOW_TOKENS:
                break
        for minute in range(first, last + 1):
            previous = windows.get(minute)
            if minute in windows and previous is None:
                continue
            existing = previous if previous is not None else []
            windows[minute] = (
                None if len(existing) + len(tokens) > MAX_WINDOW_TOKENS
                else existing + tokens
            )
    return windows, True


def compare_independent(captions: list[dict], asr: list[dict]) -> list[dict]:
    """Bounded minute comparison: disagreement is a review target, not accuracy."""
    if not captions or not asr:
        return []
    maximum = max(captions[-1]["end_ms"], asr[-1]["end_ms"])
    if maximum > MAX_COMPARISON_MINUTES * 60000:
        return [{"code": "COMPARISON_SKIPPED_LONG_SOURCE", "start_ms": 0}]
    left, left_ok = _comparison_windows(captions)
    right, right_ok = _comparison_windows(asr)
    if not left_ok or not right_ok:
        return [{"code": "COMPARISON_SKIPPED_RESOURCE_LIMIT", "start_ms": 0}]
    flags = []
    for minute in range((maximum + 59999) // 60000):
        start = minute * 60000
        a, b = left.get(minute, []), right.get(minute, [])
        if a is None or b is None:
            flags.append({"code": "COMPARISON_SKIPPED_LARGE_WINDOW", "start_ms": start})
        elif max(len(a), len(b)) >= 6 and min(len(a), len(b)) < 3:
            flags.append({"code": "CAPTION_ASR_COVERAGE_DISAGREEMENT",
                          "start_ms": start, "caption_tokens": len(a), "asr_tokens": len(b)})
        elif len(a) >= 6 and len(b) >= 6:
            similarity = difflib.SequenceMatcher(a=a, b=b, autojunk=False).ratio()
            if similarity < 0.55:
                flags.append({"code": "CAPTION_ASR_DIVERGENCE", "start_ms": start,
                              "lexical_similarity": round(similarity, 3)})
        if len(flags) >= 1000:
            break
    return flags


def atomic_text(path: Path, content: str) -> None:
    pending = path.with_name("." + path.name + ".tmp")
    try:
        pending.write_text(content, encoding="utf-8")
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def emit_documents(folder: Path, video_id: str, cues: list[dict], method: str,
                   review: dict) -> dict:
    source = f"https://www.youtube.com/watch?v={video_id}"
    lines = [f"[{cue['id']} {stamp(cue['start_ms'])}] {cue['text']}" for cue in cues]
    txt = f"Source: {source}\nAcquisition: {method}\nTranscript is not independently fact checked.\n\n" + "\n".join(lines) + "\n"
    html_lines = []
    for cue in cues:
        ts = stamp(cue["start_ms"])
        link = f"{source}&amp;t={cue['start_ms'] // 1000}s"
        html_lines.append(f'<p id="{cue["id"]}"><a href="{link}">[{cue["id"]} {ts}]</a> '
                          f'{html.escape(cue["text"], quote=True)}</p>')
    page = ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<title>Evidence-linked video transcript</title></head><body>\n"
            "<h1>Evidence-linked video transcript</h1>\n"
            f'<p>Source: <a href="{source}">{source}</a></p>\n'
            f'<p>Method: {html.escape(method)}. Not independently fact checked. '
            'Linked timestamps refer to video time.</p>\n'
            + "\n".join(html_lines) + "\n</body></html>\n")
    research = ("# Source-grounded development notes — worksheet\n\n"
                f"Video: {source}\n\n"
                "Treat transcript language as what a caption source or ASR reports, not verified fact.\n"
                "For each actionable insight capture: **claim**, **exact cNNNNN evidence IDs**, "
                "**timestamp**, **what was demonstrated vs. merely asserted**, "
                "**independent corroboration needed**, **possible implementation test**.\n\n"
                "Never invent quotations, speakers, code, or visual content absent from the evidence. "
                "Check original video at linked timestamps before committing technical decisions.\n\n"
                "## Candidate insights (not automatically inferred)\n\n"
                "| Claim / mechanism | Cue IDs & time | Demonstrated or asserted? | "
                "Corroboration needed | Proposed reproducible test |\n"
                "| --- | --- | --- | --- | --- |\n")
    outputs = {"transcript.txt": txt, "transcript.html": page,
               "development-notes.md": research,
               "quality-review.json": json.dumps(review, indent=2, sort_keys=True) + "\n"}
    artifacts = []
    for name, content in outputs.items():
        path = folder / name
        atomic_text(path, content)
        raw = path.read_bytes()
        artifacts.append({"file": name, "bytes": len(raw),
                          "sha256": hashlib.sha256(raw).hexdigest()})
    return {"artifacts": artifacts, "document": str(folder / "transcript.html")}


def output_root(path: Path, *, windows: bool | None = None) -> Path:
    """Windows transcript storage must inherit the user's private profile ACL."""
    root = checked_root(path)
    enforce_profile = os.name == "nt" if windows is None else windows
    if enforce_profile and not root.is_relative_to(Path.home().resolve()):
        raise DeliveryError("OUTPUT_OUTSIDE_USER_PROFILE")
    return root


def run(args: argparse.Namespace) -> tuple[dict, Path]:
    video_id = youtube_id(args.url)
    root = output_root(args.output_dir)
    private_directory(root)
    folder = root / f"{video_id}-{uuid.uuid4().hex[:12]}"
    private_directory(folder)
    source = f"https://www.youtube.com/watch?v={video_id}"
    packet = {"contract": CONTRACT, "status": "BLOCKED", "source": source,
              "method": None, "attempts": [], "cues": [], "quality": None,
              "caption_input_sha256": None, "cue_sha256": None,
              "artifacts": [], "failure": None,
              "proof_ceiling": "NO_TRANSCRIPT_EVIDENCE"}
    audio_folder = None
    try:
        try:
            result = acquire(source, args.captions_file, "offline" if args.captions_file else "auto")
            packet["attempts"] = result.get("attempts", [])
            packet["caption_input_sha256"] = result.get("input_sha256")
            cues = result.get("cues", [])
            method = result.get("method")
        except AcquisitionError as exc:
            cues, method = [], None
            packet["attempts"] = [{"adapter": "captions", "status": exc.status}]
        primary_cues = normalize(cues) if cues else []
        asr_cues = []
        if args.asr_model and (not primary_cues or args.compare_asr):
            media = args.media_file
            if media is None:
                delivery, receipt = capture(source, "audio", root / "media-cache",
                                            max_mb=args.max_audio_mb, timeout=300)
                packet["attempts"].append({"adapter": "audio_delivery", "status": delivery["status"],
                                           "failure": delivery.get("failure")})
                if delivery["status"] == "DELIVERED":
                    audio_folder = receipt.parent
                    media_artifact = next((x for x in delivery["artifacts"] if x["role"] == "audio"), None)
                    if media_artifact is None:
                        raise AcquisitionError("INVALID_AUDIO_DELIVERY")
                    media = audio_folder / media_artifact["file"]
            if media is not None:
                if not media.is_file() or media.is_symlink() or not 0 < media.stat().st_size <= args.max_audio_mb * 1048576:
                    raise AcquisitionError("INVALID_AUDIO_FILE")
                try:
                    asr_cues = normalize(asr_media(media, args.asr_model))
                    packet["attempts"].append({"adapter": "local_faster_whisper", "status": "SUCCESS"})
                except AcquisitionError as exc:
                    packet["attempts"].append({"adapter": "local_faster_whisper", "status": exc.status})
        if not primary_cues and asr_cues:
            primary_cues, method = asr_cues, "local_faster_whisper"
        if not primary_cues:
            raise AcquisitionError("NO_ACCESSIBLE_TRANSCRIPT")
        packet["status"] = "TRANSCRIPT_ACQUIRED"
        packet["method"] = method
        packet["cues"] = primary_cues
        packet["cue_sha256"] = hashlib.sha256(json.dumps(primary_cues, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        flags = review_flags(primary_cues)
        comparison_status = "NOT_REQUESTED"
        if args.compare_asr:
            if not asr_cues:
                comparison_status = "UNAVAILABLE"
                flags.append({"code": "ASR_COMPARISON_UNAVAILABLE", "start_ms": 0})
            else:
                comparison_flags = compare_independent(primary_cues, asr_cues)
                flags.extend(comparison_flags)
                comparison_status = ("PARTIAL_REVIEW" if any(
                    f["code"].startswith("COMPARISON_SKIPPED") for f in comparison_flags
                ) else "WINDOWS_COMPARED")
        review = {"contract": "automation.transcript-quality-review/v1",
                  "status": "REVIEW_REQUIRED" if flags else "UNVERIFIED_TRANSCRIPT",
                  "assurance": "NOT_INDEPENDENTLY_VERIFIED",
                  "cue_count": len(primary_cues),
                  "word_count": sum(len(words(c["text"])) for c in primary_cues),
                  "last_cue_end_ms": primary_cues[-1]["end_ms"],
                  "independent_asr_compared": comparison_status == "WINDOWS_COMPARED",
                  "comparison_status": comparison_status,
                  "flags": flags,
                  "notes": "Heuristic flags and lexical comparison locate review targets; neither proves accuracy."
                  }
        packet["quality"] = review
        packet["proof_ceiling"] = "TIMESTAMPED_SOURCE_TEXT_UNVERIFIED"
        packet.update(emit_documents(folder, video_id, primary_cues, method, review))
    except (AcquisitionError, DeliveryError, OSError) as exc:
        packet["status"] = "BLOCKED"
        packet["failure"] = exc.status if hasattr(exc, "status") else "LOCAL_IO_ERROR"
        packet["proof_ceiling"] = "NO_VERIFIED_TRANSCRIPT_EXPORT"
        for name in ("transcript.txt", "transcript.html", "development-notes.md", "quality-review.json"):
            (folder / name).unlink(missing_ok=True)
        packet["artifacts"] = []
        packet.pop("document", None)
    finally:
        if audio_folder is not None:
            if args.retain_audio:
                packet["audio_cleanup"] = "RETAINED_BY_REQUEST"
            else:
                try:
                    # Only the uniquely created delivery folder; never delete user media.
                    shutil.rmtree(audio_folder)
                    packet["audio_cleanup"] = "REMOVED"
                except OSError:
                    packet["audio_cleanup"] = "CLEANUP_FAILED"
        atomic_text(folder / "receipt.json", json.dumps(packet, indent=2, sort_keys=True) + "\n")
    return packet, folder / "receipt.json"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Public YouTube video URL")
    parser.add_argument("--output-dir", type=Path,
                        default=Path.home() / "Downloads" / "Automation-Transcripts")
    parser.add_argument("--captions-file", type=Path, help="Use locally supplied VTT/SRT (no provider call)")
    parser.add_argument("--media-file", type=Path, help="Owned local audio for optional offline ASR")
    parser.add_argument("--asr-model", help="Already downloaded faster-whisper model; no auto-download")
    parser.add_argument("--compare-asr", action="store_true", help="Compare caption text with opt-in offline ASR")
    parser.add_argument("--max-audio-mb", type=int, default=128)
    parser.add_argument("--retain-audio", action="store_true")
    args = parser.parse_args(argv)
    if args.max_audio_mb < 1 or args.max_audio_mb > 2048:
        parser.error("--max-audio-mb must be 1..2048")
    if args.compare_asr and not args.asr_model:
        parser.error("--compare-asr requires --asr-model")
    if args.media_file and not args.asr_model:
        parser.error("--media-file requires --asr-model")
    try:
        packet, receipt = run(args)
    except (AcquisitionError, DeliveryError, OSError) as exc:
        failure = exc.status if hasattr(exc, "status") else "LOCAL_IO_ERROR"
        print(json.dumps({"status": "BLOCKED", "failure": failure}))
        return 2
    print(json.dumps({"status": packet["status"], "failure": packet["failure"],
                      "receipt": str(receipt), "document": packet.get("document")}))
    return 0 if packet["status"] == "TRANSCRIPT_ACQUIRED" else 2


if __name__ == "__main__":
    sys.exit(main())
