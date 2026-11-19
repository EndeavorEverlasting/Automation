"""Automation's installer-bootstrap/v1 interface for trusted local adapters."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import threading
import time
from typing import Callable
import webbrowser


CONTRACT = "installer-bootstrap/v1"


@dataclass(frozen=True)
class Option:
    id: str
    label: str
    description: str
    default: bool = False


@dataclass(frozen=True)
class Step:
    id: str
    label: str
    run: Callable[[dict[str, bool]], str | None]
    option: str | None = None


class SetupError(Exception):
    """An adapter's actionable, display-safe failure message."""


class Installer:
    def __init__(self, *, title: str, description: str, destination: str,
                 options: tuple[Option, ...], steps: tuple[Step, ...]):
        self.title = title
        self.description = description
        self.destination = destination
        self.options = options
        self.steps = steps
        self.defaults = {option.id: option.default for option in options}
        for items in (options, steps):
            ids = {item.id for item in items}
            if len(ids) != len(items) or any(not re.fullmatch(r"[a-z][a-z0-9_-]*", key) for key in ids):
                raise ValueError("Option and step IDs must be unique stable slugs.")
        if not any(step.option is None for step in steps):
            raise ValueError("At least one step must be required.")
        if any(step.option is not None and step.option not in self.defaults for step in steps):
            raise ValueError("Step references an unknown option.")

    def choices(self, overrides: dict[str, bool]) -> dict[str, bool]:
        if not isinstance(overrides, dict) or any(
            key not in self.defaults or type(value) is not bool for key, value in overrides.items()
        ):
            raise ValueError("Only declared boolean options are accepted.")
        return self.defaults | overrides

    def plan(self, overrides: dict[str, bool]) -> dict:
        choices = self.choices(overrides)
        return {
            "contract": CONTRACT,
            "title": self.title,
            "description": self.description,
            "destination": self.destination,
            "options": [asdict(option) for option in self.options],
            "choices": choices,
            "status": "review",
            "progress": 0,
            "steps": [
                {"id": step.id, "label": step.label, "state": (
                    "pending" if step.option is None or choices[step.option] else "skipped"
                ), "detail": None}
                for step in self.steps
            ],
        }

    def apply(self, overrides: dict[str, bool]) -> dict:
        session = _Session(self)
        session.start(overrides)
        return session.join()

    def show(self, *, open_browser: bool = True) -> int:
        return _serve(self, open_browser)


class _Session:
    def __init__(self, installer: Installer):
        self.installer = installer
        self.lock = threading.Lock()
        self.cancel_requested = False
        self.state = installer.plan({})
        self.worker = None

    def snapshot(self) -> dict:
        with self.lock:
            return self.state | {"steps": [row.copy() for row in self.state["steps"]]}

    def start(self, overrides: dict[str, bool]) -> None:
        with self.lock:
            if self.state["status"] not in {"review", "failed", "cancelled"}:
                raise ValueError("This installation attempt cannot be started again.")
            self.state = self.installer.plan(overrides)
            self.state["status"] = "running"
            self.cancel_requested = False
            self.worker = threading.Thread(target=self._run)
            self.worker.start()

    def cancel(self) -> None:
        with self.lock:
            if self.state["status"] == "running":
                self.cancel_requested = True
                self.state["status"] = "stopping"

    def join(self) -> dict:
        if self.worker:
            self.worker.join()
        return self.snapshot()

    def _run(self) -> None:
        rows = self.state["steps"]
        active = [(step, row) for step, row in zip(self.installer.steps, rows)
                  if row["state"] == "pending"]
        for index, (step, row) in enumerate(active, 1):
            with self.lock:
                if self.cancel_requested:
                    self.state["status"] = "cancelled"
                    return
                row["state"] = "running"
            try:
                detail = step.run(self.state["choices"].copy())
            except Exception as exc:
                with self.lock:
                    row.update(state="failed", detail=(
                        str(exc) if isinstance(exc, SetupError) else "Setup could not complete this step."
                    ))
                    self.state["status"] = "failed"
                return
            with self.lock:
                row.update(state="done", detail=detail)
                self.state["progress"] = 100 * index // len(active)
                if index == len(active):
                    self.state["status"] = "done"


def _serve(installer: Installer, open_browser: bool) -> int:
    """Serve one loopback-only window with a capability URL and same-origin writes."""
    session = _Session(installer)
    prefix = "/" + secrets.token_urlsafe(24) + "/"
    assets = Path(__file__).resolve().parent
    files = {
        "": ("text/html; charset=utf-8", (assets / "installer.html").read_bytes()),
        "installer.js": ("text/javascript; charset=utf-8", (assets / "installer.js").read_bytes()),
    }
    last_seen = time.monotonic()
    closed = threading.Event()
    control = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            return  # Never echo the session URL to access logs.

        def send_payload(self, status, mime, content):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; "
                             "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(content)

        def json_response(self, status, data):
            self.send_payload(status, "application/json", json.dumps(data).encode())

        def allowed(self):
            return self.headers.get("Host") == authority and self.path.startswith(prefix)

        def do_GET(self):
            nonlocal last_seen
            if not self.allowed():
                self.json_response(404, {"error": "Unknown setup session."})
                return
            last_seen = time.monotonic()
            endpoint = self.path[len(prefix):]
            if endpoint == "state":
                self.json_response(200, session.snapshot())
            elif endpoint in files:
                self.send_payload(200, *files[endpoint])
            else:
                self.json_response(404, {"error": "Unknown setup page."})

        def do_POST(self):
            nonlocal last_seen
            if not self.allowed() or self.headers.get("Origin") != origin:
                self.json_response(403, {"error": "Setup requires a request from its own window."})
                return
            last_seen = time.monotonic()
            endpoint = self.path[len(prefix):]
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192 or self.headers.get_content_type() != "application/json":
                    raise ValueError("Expected a setup JSON request.")
                self.connection.settimeout(3)
                body = json.loads(self.rfile.read(length))
                with control:
                    if closed.is_set():
                        raise ValueError("This setup window is closed.")
                    if endpoint == "start":
                        session.start(body)
                    elif endpoint == "cancel":
                        session.cancel()
                    elif endpoint == "close":
                        if session.snapshot()["status"] in {"running", "stopping"}:
                            raise ValueError("Stop setup and wait for the current step first.")
                        self.json_response(200, session.snapshot())
                        closed.set()
                        return
                    else:
                        self.json_response(404, {"error": "Unknown setup action."})
                        return
            except (ValueError, OSError) as exc:
                self.json_response(400, {"error": str(exc)})
                return
            self.json_response(200, session.snapshot())

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        authority = f"127.0.0.1:{server.server_port}"
        origin = f"http://{authority}"
        url = origin + prefix
        print("Open setup in your browser at " + url, flush=True)
        if open_browser:
            threading.Thread(target=webbrowser.open, args=(url,),
                             kwargs={"new": 1}, daemon=True).start()
        server.timeout = 0.25
        try:
            while not closed.is_set() and time.monotonic() - last_seen < 900:
                server.handle_request()
        except KeyboardInterrupt:
            session.cancel()
        finally:
            session.cancel()
            result = session.join()
    return {"done": 0, "review": 0, "cancelled": 130}.get(result["status"], 2)
