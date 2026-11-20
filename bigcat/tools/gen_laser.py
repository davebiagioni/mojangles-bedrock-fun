"""Generate the laser pointer textures (tiny pixel art, drawn in code so there is no art file to lose).

Outputs: <rp>/textures/items/laser_pointer.png   16x16 item icon
         <rp>/textures/entity/laser_dot.png      8x8 texture for the dot's 2px cube

Everything else for the laser pointer is hand-written; see GENERATED_FILES.md.

Run standalone:  python tools/gen_laser.py
"""
from __future__ import annotations

import sys

from PIL import Image

from common import BuildError, load_config, rel

ITEM_TEXTURE = "textures/items/laser_pointer"
DOT_TEXTURE = "textures/entity/laser_dot"

# 16x16 icon: a pen-shaped pointer lying diagonally, red emitter top-right, beam beyond it.
#   . transparent   K outline   B body   H body highlight   S steel tip   R red   P pink glow
ICON = [
    "................",
    "...........P..P.",
    "............RP..",
    "..........KSRP.P",
    ".........KSSK...",
    "........KBHK....",
    ".......KBHK.....",
    "......KBHK......",
    ".....KBHK.......",
    "....KBRK........",
    "...KBHK.........",
    "..KBHK..........",
    ".KBHK...........",
    ".KBK............",
    "..K.............",
    "................",
]
COLORS = {
    "K": (28, 28, 34, 255),
    "B": (70, 74, 86, 255),
    "H": (128, 134, 150, 255),
    "S": (196, 200, 208, 255),
    "R": (235, 30, 30, 255),
    "P": (255, 120, 120, 200),
}


def _icon() -> Image.Image:
    if len(ICON) != 16 or any(len(row) != 16 for row in ICON):
        raise BuildError("gen_laser.ICON must be 16 rows of 16 characters")
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y, row in enumerate(ICON):
        for x, ch in enumerate(row):
            if ch != ".":
                im.putpixel((x, y), COLORS[ch])
    return im


def _dot() -> Image.Image:
    # Box UV for a 2x2x2 cube at uv [0,0] uses the top 8x4; fill all 8x8, bright red
    # with a lighter core so it reads as "lit" even under the lit entity material.
    im = Image.new("RGBA", (8, 8), (225, 20, 20, 255))
    for x, y in ((2, 0), (3, 1), (2, 2), (3, 3), (6, 2), (7, 3), (0, 2), (1, 3)):
        im.putpixel((x, y), (255, 110, 110, 255))
    return im


def generate_laser_textures(verbose: bool = True) -> None:
    _, paths = load_config()
    out = []
    for tex, img in ((ITEM_TEXTURE, _icon()), (DOT_TEXTURE, _dot())):
        dest = paths.rp / (tex + ".png")
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest)
        out.append(rel(dest))
    if verbose:
        print(f"  wrote {', '.join(out)}")


if __name__ == "__main__":
    try:
        generate_laser_textures()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
