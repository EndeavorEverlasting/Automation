#!/usr/bin/env python3
"""Opt-in isolated Playwright screenshot capture; never semantic or click authority."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path
from urllib.parse import urlsplit

CONTRACT = "automation.browser-visual-capture/v1"
ENGINE = "playwright-chromium-isolated/v1"
ALIAS_RE = re.compile(r"^[A-Za-z0-9_-]{1,48}$")


class CaptureError(Exception):
    def __init__(self, status: str):
        self.status = status
        super().__init__(status)


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def origin_for(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise CaptureError("INVALID_SOURCE")
    if parsed.username or parsed.password or parsed.fragment:
        raise CaptureError("INVALID_SOURCE")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise CaptureError("INVALID_SOURCE")
    try:
        port = parsed.port
    except ValueError as exc:
        raise CaptureError("INVALID_SOURCE") from exc
    default = 443 if parsed.scheme == "https" else 80
    return f"{parsed.scheme}://{parsed.hostname}" + (f":{port}" if port and port != default else "")


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as source:
        header = source.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise CaptureError("CAPTURE_INVALID")
    return struct.unpack(">II", header[16:24])


def admit(args: argparse.Namespace) -> tuple[str, str, Path | None]:
    if bool(args.source_html) == bool(args.url):
        raise CaptureError("INVALID_SOURCE")
    if args.privacy == "SYNTHETIC_PUBLIC" and args.url:
        raise CaptureError("PRIVACY_DENIED")
    if args.source_html:
        path = args.source_html.resolve(strict=True)
        if not path.is_file() or path.suffix.lower() not in {".html", ".htm"}:
            raise CaptureError("INVALID_SOURCE")
        return path.as_uri(), "local-html", path.parent
    origin = origin_for(args.url)
    if args.allow_origin != origin:
        raise CaptureError("ORIGIN_NOT_AUTHORIZED")
    return args.url, origin, None


def capture(args: argparse.Namespace) -> dict:
    source, origin, source_root = admit(args)
    outputs = [args.screenshot, args.receipt] + ([args.ax_out] if args.ax_out else [])
    if len({p.resolve() for p in outputs}) != len(outputs):
        raise CaptureError("OUTPUT_COLLISION")
    if any(p.exists() for p in outputs):
        raise CaptureError("OUTPUT_EXISTS")
    if any(not p.parent.is_dir() for p in outputs):
        raise CaptureError("OUTPUT_DIRECTORY_MISSING")
    if args.privacy == "SYNTHETIC_PUBLIC" and source_root:
        if any(p.resolve().is_relative_to(source_root.resolve()) for p in outputs):
            raise CaptureError("OUTPUT_IN_SOURCE_TREE")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise CaptureError("ENGINE_UNAVAILABLE") from exc

    blocked = 0
    with sync_playwright() as playwright:
        options = {"headless": True}
        if args.chromium_path:
            options["executable_path"] = str(args.chromium_path)
        try:
            browser = playwright.chromium.launch(**options)
        except Exception as exc:
            raise CaptureError("ENGINE_UNAVAILABLE") from exc
        try:
            context = browser.new_context(
                viewport={"width": args.width, "height": args.height},
                device_scale_factor=args.device_scale_factor,
                java_script_enabled=False,
                accept_downloads=False,
                service_workers="block",
                offline=source_root is not None,
            )
            page = context.new_page()

            def admit_request(route):
                nonlocal blocked
                allowed = False
                if source_root is None:
                    try:
                        allowed = origin_for(route.request.url) == origin
                    except CaptureError:
                        pass
                # Inline local fixture mode blocks ALL external/file subresources.
                if allowed:
                    route.continue_()
                else:
                    blocked += 1
                    route.abort()

            context.route("**/*", admit_request)
            try:
                if source_root is not None:
                    if args.source_html.stat().st_size > 4_000_000:
                        raise CaptureError("INVALID_SOURCE")
                    # Inline local fixture avoids unsafe file:// navigation and reads.
                    page.set_content(args.source_html.read_text(encoding="utf-8"),
                                     wait_until="load", timeout=args.timeout_ms)
                    response = None
                else:
                    response = page.goto(source, wait_until="load", timeout=args.timeout_ms)
                    if origin_for(page.url) != origin:
                        raise CaptureError("NAVIGATION_DENIED")
                if response is not None and response.status >= 400:
                    raise CaptureError("NAVIGATION_FAILED")
                page.screenshot(path=str(args.screenshot), full_page=False,
                                animations="disabled", caret="hide")
                if args.ax_out:
                    # Explicitly requested AX snapshot may contain private page text.
                    snapshot = page.locator("body").aria_snapshot(timeout=args.timeout_ms)
                    args.ax_out.write_text(snapshot, encoding="utf-8")
            except CaptureError:
                raise
            except Exception as exc:
                raise CaptureError("NAVIGATION_OR_CAPTURE_FAILED") from exc
            finally:
                context.close()
        finally:
            browser.close()
    width, height = png_dimensions(args.screenshot)
    return {
        "contract": CONTRACT, "engine": ENGINE, "status": "CAPTURED",
        "proof_ceiling": "ISOLATED_READ_ONLY_BROWSER_OBSERVATION",
        "semantic_verdict": "NOT_EVALUATED", "privacy": args.privacy,
        "source_kind": "LOCAL_HTML" if source_root else "EXPLICIT_ORIGIN",
        "origin_sha256": hashlib.sha256(origin.encode("utf-8")).hexdigest(),
        "host_alias": args.host_alias,
        "viewport": {"width": args.width, "height": args.height},
        "device_scale_factor": args.device_scale_factor,
        "image": {"sha256": hash_file(args.screenshot), "width": width, "height": height},
        "accessibility": "LOCAL_FILE_WRITTEN" if args.ax_out else "NOT_CAPTURED",
        "cross_origin_requests_blocked": blocked,
        "navigation_scripts": "DISABLED",
        "action_authority": "NONE",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-html", type=Path)
    source.add_argument("--url")
    parser.add_argument("--allow-origin", help="Exact scheme/host/port required for --url")
    parser.add_argument("--privacy", required=True, choices=["SYNTHETIC_PUBLIC", "PRIVATE_LOCAL_ONLY"])
    parser.add_argument("--host-alias", required=True, help="Operator-provided non-identifying host alias")
    parser.add_argument("--screenshot", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--ax-out", type=Path, help="Opt-in private accessibility snapshot")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--device-scale-factor", type=float, default=1.0)
    parser.add_argument("--timeout-ms", type=int, default=10000)
    parser.add_argument("--chromium-path", type=Path)
    args = parser.parse_args(argv)
    if (not ALIAS_RE.fullmatch(args.host_alias) or not 1 <= args.width <= 4096
        or not 1 <= args.height <= 4096 or not 0.5 <= args.device_scale_factor <= 3.0
        or not 100 <= args.timeout_ms <= 30000):
        parser.error("invalid host alias, viewport, scale or timeout")
    try:
        result = capture(args)
    except (OSError, ValueError):
        result = {"contract": CONTRACT, "engine": ENGINE, "status": "INVALID_SOURCE",
                  "proof_ceiling": "NONE", "semantic_verdict": "NOT_EVALUATED"}
    except CaptureError as exc:
        result = {"contract": CONTRACT, "engine": ENGINE, "status": exc.status,
                  "proof_ceiling": "NONE", "semantic_verdict": "NOT_EVALUATED"}
    if args.receipt.parent.is_dir() and not args.receipt.exists() and args.receipt.resolve() != args.screenshot.resolve():
        args.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"contract": CONTRACT, "status": result["status"]}, sort_keys=True))
    return 0 if result["status"] == "CAPTURED" else 2


if __name__ == "__main__":
    sys.exit(main())
