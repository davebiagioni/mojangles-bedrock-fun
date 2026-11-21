"""Generate the grappling gun textures (pixel art drawn in code, so there is no art file to lose).

Outputs: <rp>/textures/items/grappling_gun.png   16x16 item icon
         <rp>/textures/entity/grapple_hook.png    16x16 steel texture for the flying hook's model

Everything else for the grappling gun is hand-written; see GENERATED_FILES.md.

Run standalone:  python tools/gen_grapple.py
"""

from __future__ import annotations

import sys

from PIL import Image

from common import BuildError, load_config, rel

ITEM_TEXTURE = "textures/items/grappling_gun"
HOOK_TEXTURE = "textures/entity/grapple_hook"
ALL_TEXTURES = [ITEM_TEXTURE, HOOK_TEXTURE]

# 16x16 icon: a steel launcher pointing right with a wooden grip, the hook's shaft
# sticking out of the barrel and two barbs at the tip.
#   . transparent   K outline   B body   L highlight   W/w wood grip   S shaft   O/o hook
ICON = [
    "................",
    "................",
    "................",
    "............O...",
    ".KKKKKKKKKK..O..",
    ".KLLLLLLLLLK..O.",
    ".KBBBBBBBBBSSSoO",
    ".KBBBBBBBBBK..O.",
    ".KKKKKKKKKKK.O..",
    "..KWwK.K....O...",
    "..KWwK..K.......",
    "..KWwKKK........",
    ".KWwK...........",
    ".KWwK...........",
    ".KKKK...........",
    "................",
]
COLORS = {
    "K": (34, 36, 42, 255),
    "B": (96, 102, 116, 255),
    "L": (160, 168, 184, 255),
    "W": (150, 104, 56, 255),
    "w": (104, 68, 34, 255),
    "S": (196, 200, 208, 255),
    "O": (70, 74, 84, 255),
    "o": (230, 232, 238, 255),
}


def _icon() -> Image.Image:
    if len(ICON) != 16 or any(len(row) != 16 for row in ICON):
        raise BuildError("gen_grapple.ICON must be 16 rows of 16 characters")
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y, row in enumerate(ICON):
        for x, ch in enumerate(row):
            if ch != ".":
                im.putpixel((x, y), COLORS[ch])
    return im


def _hook() -> Image.Image:
    # Brushed steel: a fixed diagonal pattern of three shades. Every cube of the hook model
    # maps into this one texture, so it only has to look metallic from any face.
    shades = [(118, 122, 132, 255), (150, 156, 168, 255), (88, 92, 102, 255)]
    im = Image.new("RGBA", (16, 16))
    for y in range(16):
        for x in range(16):
            im.putpixel((x, y), shades[(x + 2 * y) % 5 % 3])
    return im


def generate_grapple_textures(verbose: bool = True) -> None:
    _, paths = load_config()
    out = []
    for tex, img in ((ITEM_TEXTURE, _icon()), (HOOK_TEXTURE, _hook())):
        dest = paths.rp / (tex + ".png")
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest)
        out.append(rel(dest))
    if verbose:
        print(f"  wrote {', '.join(out)}")


if __name__ == "__main__":
    try:
        generate_grapple_textures()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
