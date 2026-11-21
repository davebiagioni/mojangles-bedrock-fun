"""Generate the Net Trap textures (drawn in code, so there is no art file to lose).

Outputs (16x16):
  <rp>/textures/blocks/net_trap.png   the net lying on the ground: rope mesh with knots, see-through holes
  <rp>/textures/items/net_trap.png    the item icon: a bundled-up net (diagonal mesh in a rough circle)

Run standalone:  python tools/gen_net.py
"""

from __future__ import annotations

import sys

from PIL import Image

from common import BuildError, load_config, rel

NET_ID = "mymod:net_trap"
BLOCK_TEXTURE = "textures/blocks/net_trap"  # terrain_texture.json "mymod_net_trap"
ICON_TEXTURE = "textures/items/net_trap"  # item_texture.json "mymod_net_trap"
ALL_TEXTURES = [BLOCK_TEXTURE, ICON_TEXTURE]

ROPE = (196, 172, 128, 255)
ROPE_DARK = (138, 116, 80, 255)
KNOT = (102, 82, 54, 255)
MESH = 4  # pixels between ropes


def block_texture() -> Image.Image:
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y in range(16):
        for x in range(16):
            on_x, on_y = x % MESH == 1, y % MESH == 1
            if on_x and on_y:
                im.putpixel((x, y), KNOT)
            elif on_x or on_y:
                im.putpixel((x, y), ROPE if (x + y) % 3 else ROPE_DARK)
    return im


def icon_texture() -> Image.Image:
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    cx, cy, r = 7.5, 8.0, 6.8
    for y in range(16):
        for x in range(16):
            if (x - cx) ** 2 + (y - cy) ** 2 > r * r:
                continue
            a, b = (x + y) % 4 == 0, (x - y) % 4 == 0
            if a and b:
                im.putpixel((x, y), KNOT)
            elif a or b:
                im.putpixel((x, y), ROPE if x < 9 else ROPE_DARK)
    return im


def generate_net_textures(verbose: bool = True) -> None:
    _, paths = load_config()
    out = []
    for tex, img in ((BLOCK_TEXTURE, block_texture()), (ICON_TEXTURE, icon_texture())):
        dest = paths.rp / (tex + ".png")
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest)
        out.append(rel(dest))
    if verbose:
        print(f"  wrote {', '.join(out)}")


if __name__ == "__main__":
    try:
        generate_net_textures()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
