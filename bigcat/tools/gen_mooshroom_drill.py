"""Generate the Mooshroom Drill's chassis model, its texture and the item icon (see scripts/drill.js).

The drill bit is a real mooshroom: the client entity draws Minecraft's own geometry.mooshroom.v2
with the vanilla mooshroom texture (nothing copied into this repo), plus the chassis model built
here. The chassis model also has bones named `body` and `head` that hold the mushrooms (the
vanilla model has none; the game draws them separately for real mooshrooms) and the axle. The spin
animation rotates every bone called `body` and `head`, so the cow, its mushrooms and the axle all
turn together.

CUBES below is the single source of truth: each cube gets its own box-UV patch in the texture,
painted in its colour (cubes with the same size and paint share a patch).

Outputs:
  <rp>/models/entity/mooshroom_drill.geo.json   geometry.mymod.mooshroom_drill (chassis + mushrooms)
  <rp>/textures/entity/mooshroom_drill.png      its texture
  <rp>/textures/items/mooshroom_drill.png       16x16 item icon

Run standalone:  python tools/gen_mooshroom_drill.py
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass

from PIL import Image

from common import BuildError, load_config, rel, write_json

ITEM_ID = "mymod:mooshroom_drill"
VEHICLE_ID = "mymod:mooshroom_drill_vehicle"
GEOMETRY_ID = "geometry.mymod.mooshroom_drill"
GEO_FILE = "models/entity/mooshroom_drill.geo.json"
ENTITY_TEXTURE = "textures/entity/mooshroom_drill"
ICON_TEXTURE = "textures/items/mooshroom_drill"
ALL_TEXTURES = [ENTITY_TEXTURE, ICON_TEXTURE]
TEX_W, TEX_H = 128, 128

# The vanilla mooshroom's spinning bones and their pivots (geometry.mooshroom.v2). Our bones with
# the same names must use the same pivots so they turn around the same axis.
BODY_PIVOT = [0, 19, 2]
HEAD_PIVOT = [0, 20, -8]


@dataclass(frozen=True)
class Cube:
    bone: str
    origin: tuple[float, float, float]
    size: tuple[int, int, int]
    paint: str


def _mushroom(bone: str, x: float, top: float, z: float) -> list[Cube]:
    """A red mushroom standing on a surface at height `top`, centred on (x, z)."""
    return [
        Cube(bone, (x - 0.5, top, z - 0.5), (1, 2, 1), "stem"),
        Cube(bone, (x - 2, top + 2, z - 2), (4, 2, 4), "cap"),
        Cube(bone, (x - 1, top + 4, z - 1), (2, 1, 2), "cap"),
    ]


# Model pixels (16 = one block before the client entity's 1.5 scale). The mooshroom faces -z with
# its body between z -8 and 10, its back at y 22 and the top of its head at y 24. The chassis sits
# behind it, the seat at the back.
CUBES = [
    # chassis
    Cube("chassis", (-15, 0, 9), (5, 7, 27), "tread"),
    Cube("chassis", (10, 0, 9), (5, 7, 27), "tread"),
    Cube("chassis", (-10, 4, 11), (20, 6, 25), "deck"),
    Cube("chassis", (-7, 12, 12), (14, 14, 6), "motor"),
    Cube("chassis", (-9, 10, 13), (18, 2, 4), "motor"),  # motor mount
    Cube("chassis", (-5, 10, 25), (10, 3, 8), "seat"),
    Cube("chassis", (-5, 13, 32), (10, 9, 2), "seat"),  # backrest
    Cube("chassis", (7, 10, 33), (2, 14, 2), "exhaust"),
    Cube("chassis", (-9, 10, 33), (2, 14, 2), "exhaust"),
    Cube("chassis", (-11, 10, 11), (2, 3, 2), "light"),
    Cube("chassis", (9, 10, 11), (2, 3, 2), "light"),
    # the axle from the cow's rump into the motor (turns with the cow)
    Cube("body", (-1.5, 17.5, 9), (3, 3, 4), "axle"),
    # mushrooms on the back and on the head
    *_mushroom("body", -2.5, 22, -3),
    *_mushroom("body", 2.5, 22, 5),
    *_mushroom("head", 0, 24, -11),
]

PAINTS = {
    "tread": (52, 52, 58),
    "deck": (232, 178, 36),
    "motor": (148, 154, 166),
    "seat": (124, 40, 36),
    "exhaust": (78, 78, 88),
    "light": (255, 244, 170),
    "axle": (196, 200, 210),
    "stem": (226, 214, 192),
    "cap": (204, 32, 32),
}
CAP_SPOT = (250, 250, 250)
TREAD_STRIPE = (30, 30, 34)


def _patch_size(size) -> tuple[int, int]:
    w, h, d = size
    return 2 * (d + w), d + h


def layout() -> dict[tuple, tuple[int, int]]:
    """(size, paint) -> (u, v): shelf-pack one box-UV patch per distinct cube shape."""
    uvs: dict[tuple, tuple[int, int]] = {}
    x = y = shelf = 0
    for c in CUBES:
        key = (c.size, c.paint)
        if key in uvs:
            continue
        pw, ph = _patch_size(c.size)
        if x + pw > TEX_W:
            x, y, shelf = 0, y + shelf, 0
        if y + ph > TEX_H or pw > TEX_W:
            raise BuildError(f"gen_mooshroom_drill: cubes don't fit in a {TEX_W}x{TEX_H} texture")
        uvs[key] = (x, y)
        x += pw
        shelf = max(shelf, ph)
    return uvs


def geometry() -> dict:
    uvs = layout()
    bones = {
        "chassis": {"name": "chassis", "pivot": [0, 0, 0], "cubes": []},
        "body": {"name": "body", "pivot": BODY_PIVOT, "cubes": []},
        "head": {"name": "head", "pivot": HEAD_PIVOT, "cubes": []},
    }
    for c in CUBES:
        u, v = uvs[(c.size, c.paint)]
        bones[c.bone]["cubes"].append({"origin": list(c.origin), "size": list(c.size), "uv": [u, v]})
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [
            {
                "description": {
                    "identifier": GEOMETRY_ID,
                    "texture_width": TEX_W,
                    "texture_height": TEX_H,
                    "visible_bounds_width": 5,
                    "visible_bounds_height": 4,
                    "visible_bounds_offset": [0, 1.5, 0],
                },
                "bones": list(bones.values()),
            }
        ],
    }


def _shade(rgb, k: float) -> tuple[int, int, int, int]:
    return (*(max(0, min(255, round(c * k))) for c in rgb), 255)


def texture() -> Image.Image:
    rng = random.Random(7)  # deterministic speckle
    im = Image.new("RGBA", (TEX_W, TEX_H), (0, 0, 0, 0))
    for (size, paint), (u, v) in layout().items():
        w, h, d = size
        base = PAINTS[paint]
        # box-UV faces: (x, y, width, height, brightness)
        faces = [
            (u + d, v, w, d, 1.15),  # top
            (u + d + w, v, w, d, 0.7),  # bottom
            (u, v + d, d, h, 0.85),  # side
            (u + d, v + d, w, h, 1.0),  # front
            (u + d + w, v + d, d, h, 0.85),  # side
            (u + 2 * d + w, v + d, w, h, 0.9),  # back
        ]
        for fx, fy, fw, fh, k in faces:
            for py in range(fy, fy + fh):
                for px in range(fx, fx + fw):
                    edge = fw > 2 and fh > 2 and (px in (fx, fx + fw - 1) or py in (fy, fy + fh - 1))
                    kk = k * (0.8 if edge else 1.0) * (1 + (rng.random() - 0.5) * 0.08)
                    color = base
                    if paint == "tread" and (px + py) % 3 == 0:
                        color = TREAD_STRIPE
                    elif paint == "cap" and (fw, fh) == (w, d) and k > 1 and (px - fx + py - fy) % 3 == 1:
                        color = CAP_SPOT  # white spots on top of the cap
                    im.putpixel((px, py), _shade(color, kk))
    return im


# 16x16 icon: a red-and-white mooshroom bit (with a mushroom on top) in front of a yellow
# tracked chassis, with spin lines.
#   . transparent  K outline  R/r mooshroom  W white  M mushroom cap  Y/y chassis  G/g tracks  S spin
ICON = [
    "................",
    "..M.............",
    ".MMM............",
    "..W.......KK....",
    ".KKKKK...KyyK...",
    "KRRWRRK..KyyK...",
    "KRWWRrK.KYYYYK..",
    "KRRRRrKKKYYYYK.S",
    "KrRRWrKKYYYYYYK.",
    "KRRRRrKKYYYYYYKS",
    ".KKKKKKKYYYYYYK.",
    ".S.S...KGgGgGgGK",
    "......KGgGgGgGgK",
    "......KKKKKKKKKK",
    "................",
    "................",
]
COLORS = {
    "K": (36, 28, 28, 255),
    "R": (196, 38, 38, 255),
    "r": (140, 24, 24, 255),
    "W": (236, 230, 222, 255),
    "M": (220, 40, 40, 255),
    "Y": (236, 182, 40, 255),
    "y": (180, 130, 20, 255),
    "G": (70, 70, 78, 255),
    "g": (40, 40, 46, 255),
    "S": (200, 220, 240, 220),
}


def _icon() -> Image.Image:
    if len(ICON) != 16 or any(len(row) != 16 for row in ICON):
        raise BuildError("gen_mooshroom_drill.ICON must be 16 rows of 16 characters")
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y, row in enumerate(ICON):
        for x, ch in enumerate(row):
            if ch != ".":
                im.putpixel((x, y), COLORS[ch])
    return im


def generate_mooshroom_drill(verbose: bool = True) -> None:
    _, paths = load_config()
    geo = paths.rp / GEO_FILE
    write_json(geo, geometry())
    written = [geo]
    for tex, make in ((ENTITY_TEXTURE, texture), (ICON_TEXTURE, _icon)):
        dest = paths.rp / (tex + ".png")
        dest.parent.mkdir(parents=True, exist_ok=True)
        make().save(dest)
        written.append(dest)
    if verbose:
        print(f"  wrote {', '.join(rel(p) for p in written)}")


if __name__ == "__main__":
    try:
        generate_mooshroom_drill()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
