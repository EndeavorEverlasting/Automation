import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
CAPABILITY = ROOT / "capabilities" / "installer-bootstrap"
HOST = ROOT / "capabilities" / "media-transcript-acquisition" / "host_app.py"

sys.path.insert(0, str(CAPABILITY))
from installer_bootstrap import Installer, Option, SetupError, Step, _Session


class InstallerBootstrapTests(unittest.TestCase):
    def test_successful_host_install_is_usable_outside_checkout(self):
        with TemporaryDirectory() as temp:
            target = Path(temp) / "app"
            command = [sys.executable, str(HOST), "setup", "--install-dir", str(target),
                       "--prefer-audio", "--skip-tool-check"]
            plan = json.loads(subprocess.check_output(command + ["--plan"], cwd=temp))
            self.assertEqual(plan["status"], "review")
            self.assertFalse(target.exists())
            result = json.loads(subprocess.check_output(command + ["--apply"], cwd=temp))
            self.assertEqual([step["state"] for step in result["steps"]], ["done", "skipped", "done"])
            self.assertEqual(result["progress"], 100)
            installed = target / "media-delivery.pyz"
            digest = hashlib.sha256(installed.read_bytes()).digest()
            help_text = subprocess.check_output([sys.executable, "-I", str(installed), "--help"], cwd=temp)
            self.assertIn(b"doctor", help_text)
            self.assertIn(b"{doctor,capture,verify,interactive}", help_text)
            with ZipFile(installed) as package:
                self.assertIn(b"default_mode='audio'", package.read("__main__.py"))
            self.assertEqual(hashlib.sha256(installed.read_bytes()).digest(), digest)

    def test_failed_staged_validation_preserves_previous_install(self):
        from unittest.mock import patch
        sys.path.insert(0, str(HOST.parent))
        try:
            from install_host import make_installer
            with TemporaryDirectory() as temp:
                directory = Path(temp)
                installed = directory / "media-delivery.pyz"
                installed.write_bytes(b"last known usable")
                with patch("install_host.subprocess.run") as run:
                    run.return_value.returncode = 1
                    result = make_installer(directory).apply({"check_tools": False})
                self.assertEqual(result["status"], "failed")
                self.assertLess(result["progress"], 100)
                self.assertEqual(installed.read_bytes(), b"last known usable")
                self.assertEqual(list(directory.iterdir()), [installed])
        finally:
            sys.path.remove(str(HOST.parent))

    def test_cancellation_and_retry_wait_for_current_step(self):
        entered, release = threading.Event(), threading.Event()
        calls = []

        def first(choices):
            entered.set()
            if not release.wait(3):
                raise SetupError("Timed out")

        installer = Installer(title="Test", description="Test", destination="Test",
                              options=(Option("extra", "Extra", "Extra"),),
                              steps=(Step("first", "First", first),
                                     Step("extra", "Extra", lambda _: calls.append("extra"), "extra"),
                                     Step("last", "Last", lambda _: calls.append("last"))))
        session = _Session(installer)
        with self.assertRaises(ValueError):
            session.start({"extra": "true"})
        session.start({"extra": True})
        self.assertTrue(entered.wait(2))
        self.assertEqual(session.snapshot()["progress"], 0)
        with self.assertRaises(ValueError):
            session.start({})
        session.cancel()
        self.assertEqual(session.snapshot()["status"], "stopping")
        release.set()
        self.assertEqual(session.join()["status"], "cancelled")
        self.assertEqual(calls, [])
        session.start({"extra": False})
        self.assertEqual(session.join()["progress"], 100)
        self.assertEqual(calls, ["last"])

    def test_isolated_consumer_transport_and_failure(self):
        with TemporaryDirectory() as temp:
            isolated = Path(temp)
            for filename in ("installer_bootstrap.py", "installer.html", "installer.js"):
                shutil.copy2(CAPABILITY / filename, isolated / filename)
            adapter = isolated / "consumer.py"
            adapter.write_text(
                "from installer_bootstrap import Installer, Option, SetupError, Step\n"
                "def write(choices):\n"
                "    if not choices['include']:\n"
                "        raise SetupError('Choose Include to continue.')\n"
                "    from pathlib import Path\n"
                "    Path('installed').write_text('complete')\n"
                "raise SystemExit(Installer(title='Isolated', description='Test', destination='local',\n"
                "    options=(Option('include', 'Include', 'Required by adapter'),),\n"
                "    steps=(Step('write', 'Write result', write),)).show(open_browser=False))\n",
                encoding="utf-8",
            )
            with subprocess.Popen([sys.executable, str(adapter)], cwd=isolated, stdout=subprocess.PIPE,
                                  text=True) as process:
                try:
                    url = process.stdout.readline().strip().rsplit(" ", 1)[-1]
                    origin = "/".join(url.split("/")[:3])

                    def request(endpoint, payload=None, source=origin):
                        data = None if payload is None else json.dumps(payload).encode()
                        with urlopen(Request(url + endpoint, data=data, headers={
                            "Origin": source, "Content-Type": "application/json"
                        }), timeout=3) as response:
                            return response.read()

                    def wait_for(status):
                        for _ in range(40):
                            state = json.loads(request("state"))
                            if state["status"] == status:
                                return state
                            time.sleep(0.025)
                        self.fail(f"Expected {status}, got {state}")

                    self.assertIn(b"Customize setup", request(""))
                    self.assertIn(b"installer-bootstrap/v1", request("state"))
                    with self.assertRaises(HTTPError) as denied:
                        request("start", {}, "https://example.com")
                    self.assertEqual(denied.exception.code, 403)
                    self.assertFalse((isolated / "installed").exists())
                    request("start", {})
                    state = wait_for("failed")
                    self.assertEqual(state["steps"][0]["detail"], "Choose Include to continue.")
                    self.assertEqual(state["progress"], 0)
                    request("start", {"include": True})
                    self.assertEqual(wait_for("done")["progress"], 100)
                    self.assertEqual((isolated / "installed").read_text(), "complete")
                    request("close", {})
                    self.assertEqual(process.wait(3), 0)
                finally:
                    if process.poll() is None:
                        process.terminate()


if __name__ == "__main__":
    unittest.main()
