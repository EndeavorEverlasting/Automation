"""Local synthetic proof for Git history preservation and provider-independent restore."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "capabilities/git-portability/portable_git.py"
SPEC = importlib.util.spec_from_file_location("portable_git", ENTRY)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def git(cwd, *args):
    return subprocess.check_output(["git", "-C", str(cwd), *args], text=True).strip()


class GitPortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.src = self.root / "repo"
        self.src.mkdir()
        git(self.src, "init", "-b", "main")
        git(self.src, "config", "user.email", "test@example.invalid")
        git(self.src, "config", "user.name", "Portability Canary")
        (self.src / "README.md").write_text("# Portable\n", encoding="utf-8")
        git(self.src, "add", ".")
        git(self.src, "commit", "-m", "initial")
        git(self.src, "branch", "develop")
        git(self.src, "tag", "v1")
        (self.src / "README.md").write_text("# Portable\nA second commit\n", encoding="utf-8")
        git(self.src, "commit", "-am", "change")
        self.archive = self.root / "snapshot.zip"

    def test_bundle_recovers_full_refs_and_current_files(self):
        original = dict(line.split(" ", 1)[::-1] for line in git(self.src, "show-ref").splitlines())
        receipt = MODULE.archive_snapshot(self.src, self.archive, "public")
        self.assertEqual(receipt["state"], "BACKUP_CREATED")
        manifest = MODULE.verify_archive(self.archive)
        self.assertEqual(manifest["head"], git(self.src, "rev-parse", "HEAD"))
        self.assertEqual(manifest["refs"], original)
        destination = self.root / "independent-restored.git"
        restored = MODULE.restore_archive(self.archive, destination)
        self.assertEqual(restored["state"], "RESTORED_AND_VERIFIED")
        self.assertEqual(dict(line.split(" ", 1)[::-1] for line in git(destination, "show-ref").splitlines()), original)
        working = self.root / "working"
        subprocess.run(["git", "clone", str(destination), str(working)], check=True, capture_output=True)
        self.assertEqual((working / "README.md").read_text(encoding="utf-8"), "# Portable\nA second commit\n")
        self.assertEqual(git(working, "rev-parse", "HEAD"), git(self.src, "rev-parse", "HEAD"))

    def test_dirty_source_and_existing_destination_fail_closed(self):
        (self.src / "untracked.txt").write_text("do not drop this", encoding="utf-8")
        with self.assertRaisesRegex(MODULE.PortabilityError, "DIRTY_SOURCE"):
            MODULE.archive_snapshot(self.src, self.archive, "public")
        self.assertFalse(self.archive.exists())
        (self.src / "untracked.txt").unlink()
        MODULE.archive_snapshot(self.src, self.archive, "public")
        with self.assertRaisesRegex(MODULE.PortabilityError, "OUTPUT_ALREADY_EXISTS"):
            MODULE.archive_snapshot(self.src, self.archive, "public")

    def test_private_source_requires_encrypted_adapter(self):
        with self.assertRaisesRegex(MODULE.PortabilityError, "PRIVATE_ARCHIVE"):
            MODULE.archive_snapshot(self.src, self.archive, "private")
        self.assertFalse(self.archive.exists())

    def test_submodules_and_lfs_fail_closed(self):
        (self.src / ".gitmodules").write_text("[submodule \"test\"]\n", encoding="utf-8")
        git(self.src, "add", ".gitmodules")
        git(self.src, "commit", "-m", "submodule placeholder")
        with self.assertRaisesRegex(MODULE.PortabilityError, "SUBMODULE"):
            MODULE.archive_snapshot(self.src, self.archive, "public")
        (self.src / ".gitmodules").unlink()
        git(self.src, "add", "-u")
        git(self.src, "commit", "-m", "remove placeholder")
        (self.src / ".gitattributes").write_text("*.bin filter=lfs\n", encoding="utf-8")
        git(self.src, "add", ".gitattributes")
        git(self.src, "commit", "-m", "lfs shape")
        with self.assertRaisesRegex(MODULE.PortabilityError, "LFS"):
            MODULE.archive_snapshot(self.src, self.archive, "public")

    def test_corrupt_archive_is_rejected_before_restore(self):
        MODULE.archive_snapshot(self.src, self.archive, "public")
        with __import__("zipfile").ZipFile(self.archive) as z:
            payload = {p: z.read(p) for p in z.namelist()}
        manifest = json.loads(payload["archive.manifest.json"])
        manifest["bundle_sha256"] = "0" * 64
        payload["archive.manifest.json"] = json.dumps(manifest).encode()
        with __import__("zipfile").ZipFile(self.archive, "w") as z:
            for p, data in payload.items():
                z.writestr(p, data)
        with self.assertRaisesRegex(MODULE.PortabilityError, "ARCHIVE_HASH_MISMATCH"):
            MODULE.verify_archive(self.archive)
        with self.assertRaisesRegex(MODULE.PortabilityError, "ARCHIVE_HASH_MISMATCH"):
            MODULE.restore_archive(self.archive, self.root / "recovered")


if __name__ == "__main__":
    unittest.main()
