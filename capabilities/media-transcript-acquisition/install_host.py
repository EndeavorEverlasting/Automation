"""Media Delivery adapter for Automation's installer-bootstrap/v1."""
from __future__ import annotations

from io import BytesIO
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

from host_app import doctor

SOURCE = Path(__file__).resolve().parent
sys.path.insert(0, str(SOURCE.parent / "installer-bootstrap"))
from installer_bootstrap import CompletionAction, Installer, Option, SetupError, Step, StepWarning


PAYLOAD = (
    "host_app.py", "deliver_artifact.py", "acquire.py", "social_insights.py",
    "adapters/yt_dlp_social.py", "adapters/ollama_local.py", "adapters/ffmpeg_files.py",
)


def default_install_dir() -> Path:
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "Automation" / "MediaDelivery"
    return Path.home() / ".local" / "share" / "automation" / "media-delivery"


def doctor_command(target: Path) -> str:
    if sys.platform == "win32":
        # The Windows host instructions use PowerShell. Single quotes keep paths literal.
        return "& '" + sys.executable.replace("'", "''") + "' '" + str(target).replace("'", "''") + "' doctor"
    return shlex.join([sys.executable, str(target), "doctor"])


def make_installer(destination: Path) -> Installer:
    target = destination.expanduser().resolve() / "media-delivery.pyz"

    def check_sources(_choices):
        if any(not (SOURCE / name).is_file() for name in PAYLOAD):
            raise SetupError("Some application files are missing. Restore the Automation checkout and retry.")

    def check_tools(_choices):
        status = doctor()
        missing = [label for key, label in (("yt_dlp", "yt-dlp"), ("ffmpeg", "FFmpeg"))
                   if not status[key]["available"]]
        if missing:
            return StepWarning("Install " + " and ".join(missing) + " before capturing media.")
        return "Capture tools are available."

    def package_and_install(choices):
        mode = "audio" if choices["prefer_audio"] else "video"
        package = BytesIO()
        with ZipFile(package, "w", compression=ZIP_DEFLATED) as archive:
            for name in PAYLOAD:
                archive.writestr(name, (SOURCE / name).read_bytes())
            archive.writestr("adapters/__init__.py", "")
            archive.writestr("__main__.py",
                             f"from host_app import main\nraise SystemExit(main(default_mode={mode!r}, installed=True))\n")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".setup-", dir=target.parent) as stage:
                built = Path(stage) / target.name
                built.write_bytes(package.getvalue())
                # A staged artifact must run independently of the checkout before promotion.
                check = subprocess.run([sys.executable, "-I", str(built), "--help"],
                                       cwd=stage, capture_output=True, timeout=20)
                if check.returncode or b"doctor" not in check.stdout:
                    raise SetupError("The packaged launcher failed its check. The previous install is intact.")
                os.replace(built, target)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SetupError("Could not install in this folder. Check it is writable and retry.") from exc
        return "Run with Python 3.11 or later."

    return Installer(
        title="Media Delivery",
        description="Install the local command-line app and choose how it starts.",
        destination=str(target),
        options=(
            Option("prefer_audio", "Prefer audio capture",
                   "Guided and command-line capture start in audio mode. You can still choose video or both."),
            Option("check_tools", "Check capture tools",
                   "Report whether yt-dlp and FFmpeg are available on this computer.", default=True),
        ),
        steps=(
            Step("source", "Check application files", check_sources),
            Step("tools", "Check capture tools", check_tools, option="check_tools"),
            Step("install", "Verify and install the local launcher", package_and_install),
        ),
        readiness_step="tools",
        completion_action=CompletionAction("Run the installed app’s dependency check", doctor_command(target)),
    )


def setup(args) -> int:
    installer = make_installer(args.install_dir or default_install_dir())
    choices = {"prefer_audio": args.prefer_audio, "check_tools": not args.skip_tool_check}
    if args.plan:
        print(json.dumps(installer.plan(choices), indent=2))
        return 0
    if args.apply:
        result = installer.apply(choices)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "done" else 2
    return installer.show(open_browser=not args.no_open)
