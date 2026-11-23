"""Generate the Vortex Gun item icons (pixel art drawn in code, so there is no art file to lose).

Outputs: <rp>/textures/items/vortex_gun.png          16x16 Monster Vortex icon (red swirl)
         <rp>/textures/items/animal_vortex_gun.png   16x16 Animal Vortex icon (green swirl)

Everything else for the Vortex Guns is hand-written; see GENERATED_FILES.md.

Run standalone:  python tools/gen_vortex.py
"""

from __future__ import annotations

import sys

from PIL import Image

from common import BuildError, load_config, rel

ITEM_TEXTURE = "textures/items/vortex_gun"
ANIMAL_TEXTURE = "textures/items/animal_vortex_gun"
ALL_TEXTURES = [ITEM_TEXTURE, ANIMAL_TEXTURE]

# 16x16 icon: a dark gun with a swirl being sucked into the muzzle.
#   . transparent   K outline   B body   L highlight   W/w grip   P/p/q swirl (light to dark)
ICON = [
    "................",
    "..........pPPq..",
    ".........P....p.",
    "........q..Pp..P",
    ".KKKKKKKKKq.P..P",
    ".KLLLLLLLLKp.q.p",
    ".KBBBBBBBBBK..P.",
    ".KBBBBBBBBBKqP..",
    ".KKKKKKKKKKK....",
    "..KWwK.K........",
    "..KWwK..K.......",
    "..KWwKKK........",
    ".KWwK...........",
    ".KWwK...........",
    ".KKKK...........",
    "................",
]
COLORS = {
    "K": (26, 20, 36, 255),
    "B": (70, 52, 104, 255),
    "L": (130, 104, 180, 255),
    "W": (150, 104, 56, 255),
    "w": (104, 68, 34, 255),
    # swirl: Monster Vortex (red)
    "P": (255, 140, 120, 255),
    "p": (230, 60, 50, 255),
    "q": (150, 20, 30, 255),
}
ANIMAL_SWIRL = {"P": (170, 255, 140, 255), "p": (80, 210, 70, 255), "q": (30, 130, 40, 255)}


def _icon(swirl: dict | None = None) -> Image.Image:
    if len(ICON) != 16 or any(len(row) != 16 for row in ICON):
        raise BuildError("gen_vortex.ICON must be 16 rows of 16 characters")
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y, row in enumerate(ICON):
        for x, ch in enumerate(row):
            if ch != ".":
                im.putpixel((x, y), {**COLORS, **(swirl or {})}[ch])
    return im


def generate_vortex_texture(verbose: bool = True) -> None:
    _, paths = load_config()
    out = []
    for tex, img in ((ITEM_TEXTURE, _icon()), (ANIMAL_TEXTURE, _icon(ANIMAL_SWIRL))):
        dest = paths.rp / (tex + ".png")
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest)
        out.append(rel(dest))
    if verbose:
        print(f"  wrote {', '.join(out)}")


if __name__ == "__main__":
    try:
        generate_vortex_texture()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
