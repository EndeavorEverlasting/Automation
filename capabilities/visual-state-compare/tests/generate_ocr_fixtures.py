#!/usr/bin/env python3
"""Generate synthetic public OCR holdout PNGs (no private screenshots)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "fixtures" / "ocr"
FONT_CANDIDATES = (
    Path(r"C:\Windows\Fonts\arial.ttf"),
    Path(r"C:\Windows\Fonts\segoeui.ttf"),
    Path(r"C:\Windows\Fonts\DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
)


def load_font(size: int = 36):
    for candidate in FONT_CANDIDATES:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def render(path: Path, text: str, *, bg: tuple[int, int, int], fg: tuple[int, int, int], size=(720, 160)):
    image = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(image)
    font = load_font(36)
    draw.text((32, 56), text, fill=fg, font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main() -> None:
    render(OUT / "plain_serial.png", "SERIAL AB12-0O1I", bg=(255, 255, 255), fg=(0, 0, 0))
    render(OUT / "dark_dialog.png", "Confirm delete HOST-77", bg=(24, 24, 28), fg=(230, 230, 235))
    Image.new("RGB", (160, 100), (240, 240, 240)).save(OUT / "blank.png")
    print(f"wrote fixtures under {OUT}")


if __name__ == "__main__":
    main()
