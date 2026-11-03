"""Draws the 4 VSTEP skill icons (white glyphs on transparent) used on the watch home tiles.

    ~/.venvs/adcreative/bin/python scripts/make-skill-icons.py [preview.png]

Writes watch/entry/src/main/js/MainAbility/common/images/{reading,listening,writing,speaking}.png
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "watch/entry/src/main/js/MainAbility/common/images"
SIZE = 64
N = 512  # drawing canvas, downsampled for anti-aliasing
WHITE = (255, 255, 255, 255)
CLEAR = (0, 0, 0, 0)
TILE_COLORS = {"reading": "#2c6bd3", "listening": "#7646c4", "writing": "#c96a14", "speaking": "#0f8478"}


def canvas():
    img = Image.new("RGBA", (N, N), CLEAR)
    return img, ImageDraw.Draw(img)


def reading():
    img, d = canvas()
    d.polygon([(48, 140), (240, 176), (240, 420), (48, 384)], fill=WHITE)    # left page
    d.polygon([(272, 176), (464, 140), (464, 384), (272, 420)], fill=WHITE)  # right page
    for i in range(3):  # text lines cut out of the pages
        y = 230 + i * 60
        d.line([(90, y - 8), (205, y + 14)], fill=CLEAR, width=22)
        d.line([(307, y + 14), (422, y - 8)], fill=CLEAR, width=22)
    return img


def listening():
    img, d = canvas()
    d.arc((90, 70, 422, 440), start=180, end=360, fill=WHITE, width=44)       # headband
    d.rectangle((90, 250, 134, 300), fill=WHITE)                              # band ends down to the cups
    d.rectangle((378, 250, 422, 300), fill=WHITE)
    d.rounded_rectangle((62, 270, 172, 440), radius=34, fill=WHITE)           # ear cups
    d.rounded_rectangle((340, 270, 450, 440), radius=34, fill=WHITE)
    return img


def writing():
    img, d = canvas()
    d.rounded_rectangle((20, 196, 100, 316), radius=24, fill=WHITE)           # eraser
    d.rectangle((122, 196, 400, 316), fill=WHITE)                             # body
    d.polygon([(416, 196), (416, 316), (500, 256)], fill=WHITE)               # tip
    return img.rotate(40, resample=Image.BICUBIC, center=(N / 2, N / 2))


def speaking():
    img, d = canvas()
    d.rounded_rectangle((56, 86, 456, 356), radius=80, fill=WHITE)            # bubble
    d.polygon([(132, 330), (110, 448), (236, 348)], fill=WHITE)               # tail
    for x in (166, 256, 346):                                                 # dots cut out
        d.ellipse((x - 28, 193, x + 28, 249), fill=CLEAR)
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    icons = {"reading": reading(), "listening": listening(), "writing": writing(), "speaking": speaking()}
    for name, big in icons.items():
        big.resize((SIZE, SIZE), Image.LANCZOS).save(OUT / f"{name}.png", optimize=True)
        print(f"wrote {OUT / name}.png ({SIZE}x{SIZE})")
    if len(sys.argv) > 1:  # preview: icons on their tile colours, actual size and 3x
        pv = Image.new("RGBA", (4 * 170, 330), (0, 0, 0, 255))
        d = ImageDraw.Draw(pv)
        for i, name in enumerate(icons):
            x = i * 170 + 15
            d.rounded_rectangle((x, 10, x + 140, 149), radius=32, fill=TILE_COLORS[name])
            pv.alpha_composite(Image.open(OUT / f"{name}.png"), (x + 38, 30))
            d.rounded_rectangle((x - 5, 165, x + 145, 315), radius=20, fill=TILE_COLORS[name])
            pv.alpha_composite(Image.open(OUT / f"{name}.png").resize((144, 144), Image.NEAREST), (x - 2, 168))
        pv.save(sys.argv[1])
        print(f"preview {sys.argv[1]}")


if __name__ == "__main__":
    main()
