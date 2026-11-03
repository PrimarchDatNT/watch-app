"""Draws the AppNote icon (dark theme, green): a dark round badge with a thin green ring and a green
note sheet (folded corner, ruled lines) — green = the VSTEP site's dark-mode accent #5ac887.
Renders at 1024 px and downsamples (anti-aliasing). Writes the same icon for both apps:
  watch  watch/entry/src/main/resources/base/media/icon(.png|_small.png)
  phone  phone/app/src/main/res: adaptive launcher icon (dark background colour + the badge as
         foreground + a monochrome layer for Android 13 themed icons), 5 densities

    ~/.venvs/adcreative/bin/python scripts/make-icon.py [preview.png]
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "watch/entry/src/main/resources/base/media"
SIZES = {"icon.png": 104, "icon_small.png": 92}

N = 1024
BG_TOP = (40, 44, 42)          # dark, a touch lighter at the top
BG_BOTTOM = (22, 24, 23)
GREEN = (90, 200, 135, 255)    # #5ac887
FOLD = (169, 231, 193, 255)    # light green back of the folded corner
INK = (28, 31, 30, 255)        # ruled lines, same dark as the badge
RING = int(N * 0.035)          # green ring so the dark badge stands out on the watch's black UI


def badge() -> Image.Image:
    grad = Image.new("RGBA", (N, N))
    px = grad.load()
    for y in range(N):
        t = y / (N - 1)
        c = tuple(round(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)) + (255,)
        for x in range(N):
            px[x, y] = c
    mask = Image.new("L", (N, N), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, N - 1, N - 1), fill=255)
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    ImageDraw.Draw(img).ellipse((RING // 2, RING // 2, N - 1 - RING // 2, N - 1 - RING // 2), outline=GREEN, width=RING)
    return img


def draw_note(img: Image.Image) -> None:
    left, top = int(N * 0.30), int(N * 0.22)
    right, bottom = int(N * 0.70), int(N * 0.78)
    radius, fold = int(N * 0.05), int(N * 0.13)
    sheet = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(sheet)
    d.rounded_rectangle((left, top, right, bottom), radius=radius, fill=GREEN)
    cut = Image.new("L", (N, N), 255)                      # cut the top-right corner, then draw the flap
    ImageDraw.Draw(cut).polygon([(right - fold, top - 2), (right + 2, top - 2), (right + 2, top + fold)], fill=0)
    sheet.putalpha(Image.composite(sheet.getchannel("A"), Image.new("L", (N, N), 0), cut))
    d = ImageDraw.Draw(sheet)
    d.polygon([(right - fold, top), (right - fold, top + fold), (right, top + fold)], fill=FOLD)
    line_h = int(N * 0.045)
    x0, full = left + int(N * 0.07), right - int(N * 0.07)
    ys = [0.40, 0.50, 0.60, 0.70]
    for i, fy in enumerate(ys):
        y = int(N * fy)
        x1 = full if i < len(ys) - 1 else x0 + int((full - x0) * 0.55)
        d.rounded_rectangle((x0, y, x1, y + line_h), radius=line_h // 2, fill=INK)
    img.alpha_composite(sheet)


PHONE_RES = ROOT / "phone/app/src/main/res"
DENSITIES = {"mdpi": 1.0, "hdpi": 1.5, "xhdpi": 2.0, "xxhdpi": 3.0, "xxxhdpi": 4.0}
ADAPTIVE_DP = 108        # adaptive icon layer size
BADGE_DP = 68            # badge diameter inside it: within the 72dp visible mask, clear of the 66dp safe zone's edge
BACKGROUND = "#1F2221"   # badge's mid tone, fills the mask around the badge


def monochrome() -> Image.Image:
    """White ring + note (lines and fold cut out) on transparent: Android themed icons use only alpha."""
    white = (255, 255, 255, 255)
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((RING // 2, RING // 2, N - 1 - RING // 2, N - 1 - RING // 2), outline=white, width=RING)
    note = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    draw_note(note)
    alpha = note.getchannel("A")
    rgb = note.convert("RGB").load()
    a = alpha.load()
    for y in range(N):           # keep only the green sheet; drop the dark ruled lines and the light fold
        for x in range(N):
            if a[x, y] and rgb[x, y][1] < 150 or a[x, y] and rgb[x, y][0] > 140:
                a[x, y] = 0
    img.alpha_composite(Image.merge("RGBA", (*Image.new("RGB", (N, N), (255, 255, 255)).split(), alpha)))
    return img


def write_android(master: Image.Image) -> None:
    mono = monochrome()
    for density, scale in DENSITIES.items():
        px = round(ADAPTIVE_DP * scale)
        inner = round(BADGE_DP * scale)
        folder = PHONE_RES / f"mipmap-{density}"
        folder.mkdir(parents=True, exist_ok=True)
        for name, src in (("ic_launcher_foreground.png", master), ("ic_launcher_monochrome.png", mono)):
            layer = Image.new("RGBA", (px, px), (0, 0, 0, 0))
            layer.alpha_composite(src.resize((inner, inner), Image.LANCZOS), ((px - inner) // 2, (px - inner) // 2))
            layer.save(folder / name, optimize=True)
        print(f"wrote {folder}/ic_launcher_foreground.png + _monochrome.png ({px}x{px})")
    anydpi = PHONE_RES / "mipmap-anydpi-v26"
    anydpi.mkdir(parents=True, exist_ok=True)
    xml = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<!-- generated by scripts/make-icon.py -->\n'
           '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
           '    <background android:drawable="@color/ic_launcher_background" />\n'
           '    <foreground android:drawable="@mipmap/ic_launcher_foreground" />\n'
           '    <monochrome android:drawable="@mipmap/ic_launcher_monochrome" />\n'
           '</adaptive-icon>\n')
    for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
        (anydpi / name).write_text(xml, encoding="utf-8")
    (PHONE_RES / "values" / "ic_launcher_background.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<!-- generated by scripts/make-icon.py -->\n'
        f'<resources>\n    <color name="ic_launcher_background">{BACKGROUND}</color>\n</resources>\n',
        encoding="utf-8")
    print(f"wrote {anydpi}/ic_launcher(.xml|_round.xml) + values/ic_launcher_background.xml")


def main() -> None:
    master = badge()
    draw_note(master)
    for name, size in SIZES.items():
        master.resize((size, size), Image.LANCZOS).save(MEDIA / name, optimize=True)
        print(f"wrote {MEDIA / name} ({size}x{size})")
    write_android(master)
    if len(sys.argv) > 1:
        # preview: actual sizes on black (watch UI) and on light grey, plus a larger render
        icon = Image.open(MEDIA / "icon.png")
        small = Image.open(MEDIA / "icon_small.png")
        pv = Image.new("RGBA", (760, 440), (0, 0, 0, 255))
        ImageDraw.Draw(pv).rectangle((380, 0, 760, 440), fill=(225, 225, 225, 255))
        for ox in (0, 380):
            pv.alpha_composite(icon, (ox + 40, 40))
            pv.alpha_composite(small, (ox + 180, 46))
        pv.alpha_composite(icon.resize((208, 208), Image.NEAREST), (86, 200))
        pv.alpha_composite(master.resize((208, 208), Image.LANCZOS), (466, 200))
        pv.save(sys.argv[1])
        print(f"preview {sys.argv[1]}")


if __name__ == "__main__":
    main()
