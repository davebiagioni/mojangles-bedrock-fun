"""Generate the Mountain Seed item icon (pixel art drawn in code, so there is no art file to lose).

Outputs: <rp>/textures/items/mountain_seed.png   16x16 item icon

The mountain itself is made by big_cat_bp/scripts/mountain.js (diamond-square fractal); see
GENERATED_FILES.md.

Run standalone:  python tools/gen_mountain.py
"""

from __future__ import annotations

import sys

from PIL import Image

from common import BuildError, load_config, rel

ITEM_TEXTURE = "textures/items/mountain_seed"
ALL_TEXTURES = [ITEM_TEXTURE]

# 16x16 icon: a brown seed with a tiny snow-capped mountain growing out of the top.
#   . transparent   K outline   W snow   S/s stone   G/g grass   B/b seed shell
ICON = [
    "................",
    ".......K........",
    "......KWK.......",
    ".....KWWsK......",
    "....KSWSssK.....",
    "...KSSSssssK....",
    "..KGSSSsssssK...",
    ".KGGGSgGsGssgK..",
    ".KGgGGgGGGgggK..",
    "..KKBBBBBBbbK...",
    "...KBBbBBBbbK...",
    "...KBBBBBbbbK...",
    "....KBBBBbbK....",
    ".....KBBbbK.....",
    "......KKKK......",
    "................",
]
COLORS = {
    "K": (36, 30, 26, 255),
    "W": (244, 248, 252, 255),
    "S": (150, 150, 156, 255),
    "s": (108, 108, 116, 255),
    "G": (96, 172, 64, 255),
    "g": (64, 128, 44, 255),
    "B": (170, 116, 62, 255),
    "b": (126, 82, 40, 255),
}


def _icon() -> Image.Image:
    if len(ICON) != 16 or any(len(row) != 16 for row in ICON):
        raise BuildError("gen_mountain.ICON must be 16 rows of 16 characters")
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y, row in enumerate(ICON):
        for x, ch in enumerate(row):
            if ch != ".":
                im.putpixel((x, y), COLORS[ch])
    return im


def generate_mountain_texture(verbose: bool = True) -> None:
    _, paths = load_config()
    dest = paths.rp / (ITEM_TEXTURE + ".png")
    dest.parent.mkdir(parents=True, exist_ok=True)
    _icon().save(dest)
    if verbose:
        print(f"  wrote {rel(dest)}")


if __name__ == "__main__":
    try:
        generate_mountain_texture()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
