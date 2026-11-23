"""Generate the blaster icons (drawn in code, so there is no art file to lose).

Output (16x16):
  <rp>/textures/items/laser_blaster.png   a chunky grey blaster pointing up-right with a glowing cyan barrel
  <rp>/textures/items/flame_blaster.png   the same blaster with an orange, yellow-hot barrel
  <rp>/textures/items/water_blaster.png   ... with a deep blue barrel
  <rp>/textures/items/ice_blaster.png     ... with a pale icy barrel
  <rp>/textures/items/barf_blaster.png    ... with a slimy green barrel

Run standalone:  python tools/gen_blaster.py
"""

from __future__ import annotations

import sys

from PIL import Image

from common import BuildError, load_config, rel

BLASTER_ID = "mymod:laser_blaster"
ICON_TEXTURE = "textures/items/laser_blaster"  # item_texture.json "mymod_laser_blaster"
FLAME_ID = "mymod:flame_blaster"
FLAME_TEXTURE = "textures/items/flame_blaster"  # item_texture.json "mymod_flame_blaster"
WATER_ID = "mymod:water_blaster"
WATER_TEXTURE = "textures/items/water_blaster"
ICE_ID = "mymod:ice_blaster"
ICE_TEXTURE = "textures/items/ice_blaster"
BARF_ID = "mymod:barf_blaster"
BARF_TEXTURE = "textures/items/barf_blaster"
ALL_TEXTURES = [ICON_TEXTURE, FLAME_TEXTURE, WATER_TEXTURE, ICE_TEXTURE, BARF_TEXTURE]

ART = [
    "................",
    ".............WW.",
    "............WCCW",
    "...........CCCW.",
    "..........CCCC..",
    ".........GGCC...",
    "........GLLG....",
    ".......GLLLG....",
    "......GLLDDG....",
    ".....GLLDDG.....",
    "....GDDDDG......",
    "...GDDRRG.......",
    "...GDDG.GG......",
    "....GG..GDG.....",
    ".........GG.....",
    "................",
]
COLORS = {
    "W": (235, 255, 255, 255),  # white-hot tip
    "C": (60, 230, 255, 255),  # cyan barrel glow
    "G": (40, 44, 52, 255),  # dark outline
    "L": (170, 176, 186, 255),  # light metal
    "D": (110, 116, 128, 255),  # dark metal
    "R": (230, 40, 60, 255),  # red power light
}
FLAME_COLORS = {"W": (255, 250, 170, 255), "C": (255, 130, 30, 255)}  # yellow-hot tip, orange barrel
WATER_COLORS = {"W": (200, 230, 255, 255), "C": (40, 110, 240, 255)}  # light tip, deep blue barrel
ICE_COLORS = {"W": (255, 255, 255, 255), "C": (170, 225, 245, 255)}  # white tip, pale icy barrel
BARF_COLORS = {"W": (220, 240, 110, 255), "C": (120, 170, 40, 255), "R": (150, 100, 40, 255)}  # slimy green, brown


def icon(recolor: dict | None = None) -> Image.Image:
    colors = {**COLORS, **(recolor or {})}
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y, row in enumerate(ART):
        for x, ch in enumerate(row):
            if ch != ".":
                im.putpixel((x, y), colors[ch])
    return im


def generate_blaster_texture(verbose: bool = True) -> None:
    _, paths = load_config()
    out = []
    for tex, img in (
        (ICON_TEXTURE, icon()),
        (FLAME_TEXTURE, icon(FLAME_COLORS)),
        (WATER_TEXTURE, icon(WATER_COLORS)),
        (ICE_TEXTURE, icon(ICE_COLORS)),
        (BARF_TEXTURE, icon(BARF_COLORS)),
    ):
        dest = paths.rp / (tex + ".png")
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest)
        out.append(rel(dest))
    if verbose:
        print(f"  wrote {', '.join(out)}")


if __name__ == "__main__":
    try:
        generate_blaster_texture()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
