"""Drowned Trap: make drowned attack the trap, and draw its pixel art.

Outputs:
  <bp>/entities/drowned.json              vanilla drowned + one extra attack target: the trap
                                          (Mojang file with our change, so gitignored; see README)
  <rp>/textures/items/drowned_trap.png    16x16 item icon: a prismarine cage with a fish inside
  <rp>/textures/entity/drowned_lure.png   32x32 texture for the placed trap (cage + bait fish)

Only drowned get the new target, so zombies, husks and everything else ignore the trap.
scripts/drowned_trap.js does the rest (placing, the explosion, the enchanted weapon drop,
picking the trap back up).

Run standalone:  python tools/gen_drowned_trap.py
"""

from __future__ import annotations

import sys

from PIL import Image

from common import BuildError, load_config, rel, write_json
from gen_tame import _load_vanilla

TRAP_FAMILY = "bigcat_drowned_trap"
TARGET_GOAL = "minecraft:behavior.nearest_attackable_target"
TRAP_TARGET = {"filters": {"test": "is_family", "subject": "other", "value": TRAP_FAMILY}, "max_dist": 12}

ITEM_TEXTURE = "textures/items/drowned_trap"
LURE_TEXTURE = "textures/entity/drowned_lure"
ALL_TEXTURES = [ITEM_TEXTURE, LURE_TEXTURE]

#   . transparent   K dark prismarine   L light prismarine   B bars   O fish   E eye   T tail
ICON = [
    "................",
    "................",
    "..KKKKKKKKKKKK..",
    "..KLLLLLLLLLLK..",
    "..K..B..B..B.K..",
    "..K..B..B..B.K..",
    "..K..B..B..B.K..",
    "..K..OOOOO.T.K..",
    "..K..OEOOOTT.K..",
    "..K..OOOOO.T.K..",
    "..K..B..B..B.K..",
    "..K..B..B..B.K..",
    "..KLLLLLLLLLLK..",
    "..KKKKKKKKKKKK..",
    "................",
    "................",
]
COLORS = {
    "K": (28, 72, 70, 255),
    "L": (96, 176, 156, 255),
    "B": (58, 122, 112, 255),
    "O": (232, 132, 60, 255),
    "E": (20, 20, 20, 255),
    "T": (196, 98, 40, 255),
}


def patch_drowned() -> dict:
    """The vanilla drowned, with the trap added as the first thing it attacks."""
    doc = _load_vanilla("drowned")
    comps = doc.get("minecraft:entity", {}).get("components", {})
    goal = comps.get(TARGET_GOAL)
    if not isinstance(goal, dict):
        raise BuildError(f"vanilla drowned has no {TARGET_GOAL}; Mojang changed it, update gen_drowned_trap.py")
    types = goal.get("entity_types", [])
    types = types if isinstance(types, list) else [types]
    goal["entity_types"] = [TRAP_TARGET, *types]
    return doc


def _icon() -> Image.Image:
    if len(ICON) != 16 or any(len(row) != 16 for row in ICON):
        raise BuildError("gen_drowned_trap.ICON must be 16 rows of 16 characters")
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y, row in enumerate(ICON):
        for x, ch in enumerate(row):
            if ch != ".":
                im.putpixel((x, y), COLORS[ch])
    return im


def _lure() -> Image.Image:
    """32x32: the 8px cage cube's box UV at (0,0) and the bait fish cube's box UV at (0,16).

    Cage faces are a frame with two bars and see-through gaps (the material is alphatest), so
    the orange fish shows through.
    """
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    dark, light, bar = COLORS["K"], COLORS["L"], COLORS["B"]
    for fx, fy in ((8, 0), (16, 0), (0, 8), (8, 8), (16, 8), (24, 8)):
        for y in range(8):
            for x in range(8):
                if x in (0, 7) or y in (0, 7):
                    im.putpixel((fx + x, fy + y), light if y == 0 else dark)
                elif x in (2, 5):
                    im.putpixel((fx + x, fy + y), bar)
    # bait cube 4x3x3 -> box UV area 14x6
    for y in range(16, 22):
        for x in range(14):
            im.putpixel((x, y), COLORS["T"] if (x + y) % 4 == 0 else COLORS["O"])
    return im


def generate_drowned_trap(verbose: bool = True) -> None:
    _, paths = load_config()
    dest = paths.bp / "entities" / "drowned.json"
    write_json(dest, patch_drowned())
    out = [rel(dest)]
    for tex, img in ((ITEM_TEXTURE, _icon()), (LURE_TEXTURE, _lure())):
        p = paths.rp / (tex + ".png")
        p.parent.mkdir(parents=True, exist_ok=True)
        img.save(p)
        out.append(rel(p))
    if verbose:
        print(f"  wrote {', '.join(out)}")


if __name__ == "__main__":
    try:
        generate_drowned_trap()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
