"""Generate the Atomic Bomb block textures (drawn in code, so there is no art file to lose).

Outputs (16x16):
  <rp>/textures/blocks/atomic_bomb_side.png     yellow with hazard stripes and a radiation symbol
  <rp>/textures/blocks/atomic_bomb_top.png      steel lid with a red fuse in the middle
  <rp>/textures/blocks/atomic_bomb_bottom.png   plain steel

Everything else for the Atomic Bomb is hand-written; see GENERATED_FILES.md.

Run standalone:  python tools/gen_atomic_bomb.py
"""

from __future__ import annotations

import math
import sys

from PIL import Image

from common import BuildError, load_config, rel

BOMB_ID = "mymod:atomic_bomb"
SIDE_TEXTURE = "textures/blocks/atomic_bomb_side"  # terrain_texture.json "mymod_atomic_bomb_side"
TOP_TEXTURE = "textures/blocks/atomic_bomb_top"  # "mymod_atomic_bomb_top"
BOTTOM_TEXTURE = "textures/blocks/atomic_bomb_bottom"  # "mymod_atomic_bomb_bottom"
ALL_TEXTURES = [SIDE_TEXTURE, TOP_TEXTURE, BOTTOM_TEXTURE]
TERRAIN = {
    "mymod_atomic_bomb_side": SIDE_TEXTURE,
    "mymod_atomic_bomb_top": TOP_TEXTURE,
    "mymod_atomic_bomb_bottom": BOTTOM_TEXTURE,
}

YELLOW = (240, 200, 32, 255)
YELLOW_DARK = (200, 160, 20, 255)
BLACK = (28, 28, 30, 255)
STEEL = (92, 96, 104, 255)
STEEL_LIGHT = (128, 132, 140, 255)
STEEL_DARK = (60, 62, 68, 255)
RED = (200, 30, 24, 255)
RED_LIGHT = (255, 96, 64, 255)


def _side() -> Image.Image:
    im = Image.new("RGBA", (16, 16), YELLOW)
    for y in range(16):
        for x in range(16):
            if y < 3 or y > 12:
                # diagonal black/yellow hazard stripes along the top and bottom edges
                im.putpixel((x, y), BLACK if (x + y) % 4 < 2 else YELLOW_DARK)
    # radiation trefoil: a dot in the middle and three blades, one pointing down
    cx = cy = 7.5
    for y in range(3, 13):
        for x in range(16):
            dx, dy = x - cx, y - cy
            r = math.hypot(dx, dy)
            ang = math.degrees(math.atan2(dy, dx)) % 360
            in_blade = any(abs((ang - a + 180) % 360 - 180) < 30 for a in (90, 210, 330))
            if r < 1.3 or (2.2 < r < 4.9 and in_blade):
                im.putpixel((x, y), BLACK)
    return im


def _top() -> Image.Image:
    im = Image.new("RGBA", (16, 16), STEEL)
    for i in range(16):
        for e in (0, 15):
            im.putpixel((i, e), STEEL_DARK)
            im.putpixel((e, i), STEEL_DARK)
    for y in range(16):
        for x in range(16):
            r = math.hypot(x - 7.5, y - 7.5)
            if 4.5 < r < 5.6:
                im.putpixel((x, y), YELLOW)
            elif r < 2.2:
                im.putpixel((x, y), RED)
    im.putpixel((7, 7), RED_LIGHT)
    for x, y in ((3, 3), (12, 3), (3, 12), (12, 12)):  # rivets
        im.putpixel((x, y), STEEL_LIGHT)
    return im


def _bottom() -> Image.Image:
    im = Image.new("RGBA", (16, 16), STEEL_DARK)
    for y in range(16):
        for x in range(16):
            if (x + 2 * y) % 7 == 0:
                im.putpixel((x, y), STEEL)
    return im


def generate_atomic_bomb_textures(verbose: bool = True) -> None:
    _, paths = load_config()
    out = []
    for tex, img in ((SIDE_TEXTURE, _side()), (TOP_TEXTURE, _top()), (BOTTOM_TEXTURE, _bottom())):
        dest = paths.rp / (tex + ".png")
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest)
        out.append(rel(dest))
    if verbose:
        print(f"  wrote {', '.join(out)}")


if __name__ == "__main__":
    try:
        generate_atomic_bomb_textures()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
