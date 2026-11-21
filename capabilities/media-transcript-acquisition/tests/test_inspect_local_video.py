import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


CAPABILITY = Path(__file__).resolve().parents[1]
INSPECTOR = CAPABILITY / "inspect_local_video.py"
sys.path.insert(0, str(CAPABILITY))

from adapters import ffmpeg_files
from inspect_local_video import inspect
from social_insights import AcquisitionError, sample_frames


class VideoProcessingBoundaryTests(unittest.TestCase):
    def test_analysis_launches_file_tools_with_explicit_output_sinks(self):
        media = CAPABILITY / "recording with spaces.mp4"
        frame = CAPABILITY / "frame.png"
        with patch.object(ffmpeg_files.shutil, "which", side_effect=lambda name: name), \
                patch.object(ffmpeg_files, "os", SimpleNamespace(name="nt")), \
                patch.object(ffmpeg_files.subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True), \
                patch.object(ffmpeg_files.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, stdout="{}")
            ffmpeg_files.probe_video(media)
            ffmpeg_files.extract_frame(media, frame, 0.5)
            ffmpeg_files.sample_preview_frames(media, frame.parent, 3)

        self.assertEqual([call.args[0][0] for call in run.call_args_list],
                         ["ffprobe", "ffmpeg", "ffmpeg"])
        probe = run.call_args_list[0].args[0]
        self.assertEqual(probe[-3:], ["-of", "json", str(media)])
        for call in run.call_args_list:
            self.assertEqual(call.kwargs["stdin"], subprocess.DEVNULL)
            self.assertTrue(call.kwargs["capture_output"])
            self.assertFalse(call.kwargs.get("shell", False))
            self.assertEqual(call.kwargs["creationflags"], 0x08000000)
            self.assertIn("-protocol_whitelist", call.args[0])
        for call, path in zip(run.call_args_list[1:], (frame, frame.parent / "frame-%03d.jpg")):
            argv = call.args[0]
            self.assertIn("-nostdin", argv)
            self.assertEqual(argv[argv.index("-map") + 1], "0:v:0")
            self.assertIn("-an", argv)
            self.assertEqual(argv[-3:], ["-f", "image2", "./" + path.name])
            self.assertEqual(call.kwargs["cwd"], path.parent.resolve())

    def test_missing_tools_stop_without_opening_the_source(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "recording.mp4"
            source.write_bytes(b"fixture")
            output = source.parent / "review"
            with patch.object(ffmpeg_files.shutil, "which", return_value=None) as find, \
                    patch.object(ffmpeg_files.subprocess, "run") as run:
                with self.assertRaisesRegex(ValueError, "ffprobe is required"):
                    inspect(source, output, [0.5])
                with self.assertRaisesRegex(AcquisitionError, "VIDEO_ADAPTER_UNAVAILABLE"):
                    sample_frames(source, source.parent)
            self.assertEqual([call.args[0] for call in find.call_args_list], ["ffprobe", "ffmpeg"])
            run.assert_not_called()
            self.assertFalse(output.exists())



@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg and FFprobe required")
class LocalVideoTests(unittest.TestCase):
    def test_local_fingerprint_seeks_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="local video ") as temp:
            root = Path(temp)
            source = root / "Screen Recording -  two spaces.mp4"
            subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=s=160x90:r=10",
                 "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=44100",
                 "-t", "10", "-c:v", "mpeg4", "-c:a", "aac", str(source)],
                check=True, timeout=30,
            )
            before = source.read_bytes()
            pcm = subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-i", str(source), "-map", "0:a:0",
                 "-f", "s16le", "pipe:1"],
                capture_output=True, check=True, timeout=30,
            ).stdout
            self.assertTrue(any(pcm), "Fixture must contain non-silent audio")
            command = [sys.executable, str(INSPECTOR), "--input", str(source)]
            out = root / "review"
            subprocess.run(
                [*command, "--out-dir", str(out), "--at", "1.1", "--at", "0.2", "--at", "1.1"],
                check=True, timeout=50, capture_output=True,
            )
            text = (out / "source.json").read_text(encoding="utf-8")
            result = json.loads(text)
            self.assertEqual(result["processing"], "FILES_ONLY")
            self.assertEqual(result["source"]["sha256"], hashlib.sha256(before).hexdigest())
            self.assertEqual(result["source"]["bytes"], len(before))
            self.assertAlmostEqual(result["source"]["duration_seconds"], 10)
            self.assertNotIn(source.name, text)
            self.assertEqual([item["requested_seconds"] for item in result["frames"]], [0.2, 1.1])
            for item in result["frames"]:
                data = (out / item["file"]).read_bytes()
                self.assertEqual(item["sha256"], hashlib.sha256(data).hexdigest())
            for target, args in ((out, []), (root / "outside", ["--at", "11"])):
                rejected = subprocess.run(
                    [*command, "--out-dir", str(target), *args], capture_output=True, timeout=30
                )
                self.assertEqual(rejected.returncode, 2)
                self.assertNotIn(str(source).encode(), rejected.stderr)
            self.assertFalse((root / "outside").exists())
            self.assertEqual(text, (out / "source.json").read_text(encoding="utf-8"))
            social_output = root / "review with % signs" / "social.json"
            subprocess.run(
                [sys.executable, str(CAPABILITY / "social_insights.py"),
                 "--url", "https://www.instagram.com/reel/fixture", "--strategy", "offline",
                 "--media-file", str(source), "--out", str(social_output)],
                check=True, timeout=30, capture_output=True,
            )
            social = json.loads(social_output.read_text(encoding="utf-8"))
            self.assertEqual(social["status"], "EVIDENCE_READY")
            self.assertTrue(social["frames"])
            self.assertEqual(before, source.read_bytes())


if __name__ == "__main__":
    unittest.main()
