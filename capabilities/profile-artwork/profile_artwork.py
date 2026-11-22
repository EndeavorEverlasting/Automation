#!/usr/bin/env python3
"""Build, verify and restore artwork for a GitHub profile README."""
from argparse import ArgumentParser
from contextlib import contextmanager
from hashlib import sha256
from html import escape
from html.parser import HTMLParser
from io import BytesIO
import json
from math import pi, sin, tau
from pathlib import Path
from random import Random
import re
from shutil import rmtree
from tempfile import NamedTemporaryFile, TemporaryDirectory
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

SCHEMA = "profile-artwork/v1"
CONFIG = "profile-artwork.json"
ARCHIVE = "assets/profile-artwork"
SCENES = ("stitch-descent", "stitch-resume", "stitch-pulse")
FILES = tuple(f"{scene}.{kind}" for scene in SCENES for kind in ("gif", "png"))
RELEASE = re.compile(r"v(?:0[1-9]|[1-9][0-9]+)")
ACCOUNT = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")
COLOR = re.compile(r"#[0-9A-Fa-f]{6}")
GITHUB = "https://github.com/"
BUDGET = 250_000
ALT = (
    "Two colored filaments carry light downward.",
    "The colored filaments continue downward through a second field.",
    "Explore the projects and find ways to collaborate.",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def repo_path(root, path):
    full = root / path
    require(full.resolve() == full, f"Symlinked output path: {path}.")
    return full


def write_atomic(path, data):
    temp = None
    try:
        with NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temp = Path(handle.name)
            handle.write(data)
        temp.replace(path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


@contextmanager
def editing(root):
    lock = repo_path(root, ".profile-artwork.lock")
    try:
        with lock.open("x"):
            pass
    except FileExistsError as error:
        raise ValueError("Another artwork edit is active. Inspect .profile-artwork.lock.") from error
    try:
        yield
    finally:
        lock.unlink()


def validate_config(config):
    require(isinstance(config, dict) and config.get("schema") == SCHEMA, f"Invalid {CONFIG}.")
    account = config.get("account", "")
    require(isinstance(account, str) and len(account) <= 39 and ACCOUNT.fullmatch(account),
            "Use a valid GitHub profile login.")
    for key in ("title", "tagline"):
        value = config.get(key)
        require(isinstance(value, str) and 0 < len(value.strip()) <= 160
                and not any(ord(character) < 32 for character in value),
                f"Use a nonempty one-line {key} of at most 160 characters.")
    for key in ("cool", "warm"):
        require(isinstance(config.get(key), str) and COLOR.fullmatch(config[key]),
                f"{key} must be a #RRGGBB color.")
    return config


def configuration(root):
    return validate_config(json.loads(repo_path(root, CONFIG).read_bytes()))


def pillow():
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError as error:
        raise ValueError("Install Pillow with python -m pip install 'Pillow>=11,<14'.") from error
    return Image, ImageDraw, ImageFilter


def render(config, output):
    """Render all three panels from one vertical field and a fixed spatial seed."""
    Image, Draw, Filter = pillow()
    width, panel_height, count = 560, 212, 21
    height = panel_height * len(SCENES)
    background = (13, 17, 23)
    colors = [tuple(bytes.fromhex(config[key][1:])) for key in ("cool", "warm")]
    rng = Random(1181)
    plate = Image.new("RGB", (width, height), background)
    dust = Draw.Draw(plate)
    for _ in range(700):
        x, y = rng.randrange(width), rng.randrange(height)
        color = rng.choice(colors)
        strength = rng.uniform(.02, .16)
        dust.point((x, y), fill=tuple(round(b + (c - b) * strength) for b, c in zip(background, color)))

    def lane_x(lane, y):
        phase = y / height * tau
        return (width * (.43 + lane * .13) + 96 * sin(phase + lane * 1.3)
                + 38 * sin(phase * 2 - lane * .9))

    for lane, color in enumerate(colors):
        for _ in range(68):
            start, span = rng.randrange(-90, height), rng.randrange(45, 225)
            twist, phase = rng.uniform(-65, 65), rng.uniform(0, tau)
            opacity = rng.uniform(.08, .49)
            ink = tuple(round(b + (c - b) * opacity) for b, c in zip(background, color))
            points = []
            for index in range(38):
                u = index / 37
                y = start + u * span
                x = lane_x(lane, y) + twist * sin(pi * u) + 9 * sin(u * tau + phase)
                points.append((x, y))
            dust.line(points, fill=ink, width=1)

    for part, scene in enumerate(SCENES):
        offset = part * panel_height
        still = plate.crop((0, offset, width, offset + panel_height))
        still.save(output / f"{scene}.png", optimize=True)
        frames = []
        for index in range(count):
            frame = still.convert("RGBA")
            halo = Image.new("RGBA", still.size)
            glow = Draw.Draw(halo)
            cores = []
            for lane, color in enumerate(colors):
                phase = (index / count - lane * .12 - part * .14) % 1
                y = round(phase * (panel_height - 1))
                x = round(lane_x(lane, y + offset))
                strength = sin(pi * phase) ** .7
                glow.ellipse((x-13, y-13, x+13, y+13), fill=(*color, round(190 * strength)))
                cores.append((x, y, color, strength))
            halo = halo.filter(Filter.GaussianBlur(6))
            glow = Draw.Draw(halo)
            for x, y, color, strength in cores:
                glow.ellipse((x-3, y-3, x+3, y+3), fill=(*color, round(240 * strength)))
            frames.append(Image.alpha_composite(frame, halo).convert("RGB"))
        # Include lit frames in the common palette so their brightest tones survive encoding.
        strip = Image.new("RGB", (width, panel_height * 3))
        for i, image in enumerate((still, frames[7], frames[14])):
            strip.paste(image, (0, i * panel_height))
        palette = strip.quantize(colors=52)
        indexed = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
        indexed[0].save(output / f"{scene}.gif", save_all=True, append_images=indexed[1:],
                        optimize=True, duration=130, loop=0, disposal=1)


def check_media(assets):
    Image, _, _ = pillow()
    require(all(len(data) <= 4_000_000 for data in assets.values()),
            "Each artwork file must be under 4 MB.")
    require(sum(len(assets[f"{scene}.gif"]) for scene in SCENES) <= BUDGET,
            "The three GIFs exceed 250 kB combined.")
    for scene in SCENES:
        with Image.open(BytesIO(assets[f"{scene}.gif"])) as gif:
            require(gif.format == "GIF" and 1 < gif.n_frames <= 100
                    and gif.height * gif.width <= 1_500_000 and gif.height / gif.width >= .27,
                    f"{scene} must be an animated profile GIF of suitable dimensions.")
            size = gif.size
            total = 0
            for index in range(gif.n_frames):
                gif.seek(index)
                gif.load()
                delay = gif.info.get("duration", 0)
                require(delay >= 20, f"{scene} has an unsafe frame delay.")
                total += delay
            require(total <= 5000, f"{scene} exceeds five seconds per loop.")
        with Image.open(BytesIO(assets[f"{scene}.png"])) as poster:
            require(poster.format == "PNG" and poster.n_frames == 1 and poster.size == size,
                    f"{scene} needs a matching-size, static reduced-motion PNG.")
            poster.load()


def marker(scene, end):
    return f"<!-- profile-artwork:{scene}:{end} -->"


def block(scene, name, account):
    prefix = f"{ARCHIVE}/{name}/{scene}"
    img = (f'<picture>\n  <source media="(prefers-reduced-motion: reduce)" srcset="{prefix}.png" />\n'
           f'  <img src="{prefix}.gif" width="100%" alt="{ALT[SCENES.index(scene)]}" />\n</picture>')
    if scene == SCENES[-1]:
        img = f'<a href="{GITHUB}{account}?tab=repositories">\n{img}\n</a>'
    return f"{marker(scene, 'start')}\n{img}\n{marker(scene, 'end')}"


def block_span(text, scene):
    begin, end = (marker(scene, point) for point in ("start", "end"))
    require(text.count(begin) == text.count(end) == 1, f"Malformed README artwork block: {scene}.")
    low, high = text.index(begin), text.index(end)
    require(low < high and "profile-artwork:" not in text[low+len(begin):high],
            f"Overlapping README artwork block: {scene}.")
    return low, high + len(end)


def update_readme(text, name, account, *, starter=""):
    if "profile-artwork:" not in text:
        intro, continuation, footer = (block(scene, name, account) for scene in SCENES)
        body = text if text.strip() else starter
        return (f"{intro}\n\n{body}" + ("\n" if body.endswith("\n") else "\n\n")
                + f"{continuation}\n\n{footer}\n")
    for scene in SCENES:
        low, high = block_span(text, scene)
        text = text[:low] + block(scene, name, account) + text[high:]
    return text


def list_releases(root):
    archive = repo_path(root, ARCHIVE)
    if not archive.exists():
        return []
    return sorted((entry.name for entry in archive.iterdir() if RELEASE.fullmatch(entry.name)),
                  key=lambda name: int(name[1:]))


def read_release(root, name, account):
    require(RELEASE.fullmatch(name), "Use a release name such as v01.")
    directory = repo_path(root, f"{ARCHIVE}/{name}")
    manifest = json.loads(repo_path(root, f"{ARCHIVE}/{name}/release.json").read_bytes())
    require(isinstance(manifest, dict) and manifest.get("schema") == SCHEMA
            and manifest.get("version") == name and manifest.get("account") == account
            and set(manifest.get("sha256", {})) == set(FILES), f"Invalid manifest for {name}.")
    assets = {file: repo_path(root, f"{ARCHIVE}/{name}/{file}").read_bytes() for file in FILES}
    require(all(sha256(content).hexdigest() == manifest["sha256"][file]
                for file, content in assets.items()), f"{directory.name} artwork bytes changed.")
    check_media(assets)
    return assets


def active_release(root, account):
    text = repo_path(root, "README.md").read_bytes().decode("utf-8").replace("\r\n", "\n")
    start, end = block_span(text, SCENES[0])
    match = re.search(rf'src="{re.escape(ARCHIVE)}/(v[0-9]+)/{SCENES[0]}\.gif"', text[start:end])
    require(match, "README does not select an artwork release.")
    name = match.group(1)
    require(update_readme(text, name, account) == text and
            [text.index(marker(scene, "start")) for scene in SCENES] ==
            sorted(text.index(marker(scene, "start")) for scene in SCENES),
            "README contains mixed releases, incomplete markup or misplaced panels.")
    return name


def http_read(url):
    request = Request(url, headers={"User-Agent": "ProfileArtwork/1.0", "Cache-Control": "no-cache"})
    with urlopen(request, timeout=12) as response:
        content = response.read(4_000_001)
    require(len(content) <= 4_000_000, "GitHub response exceeded the read limit.")
    return content


class PublishedArtwork(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.article = []
        self.link = None
        self.picture = None
        self.images = []
        self.hidden = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "article":
            self.article.append("markdown-body" in (attrs.get("class") or "").split())
        if self.hidden:
            if tag == self.hidden[-1]:
                self.hidden.append(tag)
            return
        style = re.sub(r"\s+", "", (attrs.get("style") or "").lower())
        if ("hidden" in attrs or "display:none" in style or "visibility:hidden" in style
                or tag in ("code", "template") or (tag == "details" and "open" not in attrs)):
            if tag not in ("img", "source", "input", "br", "hr", "link", "meta"):
                self.hidden.append(tag)
            return
        if any(self.article):
            if tag == "a":
                self.link = attrs.get("href")
            elif tag == "picture":
                self.picture = []
            elif (tag == "source" and self.picture is not None
                  and attrs.get("media") == "(prefers-reduced-motion: reduce)"):
                self.picture.append(attrs.get("srcset"))
            elif tag == "img":
                self.images.append((attrs, self.link, tuple(self.picture or ())))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.hidden and self.hidden[-1] == tag:
            self.hidden.pop()
        if tag == "a":
            self.link = None
        if tag == "picture":
            self.picture = None
        if tag == "article" and self.article:
            self.article.pop()


def verify_public(account, name, assets):
    profile_url = GITHUB + account
    page = PublishedArtwork(http_read(profile_url).decode("utf-8"))
    prefix = f"/{ARCHIVE}/{name}/"
    images = [(image, href, stills) for image, href, stills in page.images
              if f"/{ARCHIVE}/" in (image.get("src") or "")]
    require(len(images) == len(SCENES), "Public profile shows the wrong artwork layout.")
    for i, (scene, (image, href, stills)) in enumerate(zip(SCENES, images)):
        require(image.get("alt") == ALT[i] and image.get("width") == "100%" and len(stills) == 1,
                "Public image is missing accessibility or responsive markup.")
        if scene == SCENES[-1]:
            require(urljoin(profile_url, href or "") == profile_url + "?tab=repositories",
                    "Public footer link does not open repositories.")
        for suffix, src in (("gif", image.get("src")), ("png", stills[0])):
            filename = f"{scene}.{suffix}"
            url = urljoin(profile_url, src or "")
            parts = urlsplit(url)
            qualified = f"/{account}/{account}/".casefold()
            require(parts.scheme == "https" and parts.netloc in ("github.com", "raw.githubusercontent.com")
                    and parts.path.casefold().startswith(qualified)
                    and parts.path.endswith(prefix + filename)
                    and (parts.netloc != "github.com" or parts.path[len(qualified):].startswith("raw/")),
                    f"Public {filename} is not from the selected release.")
            require(http_read(url) == assets[filename], f"Public {filename} bytes differ.")
    return profile_url


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Target profile checkout.")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create editable profile settings.")
    for key in ("account", "title", "tagline"):
        init.add_argument(f"--{key}", required=True)
    init.add_argument("--cool", default="#58c4ed")
    init.add_argument("--warm", default="#f2a461")
    build = commands.add_parser("build", help="Generate and select the next immutable release.")
    build.add_argument("--from-assets", type=Path, help="Use six previously generated GIF/PNG files.")
    verify = commands.add_parser("verify", help="Verify local release with optional public readback.")
    verify.add_argument("--live", action="store_true")
    commands.add_parser("status", help="Report the selected release and rollback candidates.")
    restore = commands.add_parser("restore", help="Select an older release and preserve the README prose.")
    restore.add_argument("version")
    args = parser.parse_args()
    root = args.repo.resolve()
    try:
        require(root.is_dir(), "Target checkout directory must exist.")
        command = args.command
        if command == "init":
            keys = ("account", "title", "tagline", "cool", "warm")
            config = validate_config({"schema": SCHEMA, **{key: getattr(args, key) for key in keys}})
            with editing(root):
                file = repo_path(root, CONFIG)
                require(not file.exists(), f"Edit the existing {CONFIG}.")
                write_atomic(file, json_bytes(config))
            result = {"configured": True, "account": config["account"]}
        elif command == "build":
            result = build_release(root, args.from_assets)
        elif command == "restore":
            result = restore_release(root, args.version)
        else:
            account = configuration(root)["account"]
            name = active_release(root, account)
            assets = read_release(root, name, account)
            result = {"active": name, "versions": list_releases(root), "verified": True}
            if command == "verify" and args.live:
                result["public_profile"] = verify_public(account, name, assets)
        print(json_bytes({"schema": SCHEMA, **result}).decode(), end="")
    except (KeyError, TypeError, ValueError, OSError, EOFError) as error:
        parser.exit(1, f"Profile artwork: {error}\n")


def build_release(root, source):
    with editing(root):
        config = configuration(root)
        account = config["account"]
        readme = repo_path(root, "README.md")
        old = readme.read_bytes() if readme.exists() else b""
        versions = list_releases(root)
        if versions:
            read_release(root, active_release(root, account), account)
        name = f"v{(int(versions[-1][1:]) if versions else 0) + 1:02d}"
        title = escape(config["title"])
        tagline = escape(config["tagline"])
        layout = update_readme(old.decode("utf-8"), name, account, starter=f"# {title}\n\n{tagline}\n")
        archive = repo_path(root, ARCHIVE)
        archive.mkdir(parents=True, exist_ok=True)
        final = repo_path(root, f"{ARCHIVE}/{name}")
        with TemporaryDirectory(dir=archive) as directory:
            staging = Path(directory) / name
            staging.mkdir()
            if source is None:
                render(config, staging)
            else:
                for file in FILES:
                    (staging / file).write_bytes((source / file).read_bytes())
            assets = {file: (staging / file).read_bytes() for file in FILES}
            check_media(assets)
            manifest = {"schema": SCHEMA, "version": name, "account": account,
                        "sha256": {file: sha256(data).hexdigest() for file, data in assets.items()}}
            (staging / "release.json").write_bytes(json_bytes(manifest))
            require(not final.exists(), f"{name} already exists.")
            staging.rename(final)
        try:
            require((readme.read_bytes() if readme.exists() else b"") == old,
                    "README changed during rendering. Retry from the current file.")
            write_atomic(readme, layout.encode("utf-8"))
        except (OSError, ValueError):
            rmtree(final)
            raise
    return {"active": name, "manifest": f"{ARCHIVE}/{name}/release.json"}


def restore_release(root, name):
    with editing(root):
        account = configuration(root)["account"]
        active_release(root, account)
        read_release(root, name, account)
        readme = repo_path(root, "README.md")
        before = readme.read_bytes()
        layout = update_readme(before.decode("utf-8"), name, account)
        require(readme.read_bytes() == before, "README changed during restore.")
        write_atomic(readme, layout.encode("utf-8"))
    return {"active": name}


if __name__ == "__main__":
    main()
