"""Generate the Cat Orb item icons (drawn in code, so there is no art file to lose).

Outputs: <rp>/textures/items/cat_orb.png        16x16 empty orb: pale glass sphere with a gold band
         <rp>/textures/items/cat_orb_full.png   16x16 occupied orb: amber glow with a cat silhouette

Run standalone:  python tools/gen_orb.py
"""
from __future__ import annotations

import sys

from PIL import Image

from common import BuildError, load_config, rel

EMPTY_TEXTURE = "textures/items/cat_orb"
FULL_TEXTURE = "textures/items/cat_orb_full"

CX, CY, R = 7.5, 8.0, 6.6  # sphere centre and radius in pixels

# Sitting cat seen from the front, drawn inside the occupied orb (C = cat, E = eye).
CAT = [
    "................",
    "................",
    "................",
    "................",
    ".....C....C.....",
    ".....CC..CC.....",
    ".....CCCCCC.....",
    ".....CECCEC.....",
    ".....CCCCCC.....",
    "......CCCC......",
    ".....CCCCCC.....",
    ".....CCCCCCC....",
    ".....CCCCCC.C...",
    "................",
    "................",
    "................",
]


def _lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _orb(inner_dark, inner_light, alpha) -> Image.Image:
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    outline = (36, 30, 54, 255)
    gold, gold_hi = (214, 160, 52, 255), (255, 222, 120, 255)
    for y in range(16):
        for x in range(16):
            dx, dy = x + 0.5 - CX - 0.5, y + 0.5 - CY
            d = (dx * dx + dy * dy) ** 0.5
            if d > R + 0.5:
                continue
            if d > R - 0.7:
                im.putpixel((x, y), outline)
                continue
            # light from the top-left
            t = max(0.0, min(1.0, 0.5 + (-dx - dy) / (2.2 * R)))
            c = _lerp(inner_dark, inner_light, t)
            im.putpixel((x, y), (*c, alpha))
    # gold band around the middle, slightly curved
    for x in range(16):
        for y in (8, 9):
            if im.getpixel((x, y))[3] and im.getpixel((x, y))[:3] != outline[:3]:
                im.putpixel((x, y), gold_hi if y == 8 and 4 <= x <= 8 else gold)
    # specular highlight
    for x, y in ((4, 4), (5, 4), (4, 5), (5, 3)):
        im.putpixel((x, y), (255, 255, 255, 255))
    return im


def _empty() -> Image.Image:
    return _orb((120, 176, 214), (220, 244, 255), 210)


def _full() -> Image.Image:
    im = _orb((150, 70, 20), (255, 196, 96), 255)
    cat_col, eye_col = (58, 30, 14, 255), (140, 255, 140, 255)
    for y, row in enumerate(CAT):
        for x, ch in enumerate(row):
            if ch == "." or not im.getpixel((x, y))[3]:
                continue
            if y in (8, 9) and ch == "C":
                continue  # keep the gold band in front of the cat
            im.putpixel((x, y), eye_col if ch == "E" else cat_col)
    for x, y in ((4, 4), (5, 4), (4, 5), (5, 3)):
        im.putpixel((x, y), (255, 255, 255, 255))
    return im


def generate_orb_textures(verbose: bool = True) -> None:
    _, paths = load_config()
    out = []
    for tex, img in ((EMPTY_TEXTURE, _empty()), (FULL_TEXTURE, _full())):
        dest = paths.rp / (tex + ".png")
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest)
        out.append(rel(dest))
    if verbose:
        print(f"  wrote {', '.join(out)}")


if __name__ == "__main__":
    try:
        generate_orb_textures()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
