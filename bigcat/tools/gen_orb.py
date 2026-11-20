"""Generate the orb item icons (drawn in code, so there is no art file to lose).

Outputs (16x16, in <rp>/textures/items/):
  cat_orb.png / cat_orb_full.png              pale glass, gold band / amber glow with a cat
  creature_orb.png / creature_orb_full.png    mint glass, silver band / green glow with a paw print
  trap_orb.png / trap_orb_full.png            smoky glass, red band / red glow with a player

Run standalone:  python tools/gen_orb.py
"""
from __future__ import annotations

import sys

from PIL import Image

from common import BuildError, load_config, rel

EMPTY_TEXTURE = "textures/items/cat_orb"
FULL_TEXTURE = "textures/items/cat_orb_full"
ALL_TEXTURES = [f"textures/items/{n}{f}" for n in ("cat_orb", "creature_orb", "trap_orb") for f in ("", "_full")]

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


# Paw print inside the occupied Creature Orb (P = pad).
PAW = [
    "................",
    "................",
    "................",
    "........P.P.....",
    "......P.P.P.P...",
    "......P.....P...",
    "........PPP.....",
    ".......PPPPP....",
    "................",
    "................",
    ".......PPPPP....",
    "........PPP.....",
    "................",
    "................",
    "................",
    "................",
]

# Player figure inside the occupied Trap Orb (H = head, B = body).
FIGURE = [
    "................",
    "................",
    "................",
    "......HHHH......",
    "......HHHH......",
    "......HHHH......",
    "......HHHH......",
    ".....BBBBBB.....",
    ".....BBBBBB.....",
    ".....BBBBBB.....",
    ".....BBBBBB.....",
    "......B..B......",
    "......B..B......",
    "................",
    "................",
    "................",
]


def _lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _orb(inner_dark, inner_light, alpha, band=((214, 160, 52), (255, 222, 120))) -> Image.Image:
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    outline = (36, 30, 54, 255)
    gold, gold_hi = (*band[0], 255), (*band[1], 255)
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


SILVER = ((170, 178, 190), (236, 240, 246))
RED = ((178, 34, 40), (240, 96, 90))


def _overlay(im, pattern, colors, keep_band=True) -> Image.Image:
    for y, row in enumerate(pattern):
        for x, ch in enumerate(row):
            if ch == "." or not im.getpixel((x, y))[3]:
                continue
            if keep_band and y in (8, 9):
                continue
            im.putpixel((x, y), colors[ch])
    for x, y in ((4, 4), (5, 4), (4, 5), (5, 3)):
        im.putpixel((x, y), (255, 255, 255, 255))
    return im


def _creature_empty() -> Image.Image:
    return _orb((110, 190, 150), (225, 255, 236), 210, SILVER)


def _creature_full() -> Image.Image:
    return _overlay(_orb((24, 110, 56), (140, 236, 150), 255, SILVER), PAW, {"P": (14, 52, 26, 255)})


def _trap_empty() -> Image.Image:
    return _orb((70, 62, 92), (182, 172, 204), 220, RED)


def _trap_full() -> Image.Image:
    return _overlay(_orb((120, 16, 26), (255, 120, 104), 255, RED), FIGURE,
                    {"H": (60, 12, 16, 255), "B": (60, 12, 16, 255)})


def generate_orb_textures(verbose: bool = True) -> None:
    _, paths = load_config()
    out = []
    makers = (_empty, _full, _creature_empty, _creature_full, _trap_empty, _trap_full)
    for tex, make in zip(ALL_TEXTURES, makers):
        dest = paths.rp / (tex + ".png")
        dest.parent.mkdir(parents=True, exist_ok=True)
        make().save(dest)
        out.append(rel(dest))
    if verbose:
        print(f"  wrote {', '.join(out)}")


if __name__ == "__main__":
    try:
        generate_orb_textures()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
