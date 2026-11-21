"""Generate the wand item icons (drawn in code, so there is no art file to lose).

Outputs (16x16, in <rp>/textures/items/):
  size_wand.png    wooden wand with a red mushroom cap (one bite makes you small, the other big)
  vapor_wand.png   wooden wand with a rainbow star and a green puff

Run standalone:  python tools/gen_wand.py
"""

from __future__ import annotations

import sys

from PIL import Image

from common import BuildError, load_config, rel

ALL_TEXTURES = ["textures/items/size_wand", "textures/items/vapor_wand"]

WOOD, WOOD_DARK = (150, 104, 56, 255), (92, 60, 30, 255)

SIZE_TIP = [
    "................",
    "..........RRR...",
    ".........RWRRR..",
    "........RRRRWRR.",
    "........RWRRRRR.",
    ".........RRRWR..",
    "..........SSS...",
    "................",
]
VAPOR_TIP = [
    "...........1....",
    "..........121...",
    ".......G.12321..",
    "......GgG.141...",
    "......GgG..5....",
    ".......G........",
    "................",
    "................",
]
TIP_COLORS = {
    "R": (206, 40, 40, 255),
    "W": (250, 246, 236, 255),
    "S": (232, 222, 200, 255),
    "1": (255, 70, 70, 255),
    "2": (255, 190, 40, 255),
    "3": (255, 255, 200, 255),
    "4": (70, 200, 255, 255),
    "5": (190, 90, 255, 255),
    "G": (96, 170, 48, 255),
    "g": (150, 220, 80, 255),
}


def _wand(tip: list[str]) -> Image.Image:
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    # diagonal stick from the bottom-left corner towards the tip, 2 px thick with a dark edge
    for i in range(9):
        x, y = 2 + i, 14 - i
        im.putpixel((x, y), WOOD)
        im.putpixel((x + 1, y), WOOD_DARK)
    for y, row in enumerate(tip):
        for x, ch in enumerate(row):
            if ch != ".":
                im.putpixel((x, y), TIP_COLORS[ch])
    return im


def generate_wand_textures(verbose: bool = True) -> None:
    _, paths = load_config()
    out = []
    for tex, tip in zip(ALL_TEXTURES, (SIZE_TIP, VAPOR_TIP), strict=True):
        dest = paths.rp / (tex + ".png")
        dest.parent.mkdir(parents=True, exist_ok=True)
        _wand(tip).save(dest)
        out.append(rel(dest))
    if verbose:
        print(f"  wrote {', '.join(out)}")


if __name__ == "__main__":
    try:
        generate_wand_textures()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
