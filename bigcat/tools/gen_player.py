"""Let the Size Wand make players mini or huge (see scripts/wands.js).

Reads the vanilla player definition that tools/fetch_vanilla.py copied into vanilla/ and writes a
modified copy to <bp>/entities/player.json. It's a Mojang file with our changes, so it's gitignored
and rebuilt on every build (see README "Mojang content").

What changes:
  * component groups mymod:size_mini and mymod:size_huge, each holding only minecraft:scale.
    Vanilla players have no minecraft:scale, so removing both groups puts them back to normal.
  * events mymod:size_mini / mymod:size_huge / mymod:size_normal that swap the groups. The
    script calls them with player.triggerEvent().

Only the look changes: the hitbox, reach and first-person camera height stay vanilla.
Any other add-on that also replaces player.json will conflict with this one (the last pack
applied wins).

Run standalone:  python tools/gen_player.py
"""

from __future__ import annotations

import sys

from common import BuildError, load_config, rel, write_json
from gen_tame import _load_vanilla

SIZES = {"mini": 0.4, "huge": 2.5}  # keep in sync with the comment at the top of scripts/wands.js
GROUPS = {name: f"mymod:size_{name}" for name in SIZES}
EVENTS = {name: f"mymod:size_{name}" for name in (*SIZES, "normal")}


def _patch() -> dict:
    doc = _load_vanilla("player")
    ent = doc["minecraft:entity"]
    if "minecraft:scale" in ent["components"]:
        raise BuildError("vanilla player.json now has minecraft:scale; tools/gen_player.py needs updating")
    groups, events = ent.setdefault("component_groups", {}), ent.setdefault("events", {})
    for name, scale in SIZES.items():
        groups[GROUPS[name]] = {"minecraft:scale": {"value": scale}}
    all_groups = list(GROUPS.values())
    for name in SIZES:
        events[EVENTS[name]] = {
            "remove": {"component_groups": [g for g in all_groups if g != GROUPS[name]]},
            "add": {"component_groups": [GROUPS[name]]},
        }
    events[EVENTS["normal"]] = {"remove": {"component_groups": all_groups}}
    return doc


def generate_player(verbose: bool = True) -> None:
    _, paths = load_config()
    dest = paths.bp / "entities" / "player.json"
    write_json(dest, _patch())
    if verbose:
        print(f"  wrote {rel(dest)}")


if __name__ == "__main__":
    try:
        generate_player()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
