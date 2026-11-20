"""Make zombies, creepers and skeletons tameable (the funny way; see scripts/tame_monsters.js).

Reads the vanilla definitions that tools/fetch_vanilla.py copied into vanilla/ and writes
modified copies into <bp>/entities/. Those outputs are Mojang files with our changes, so they are
gitignored and rebuilt on every build (see README "Mojang content").

What changes, per mob:
  * minecraft:tameable with probability 0, so feeding never tames them by itself; the script
    calls tame() when you do the funny thing, and the tame_event adds the tamed group below.
  * an extra minecraft:interact entry, so touch screens show a button ("Give Milk", "Give Cake",
    "Hug") and the script gets the interaction. The creeper keeps its flint-and-steel one.
  * component group mymod:tamed_monster (added on taming), which overrides the base goals:
      - follows its owner, never targets or fights back against players,
      - zombies and skeletons defend you and attack monsters that aren't tamed,
      - creepers only tag along (a creeper that attacks just blows up),
      - never despawns.

Run standalone:  python tools/gen_tame.py
"""
from __future__ import annotations

import json
import re
import sys

from common import ROOT, BuildError, load_config, rel, write_json

VANILLA = ROOT / "vanilla"
TAMED_GROUP = "mymod:tamed_monster"
TAME_EVENT = "mymod:on_tamed"
TRY_EVENT = "mymod:taming_attempt"  # no-op; the script does the work
NEVER = {"test": "is_family", "subject": "self", "value": "mymod_never"}  # a filter that never matches
NOT_TAMED_SELF = {"test": "has_component", "subject": "self", "operator": "!=", "value": "minecraft:is_tamed"}

MOBS = {
    "zombie": {
        "interact": {"text": "action.interact.mymod_give_cake", "item": "cake"},
        "fights": True,
    },
    "skeleton": {
        "interact": {"text": "action.interact.mymod_give_milk", "item": "milk_bucket"},
        "fights": True,
    },
    "creeper": {
        "interact": {"text": "action.interact.mymod_hug", "sneaking": True},
        "fights": False,
    },
}
LANG = {
    "action.interact.mymod_give_cake": "Give Cake",
    "action.interact.mymod_give_milk": "Give Milk",
    "action.interact.mymod_hug": "Hug",
}


def _strip_comments(text: str) -> str:
    """Mojang's files have // comments; JSON doesn't. Strings are left alone."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\":
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            i = text.find("*/", i + 2) + 2
            continue
        out.append(c)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def _load_vanilla(name: str) -> dict:
    p = VANILLA / f"{name}.json"
    if not p.is_file():
        raise BuildError(f"{rel(p)} missing; run tools/fetch_vanilla.py")
    try:
        return json.loads(_strip_comments(p.read_text(encoding="utf-8-sig")))
    except json.JSONDecodeError as e:
        raise BuildError(f"{rel(p)}: could not parse: {e}") from None


def _interaction(spec: dict) -> dict:
    conds = [{"test": "is_family", "subject": "other", "value": "player"}, NOT_TAMED_SELF]
    if "item" in spec:
        conds.append({"test": "has_equipment", "subject": "other", "domain": "hand", "value": spec["item"]})
    if spec.get("sneaking"):
        conds.append({"test": "is_sneaking", "subject": "other"})
    return {
        "interact_text": spec["text"],
        "on_interact": {"event": TRY_EVENT, "target": "self", "filters": {"all_of": conds}},
    }


def _tamed_group(fights: bool) -> dict:
    g = {
        "minecraft:is_tamed": {},
        "minecraft:behavior.follow_owner": {
            "priority": 3, "speed_multiplier": 1.15, "start_distance": 8, "stop_distance": 3,
        },
        # never despawn once tamed (the base despawn rule can't be removed, only overridden)
        "minecraft:persistent": {},
        "minecraft:despawn": {
            "despawn_from_chance": False,
            "despawn_from_inactivity": False,
            "despawn_from_simulation_edge": False,
            "filters": NEVER,
        },
        # don't fight back against any player
        "minecraft:behavior.hurt_by_target": {
            "priority": 1,
            "entity_types": [{"filters": {"test": "is_family", "subject": "other", "operator": "!=", "value": "player"}}],
        },
    }
    if fights:
        g["minecraft:behavior.owner_hurt_by_target"] = {"priority": 1}
        g["minecraft:behavior.owner_hurt_target"] = {"priority": 2}
        g["minecraft:behavior.nearest_attackable_target"] = {
            "priority": 2,
            "must_see": True,
            "reselect_targets": True,
            "within_radius": 16,
            "entity_types": [{
                "filters": {"all_of": [
                    {"test": "is_family", "subject": "other", "value": "monster"},
                    {"test": "has_component", "subject": "other", "operator": "!=", "value": "minecraft:is_tamed"},
                ]},
                "max_dist": 16,
            }],
        }
    else:
        g["minecraft:behavior.nearest_attackable_target"] = {
            "priority": 1, "entity_types": [{"filters": NEVER, "max_dist": 1}],
        }
    return g


def _patch(name: str, spec: dict) -> dict:
    doc = _load_vanilla(name)
    ent = doc["minecraft:entity"]
    comps, groups, events = ent["components"], ent.setdefault("component_groups", {}), ent.setdefault("events", {})

    comps["minecraft:tameable"] = {
        "probability": 0.0,
        "tame_items": "barrier",  # never fed in survival; the script tames instead
        "tame_event": {"event": TAME_EVENT, "target": "self"},
    }
    interact = comps.get("minecraft:interact")
    ours = _interaction(spec["interact"])
    if interact is None:
        comps["minecraft:interact"] = {"interactions": [ours]}
    else:
        existing = interact.get("interactions", [])
        existing = existing if isinstance(existing, list) else [existing]
        interact["interactions"] = existing + [ours]

    groups[TAMED_GROUP] = _tamed_group(spec["fights"])
    events[TAME_EVENT] = {"add": {"component_groups": [TAMED_GROUP]}}
    events[TRY_EVENT] = {"add": {"component_groups": []}}
    return doc


def generate_tame(verbose: bool = True) -> None:
    _, paths = load_config()
    out = []
    for name, spec in MOBS.items():
        dest = paths.bp / "entities" / f"{name}.json"
        write_json(dest, _patch(name, spec))
        out.append(rel(dest))
    lang = paths.rp / "texts/en_US.lang"
    text = lang.read_text(encoding="utf-8")
    missing = [f"{k}={v}" for k, v in LANG.items() if f"{k}=" not in text]
    if missing:
        lang.write_text(text.rstrip("\n") + "\n" + "\n".join(missing) + "\n", encoding="utf-8", newline="\n")
    if verbose:
        print(f"  wrote {', '.join(out)}")


if __name__ == "__main__":
    try:
        generate_tame()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
