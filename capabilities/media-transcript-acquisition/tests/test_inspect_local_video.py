import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


CAPABILITY = Path(__file__).resolve().parents[1]
INSPECTOR = CAPABILITY / "inspect_local_video.py"


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg and FFprobe required")
class LocalVideoTests(unittest.TestCase):
    def test_local_fingerprint_seeks_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="local video ") as temp:
            root = Path(temp)
            source = root / "Screen Recording -  two spaces.mp4"
            subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=s=160x90:r=10",
                 "-t", "2", "-c:v", "mpeg4", str(source)],
                check=True, timeout=30,
            )
            before = source.read_bytes()
            command = [sys.executable, str(INSPECTOR), "--input", str(source)]
            out = root / "review"
            subprocess.run(
                [*command, "--out-dir", str(out), "--at", "1.1", "--at", "0.2", "--at", "1.1"],
                check=True, timeout=50, capture_output=True,
            )
            text = (out / "source.json").read_text(encoding="utf-8")
            result = json.loads(text)
            self.assertEqual(result["source"]["sha256"], hashlib.sha256(before).hexdigest())
            self.assertEqual(result["source"]["bytes"], len(before))
            self.assertAlmostEqual(result["source"]["duration_seconds"], 2)
            self.assertNotIn(source.name, text)
            self.assertEqual([item["requested_seconds"] for item in result["frames"]], [0.2, 1.1])
            for item in result["frames"]:
                data = (out / item["file"]).read_bytes()
                self.assertEqual(item["sha256"], hashlib.sha256(data).hexdigest())
            for target, args in ((out, []), (root / "outside", ["--at", "3"])):
                rejected = subprocess.run(
                    [*command, "--out-dir", str(target), *args], capture_output=True, timeout=30
                )
                self.assertEqual(rejected.returncode, 2)
                self.assertNotIn(str(source).encode(), rejected.stderr)
            self.assertFalse((root / "outside").exists())
            self.assertEqual(text, (out / "source.json").read_text(encoding="utf-8"))
            self.assertEqual(before, source.read_bytes())


if __name__ == "__main__":
    unittest.main()
