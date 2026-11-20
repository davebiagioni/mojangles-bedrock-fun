"""Generate the laser pointer textures (tiny pixel art, drawn in code so there is no art file to lose).

Outputs: <rp>/textures/items/laser_pointer.png   16x16 item icon
         <rp>/textures/entity/laser_dot.png      16x16 texture for the dot's 4px cube

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
    # Box UV for a 4x4x4 cube at uv [0,0] uses the top 16x8; fill all 16x16. Bright red with
    # a pale core on each face. The render controller ignores lighting, so this is the exact
    # colour you see, even in shade or at night.
    im = Image.new("RGBA", (16, 16), (235, 25, 25, 255))
    # face rectangles of the box UV layout (x, y, w, h)
    for fx, fy in ((4, 0), (8, 0), (0, 4), (4, 4), (8, 4), (12, 4)):
        for dx, dy in ((1, 1), (2, 1), (1, 2), (2, 2)):
            im.putpixel((fx + dx, fy + dy), (255, 140, 140, 255))
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
