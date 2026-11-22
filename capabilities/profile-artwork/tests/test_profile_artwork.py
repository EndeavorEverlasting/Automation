import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DIRECTORY))
import profile_artwork as art


class PortableArtworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.fixture = Path(cls.directory.name) / "starter"
        cls.fixture.mkdir()
        cls.execute(cls.fixture, "init", "--account", "fixture-maker",
                    "--title", "Fixture Maker", "--tagline", "Build & share.")
        cls.execute(cls.fixture, "build")

    @staticmethod
    def execute(root, *args, succeeds=True):
        tool = root / "profile_artwork.py"
        if not tool.exists():
            shutil.copyfile(DIRECTORY / tool.name, tool)
        result = subprocess.run([sys.executable, "-B", str(tool), *args], cwd=root,
                                capture_output=True, text=True)
        if succeeds:
            if result.returncode:
                raise AssertionError(result.stderr)
            return json.loads(result.stdout)
        if result.returncode == 0:
            raise AssertionError("Invalid input unexpectedly succeeded.")
        return result.stderr

    def setUp(self):
        self.sandbox = TemporaryDirectory()
        self.addCleanup(self.sandbox.cleanup)
        self.root = Path(self.sandbox.name) / "consumer"
        shutil.copytree(self.fixture, self.root)
        self.readme = self.root / "README.md"
        self.v1 = self.root / art.ARCHIVE / "v01"

    def test_build_then_restore_keeps_edited_prose_and_old_assets(self):
        first = (self.v1 / "release.json").read_bytes()
        self.readme.write_text(self.readme.read_text().replace("Build &amp; share.", "My own portfolio."))
        config = self.root / art.CONFIG
        config.write_text(config.read_text().replace("#58c4ed", "#90dd72"))
        result = self.execute(self.root, "build")
        self.assertEqual(result["active"], "v02")
        self.assertNotEqual((self.v1 / "stitch-descent.gif").read_bytes(),
                            (self.root / art.ARCHIVE / "v02/stitch-descent.gif").read_bytes())
        self.assertEqual(first, (self.v1 / "release.json").read_bytes())
        self.execute(self.root, "restore", "v01")
        self.assertIn("My own portfolio.", self.readme.read_text())
        self.assertEqual(self.execute(self.root, "verify")["active"], "v01")

    def test_editorial_links_to_archives_do_not_select_a_release(self):
        self.execute(self.root, "build", "--from-assets", str(self.v1))
        note = "[First artwork](assets/profile-artwork/v01/stitch-descent.gif)\n\n"
        self.readme.write_text(note + self.readme.read_text())
        self.assertEqual(self.execute(self.root, "verify")["active"], "v02")
        self.assertEqual(self.execute(self.root, "build", "--from-assets", str(self.v1))["active"], "v03")
        self.execute(self.root, "restore", "v01")
        self.assertTrue(self.readme.read_text().startswith(note))
        self.assertEqual(self.execute(self.root, "verify")["active"], "v01")

    def test_import_needs_no_source_checkout_and_copies_exact_media(self):
        other = self.root.parent / "another"
        other.mkdir()
        self.execute(other, "init", "--account", "another-artist", "--title", "Artist",
                     "--tagline", "Motion and code.")
        self.execute(other, "build", "--from-assets", str(self.v1))
        new = other / art.ARCHIVE / "v01"
        for file in art.FILES:
            self.assertEqual((self.v1 / file).read_bytes(), (new / file).read_bytes())
        self.assertIn("github.com/another-artist?tab=repositories", (other / "README.md").read_text())

    def test_bad_import_does_not_advance_or_change_readme(self):
        source = self.root.parent / "bad"
        shutil.copytree(self.v1, source)
        (source / "stitch-descent.gif").write_bytes(b"not a gif")
        old = self.readme.read_bytes()
        self.execute(self.root, "build", "--from-assets", str(source), succeeds=False)
        self.assertEqual(old, self.readme.read_bytes())
        self.assertEqual(art.list_releases(self.root), ["v01"])
        self.assertFalse((self.root / ".profile-artwork.lock").exists())

    def test_animated_png_cannot_be_used_as_a_reduced_motion_poster(self):
        animated = self.root.parent / "animated-poster"
        shutil.copytree(self.v1, animated)
        poster = animated / "stitch-descent.png"
        with Image.open(poster) as source:
            image = source.convert("RGB")
        image.save(poster, save_all=True, append_images=[Image.new("RGB", image.size, "#e9a636")],
                   duration=130, loop=0)
        error = self.execute(self.root, "build", "--from-assets", str(animated), succeeds=False)
        self.assertIn("static reduced-motion PNG", error)
        self.assertEqual(art.list_releases(self.root), ["v01"])

    def test_corrupted_archive_and_mixed_readme_fail(self):
        self.readme.write_text(self.readme.read_text().replace("v01/stitch-resume.gif", "v02/stitch-resume.gif"))
        self.assertIn("mixed releases", self.execute(self.root, "verify", succeeds=False))
        self.readme.write_bytes((self.fixture / "README.md").read_bytes())
        (self.v1 / "stitch-resume.gif").write_bytes(b"garbage")
        self.assertIn("artwork bytes changed", self.execute(self.root, "verify", succeeds=False))

    def test_rendered_frames_are_visibly_different_at_phone_width(self):
        for scene in art.SCENES:
            with Image.open(self.v1 / f"{scene}.gif") as gif:
                still = gif.convert("RGB").resize((255, 97), Image.Resampling.LANCZOS)
                gif.seek(10)
                middle = gif.convert("RGB").resize((255, 97), Image.Resampling.LANCZOS)
                self.assertGreater(sum(ImageChops.difference(still, middle).tobytes()), 5000)

    def test_public_readback_checks_rendered_panel_bytes_and_link(self):
        page = "https://github.com/fixture-maker"
        prefix = f"{page}/fixture-maker/raw/main/{art.ARCHIVE}"
        text = self.readme.read_text().replace(art.ARCHIVE, prefix)
        markup = f'<article class="markdown-body">{text}</article>'
        assets = art.read_release(self.root, "v01", "fixture-maker")
        responses = {page: markup.encode(), **{f"{prefix}/v01/{k}": v for k, v in assets.items()}}
        with patch.object(art, "http_read", side_effect=responses.__getitem__):
            self.assertEqual(art.verify_public("fixture-maker", "v01", assets), page)
            responses[page] = markup.replace("<picture>", "<details><picture>", 1).replace(
                "</picture>", "</picture></details>", 1).encode()
            with self.assertRaisesRegex(ValueError, "wrong artwork layout"):
                art.verify_public("fixture-maker", "v01", assets)
            responses[page] = markup.encode()
            responses[f"{prefix}/v01/stitch-pulse.gif"] = b"old glyphs"
            with self.assertRaisesRegex(ValueError, "bytes differ"):
                art.verify_public("fixture-maker", "v01", assets)

    def test_init_and_lock_preserve_existing_files(self):
        settings = self.root / art.CONFIG
        before = settings.read_bytes()
        self.execute(self.root, "init", "--account", "new-user", "--title", "New",
                     "--tagline", "New", succeeds=False)
        self.assertEqual(before, settings.read_bytes())
        (self.root / ".profile-artwork.lock").touch()
        self.assertIn("Another artwork edit", self.execute(self.root, "build", succeeds=False))
        self.assertEqual(art.list_releases(self.root), ["v01"])


if __name__ == "__main__":
    unittest.main()
