"""Generate the Air Cannon item icon (pixel art drawn in code, so there is no art file to lose).

Outputs: <rp>/textures/items/air_cannon.png   16x16 item icon

Everything else for the Air Cannon is hand-written; see GENERATED_FILES.md.

Run standalone:  python tools/gen_air_cannon.py
"""

from __future__ import annotations

import sys

from PIL import Image

from common import BuildError, load_config, rel

ITEM_TEXTURE = "textures/items/air_cannon"
ALL_TEXTURES = [ITEM_TEXTURE]

# 16x16 icon: a teal cannon pointing right with a flared bell, a wooden grip, and puffs of
# air coming out of the bell.
#   . transparent   K outline   L highlight   B body   D shadow   W/w grip   A/a air
ICON = [
    "................",
    "................",
    "...........K....",
    "..........KLK.a.",
    ".KKKKKKKKKLBK..A",
    ".KLLLLLLLLLBK.A.",
    ".KBBBBBBBBBBKA..",
    ".KBBBBBBBBBBK.aA",
    ".KDDDDDDDDDBK.A.",
    ".KKKKKKKKKDBK..a",
    "..KWwK....KDK...",
    "..KWwK.....K....",
    ".KWwK...........",
    ".KWwK...........",
    ".KKKK...........",
    "................",
]
COLORS = {
    "K": (24, 40, 48, 255),
    "L": (150, 232, 228, 255),
    "B": (52, 170, 176, 255),
    "D": (28, 104, 112, 255),
    "W": (150, 104, 56, 255),
    "w": (104, 68, 34, 255),
    "A": (236, 248, 255, 255),
    "a": (190, 220, 240, 200),
}


def _icon() -> Image.Image:
    if len(ICON) != 16 or any(len(row) != 16 for row in ICON):
        raise BuildError("gen_air_cannon.ICON must be 16 rows of 16 characters")
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y, row in enumerate(ICON):
        for x, ch in enumerate(row):
            if ch != ".":
                im.putpixel((x, y), COLORS[ch])
    return im


def generate_air_cannon_textures(verbose: bool = True) -> None:
    _, paths = load_config()
    dest = paths.rp / (ITEM_TEXTURE + ".png")
    dest.parent.mkdir(parents=True, exist_ok=True)
    _icon().save(dest)
    if verbose:
        print(f"  wrote {rel(dest)}")


if __name__ == "__main__":
    try:
        generate_air_cannon_textures()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
