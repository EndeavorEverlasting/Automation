"""Offline, network-free research transcript end-to-end and regression checks."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.youtube.com/watch?v=pl0EltNU5p0"
VTT = """WEBVTT

00:00:01.000 --> 00:00:02.900
Intro to &lt;model&gt; architecture.

00:00:03.000 --> 00:00:04.900
A second actionable thought.

00:00:05.000 --> 00:00:06.900
Test claims with evidence.
"""
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("research_transcribe", ROOT / "transcribe.py")
T = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(T)


class ResearchTranscriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.captions = self.root / "clip.vtt"
        self.captions.write_text(VTT, encoding="utf-8")
        self.output = self.root / "exports"

    def cli(self, *extras):
        return subprocess.run(
            [sys.executable, str(ROOT / "transcribe.py"), "--url", URL,
             "--output-dir", str(self.output), *extras],
            capture_output=True, text=True, timeout=15, cwd=self.root)

    def test_offline_cli_delivers_documents_and_hashes(self):
        proc = self.cli("--captions-file", str(self.captions))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        response = json.loads(proc.stdout)
        self.assertEqual(response["status"], "TRANSCRIPT_ACQUIRED")
        folder = Path(response["receipt"]).parent
        evidence = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["contract"], "automation.research-transcript/v1")
        self.assertEqual(evidence["method"], "provided_captions")
        import hashlib
        self.assertEqual(evidence["caption_input_sha256"], hashlib.sha256(self.captions.read_bytes()).hexdigest())
        self.assertEqual(len(evidence["cue_sha256"]), 64)
        self.assertEqual(evidence["quality"]["cue_count"], 3)
        self.assertFalse(evidence["quality"]["independent_asr_compared"])
        self.assertEqual(evidence["proof_ceiling"], "TIMESTAMPED_SOURCE_TEXT_UNVERIFIED")
        self.assertEqual(len(evidence["artifacts"]), 4)
        page = (folder / "transcript.html").read_text(encoding="utf-8")
        self.assertIn("&lt;model&gt;", page)
        self.assertNotIn("<model>", page)
        self.assertIn("t=1s", page)
        self.assertIn("c00001", page)
        self.assertIn("evidence IDs", (folder / "development-notes.md").read_text())
        import hashlib
        for artifact in evidence["artifacts"]:
            actual = (folder / artifact["file"]).read_bytes()
            self.assertEqual(len(actual), artifact["bytes"])
            self.assertEqual(hashlib.sha256(actual).hexdigest(), artifact["sha256"])

    def test_blocked_source_never_fabricates_transcript(self):
        self.captions.write_text("not captions", encoding="utf-8")
        proc = self.cli("--captions-file", str(self.captions))
        self.assertEqual(proc.returncode, 2)
        receipt = Path(json.loads(proc.stdout)["receipt"])
        packet = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(packet["status"], "BLOCKED")
        self.assertEqual(packet["failure"], "NO_ACCESSIBLE_TRANSCRIPT")
        self.assertFalse((receipt.parent / "transcript.html").exists())

    def test_input_validation_rejects_unordered_and_html_text(self):
        with self.assertRaises(T.AcquisitionError):
            T.normalize([{"start_ms": 2, "end_ms": 5, "text": "x"},
                         {"start_ms": 1, "end_ms": 5, "text": "y"}])
        with self.assertRaises(T.AcquisitionError):
            T.normalize([{"start_ms": 0, "end_ms": 2, "text": ""}])
        self.assertEqual(T.stamp(3723000), "01:02:03")

    def test_asr_fallback_uses_explicit_local_media_not_download(self):
        media = self.root / "owned.wav"
        media.write_bytes(b"synthetic-only")
        args = T.argparse.Namespace(url=URL, output_dir=self.output, captions_file=None,
                    media_file=media, asr_model="already-local", compare_asr=False,
                    max_audio_mb=128, retain_audio=False)
        asr = [{"start_ms": 1000, "end_ms": 2000, "text": "First."},
               {"start_ms": 2000, "end_ms": 3000, "text": "Second."},
               {"start_ms": 3000, "end_ms": 4000, "text": "Third."}]
        with patch.object(T, "acquire", return_value={"attempts": [{"adapter": "youtube_transcript_api",
                    "status": "PROVIDER_BLOCKED"}], "cues": [], "method": None}), \
             patch.object(T, "asr_media", return_value=asr), \
             patch.object(T, "capture", side_effect=AssertionError("Download forbidden")):
            result, receipt = T.run(args)
        self.assertEqual(result["status"], "TRANSCRIPT_ACQUIRED")
        self.assertEqual(result["method"], "local_faster_whisper")
        self.assertTrue(media.exists(), "Operator-supplied audio must be preserved")
        self.assertTrue(receipt.is_file())

    def test_caption_asr_disagreement_is_review_flag_not_confidence(self):
        caption = T.normalize([{"start_ms": 1000, "end_ms": 20000,
            "text": "the algorithm maps frames onto a trained motion model"}])
        asr = T.normalize([{"start_ms": 1000, "end_ms": 20000,
            "text": "winter birds and distant weather sound in the mountain valley"}])
        flags = T.compare_independent(caption, asr)
        self.assertEqual(flags[0]["code"], "CAPTION_ASR_DIVERGENCE")
        self.assertNotIn("confidence", json.dumps(flags))

    def test_comparison_detects_missing_caption_tail(self):
        caption = T.normalize([{"start_ms": 0, "end_ms": 20000,
            "text": "some technical words spoken in the opening section"}])
        asr = T.normalize([{"start_ms": 0, "end_ms": 20000,
            "text": "some technical words spoken in the opening section"},
            {"start_ms": 62000, "end_ms": 70000,
             "text": "more technical words appear after the captions end abruptly"}])
        flags = T.compare_independent(caption, asr)
        self.assertIn({"code": "CAPTION_ASR_COVERAGE_DISAGREEMENT", "start_ms": 60000,
                       "caption_tokens": 0, "asr_tokens": 9}, flags)

    def test_comparison_caps_large_and_pathological_windows(self):
        long_text = "token " * (T.MAX_WINDOW_TOKENS + 10)
        left = T.normalize([{"start_ms": 0, "end_ms": 50000, "text": long_text}])
        right = T.normalize([{"start_ms": 0, "end_ms": 50000, "text": long_text}])
        self.assertEqual(T.compare_independent(left, right)[0]["code"],
                         "COMPARISON_SKIPPED_LARGE_WINDOW")
        long_asr = T.normalize([{"start_ms": 0, "end_ms": (T.MAX_COMPARISON_MINUTES + 1) * 60000,
                                "text": "speech"}])
        self.assertEqual(T.compare_independent(left, long_asr)[0]["code"],
                         "COMPARISON_SKIPPED_LONG_SOURCE")

    def test_output_boundary_and_unwritable_directory_have_typed_status(self):
        import contextlib
        import io
        with self.assertRaises(T.DeliveryError):
            T.output_root(self.output, windows=True)
        stream = io.StringIO()
        with patch.object(T, "private_directory", side_effect=OSError("read only")), \
             contextlib.redirect_stdout(stream):
            result = T.main(["--url", URL, "--output-dir", str(self.output),
                             "--captions-file", str(self.captions)])
        self.assertEqual(result, 2)
        self.assertEqual(json.loads(stream.getvalue()),
                         {"status": "BLOCKED", "failure": "LOCAL_IO_ERROR"})

    def test_receipt_write_failure_is_typed_without_false_receipt(self):
        import contextlib
        import io
        original = T.atomic_text
        def fail_receipt(path, content):
            if path.name == "receipt.json":
                raise OSError("disk full")
            return original(path, content)
        stream = io.StringIO()
        with patch.object(T, "atomic_text", side_effect=fail_receipt), \
             contextlib.redirect_stdout(stream):
            result = T.main(["--url", URL, "--output-dir", str(self.output),
                             "--captions-file", str(self.captions)])
        self.assertEqual(result, 2)
        output = json.loads(stream.getvalue())
        self.assertEqual(output, {"status": "BLOCKED", "failure": "LOCAL_IO_ERROR"})
        self.assertNotIn("receipt", output)

    def test_no_output_inside_source_repository(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "transcribe.py"), "--url", URL,
             "--output-dir", str(ROOT), "--captions-file", str(self.captions)],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)["failure"], "OUTPUT_INSIDE_REPOSITORY")

    def test_flag_review_helps_identify_problem_spans(self):
        cues = T.normalize([
            {"start_ms": 0, "end_ms": 2000, "text": "[inaudible]"},
            {"start_ms": 123000, "end_ms": 125000, "text": "word"},
            {"start_ms": 125000, "end_ms": 127000, "text": "word"}])
        codes = {x["code"] for x in T.review_flags(cues)}
        self.assertIn("NON_SPEECH_OR_INAUDIBLE", codes)
        self.assertIn("LONG_UNCAPTIONED_SPAN", codes)
        self.assertIn("REPEATED_ADJACENT_CUE", codes)


if __name__ == "__main__":
    unittest.main()
