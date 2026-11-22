"""Generate the Morph Wand's creature costume (see scripts/morph.js).

FORMS below is the single source of truth for the creatures a player can turn into. Form 0 is
"yourself" (no costume). Everything else is drawn with Minecraft's own models, textures and
animations, so there is no art to keep in sync.

How it works: the player is made invisible and a mymod:morph entity (no AI, can't be hurt, no
collision) is teleported onto them every tick. Its int property mymod:form picks the creature.

Outputs:
  <bp>/entities/morph.json                         the costume entity
  <bp>/scripts/morph_forms.js                      FORMS for the script (names, sounds)
  <rp>/entity/morph.entity.json                    one geometry / texture / material per form
  <rp>/render_controllers/morph.render_controllers.json   one render controller per form
  <rp>/textures/items/morph_wand.png               the wand icon

Run standalone:  python tools/gen_morph.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field

from common import BuildError, load_config, rel, write_json, write_text
from gen_wand import _wand

WAND_ID = "mymod:morph_wand"
MORPH_ID = "mymod:morph"
FAMILY = "bigcat_morph"
PROPERTY = "mymod:form"
ICON_TEXTURE = "textures/items/morph_wand"
ALL_TEXTURES = [ICON_TEXTURE]
RC = "controller.render.mymod.morph.{key}"
LOOK = "animation.common.look_at_target"
MOVING = "query.modified_move_speed"  # what vanilla uses to blend walk animations in


@dataclass(frozen=True)
class Form:
    key: str
    name: str
    geometry: str
    texture: str
    material: str
    # short name -> (vanilla animation id, extra Molang condition or None)
    animations: dict[str, tuple[str, str | None]]
    sound: str
    pitch: float = 1.0
    scale: float = 1.0
    hidden_bones: tuple[str, ...] = ()  # parts the vanilla render controller hides
    pre_animation: tuple[str, ...] = field(default=())  # variables the vanilla animations read


# Order = the order the wand cycles through. Keep perks in scripts/morph.js keyed by `key`.
FORMS = [
    Form(
        "chicken",
        "a Chicken",
        "geometry.chicken.v1.12",
        "textures/entity/chicken/chicken",
        "chicken",
        {
            "general": ("animation.chicken.general", None),
            "move": ("animation.chicken.move", MOVING),
            "look": (LOOK, None),
        },
        "mob.chicken.say",
        # vanilla chickens get this from the game; flap while moving
        pre_animation=(
            "variable.wing_flap = math.abs(math.sin(query.life_time * 1300)) * 60 "
            "* math.min(query.modified_move_speed * 3, 1);",
        ),
    ),
    Form(
        "pig",
        "a Pig",
        "geometry.pig.v3",
        "textures/entity/pig/pig_v3",
        "pig_v3",
        {"setup": ("animation.pig.setup", None), "walk": ("animation.quadruped.walk", MOVING), "look": (LOOK, None)},
        "mob.pig.say",
    ),
    Form(
        "fox",
        "a Fox",
        "geometry.fox",
        "textures/entity/fox/fox",
        "fox",
        {"setup": ("animation.fox.setup", None), "walk": ("animation.quadruped.walk", MOVING), "look": (LOOK, None)},
        "mob.fox.ambient",
        hidden_bones=("head_sleeping",),
    ),
    Form(
        "frog",
        "a Frog",
        "geometry.frog",
        "textures/entity/frog/temperate_frog",
        "frog",
        {"walk": ("animation.frog.walk", f"{MOVING} > 0.1"), "look": (LOOK, None)},
        "mob.frog.ambient",
        hidden_bones=("croaking_body", "tongue"),
    ),
    Form(
        "bee",
        "a Bee",
        "geometry.bee",
        "textures/entity/bee/bee",
        "bee",
        {"flying": ("animation.bee.flying", None), "bob": ("animation.bee.fly.bobbing", None)},
        "mob.bee.aggressive",
        pitch=1.2,
    ),
    Form(
        "creeper",
        "a Creeper",
        "geometry.creeper.v1.8",
        "textures/entity/creeper/creeper",
        "creeper",
        {"legs": ("animation.creeper.legs", None), "look": (LOOK, None)},
        "random.fuse",
        pre_animation=(
            "variable.leg_rot = Math.cos(query.modified_distance_moved * 38.17326) "
            "* 80.22 * query.modified_move_speed;",
        ),
    ),
    Form(
        "iron_golem",
        "an Iron Golem",
        "geometry.irongolem",
        "textures/entity/iron_golem",
        "iron_golem",
        {
            "walk": ("animation.iron_golem.walk", None),
            "arms": ("animation.iron_golem.move", None),
            "look": (LOOK, None),
        },
        "mob.irongolem.hit",
        pitch=0.8,
        pre_animation=(
            "variable.modified_tcos0 = Math.clamp(Math.cos(query.modified_distance_moved * 13.5) "
            "* Math.min(query.modified_move_speed, 0.6) * 25.0, -12.5, 12.5);",
        ),
    ),
    Form(
        "big_cat",
        "a Big Cat",
        "geometry.cat",
        "textures/entity/coats/coat_000",
        "cat",
        {"walk": ("animation.cat.walk", None), "look": (LOOK, None)},
        "mob.cat.meow",
        pitch=0.6,
        scale=2.0,
    ),
]


def form_condition(n: int) -> str:
    return f"query.property('{PROPERTY}') == {n}"


def behavior_entity() -> dict:
    return {
        "format_version": "1.26.50",
        "minecraft:entity": {
            "description": {
                "identifier": MORPH_ID,
                "is_spawnable": False,
                "is_summonable": True,
                "properties": {PROPERTY: {"type": "int", "range": [0, len(FORMS)], "default": 0, "client_sync": True}},
            },
            "components": {
                "minecraft:type_family": {"family": [FAMILY, "inanimate"]},
                "minecraft:health": {"value": 1, "max": 1},
                "minecraft:damage_sensor": {"triggers": {"cause": "all", "deals_damage": "no"}},
                "minecraft:fire_immune": {},
                "minecraft:breathable": {"breathes_air": True, "breathes_water": True},
                "minecraft:knockback_resistance": {"value": 1.0},
                # Tiny, so clicks and arrows go through to the (invisible) player inside the costume.
                "minecraft:collision_box": {"width": 0.01, "height": 0.01},
                "minecraft:physics": {"has_gravity": False, "has_collision": False},
            },
        },
    }


def client_entity() -> dict:
    animations, animate = {}, []
    pre = ["variable.gliding_speed_value = 1.0;"]
    for n, f in enumerate(FORMS, start=1):
        for short, (anim, cond) in f.animations.items():
            name = f"{f.key}_{short}"
            animations[name] = anim
            animate.append({name: form_condition(n) + (f" && {cond}" if cond else "")})
        pre += [p for p in f.pre_animation if p not in pre]
    scale = " : ".join(f"{form_condition(n)} ? {f.scale}" for n, f in enumerate(FORMS, start=1) if f.scale != 1.0)
    return {
        "format_version": "1.10.0",
        "minecraft:client_entity": {
            "description": {
                "identifier": MORPH_ID,
                "materials": {f.key: f.material for f in FORMS},
                "textures": {f.key: f.texture for f in FORMS},
                "geometry": {f.key: f.geometry for f in FORMS},
                "animations": animations,
                "scripts": {
                    "pre_animation": pre,
                    "animate": animate,
                    "scale": f"{scale} : 1.0" if scale else "1.0",
                },
                "render_controllers": [{RC.format(key=f.key): form_condition(n)} for n, f in enumerate(FORMS, start=1)],
            },
        },
    }


def render_controllers() -> dict:
    rcs = {}
    for f in FORMS:
        rc = {
            "geometry": f"Geometry.{f.key}",
            "materials": [{"*": f"Material.{f.key}"}],
            "textures": [f"Texture.{f.key}"],
        }
        if f.hidden_bones:
            rc["part_visibility"] = [{bone: False} for bone in f.hidden_bones]
        rcs[RC.format(key=f.key)] = rc
    return {"format_version": "1.8.0", "render_controllers": rcs}


def forms_js() -> str:
    rows = [{"key": "human", "name": "yourself again", "sound": "random.pop", "pitch": 1.0}]
    rows += [{"key": f.key, "name": f.name, "sound": f.sound, "pitch": f.pitch} for f in FORMS]
    body = ",\n".join(f"  {json.dumps(r)}" for r in rows)
    return (
        "// GENERATED by tools/gen_morph.py - do not edit. Index = the mymod:form property.\n"
        f'export const MORPH_ID = "{MORPH_ID}";\n'
        f'export const FORM_PROPERTY = "{PROPERTY}";\n'
        f"export const FORMS = [\n{body},\n];\n"
    )


# A little pink pig face on the end of the stick.
TIP = [
    "..........PPPP..",
    ".........PEPPEP.",
    ".........PPPPPP.",
    ".........PSSSSP.",
    ".........PSNNSP.",
    "..........PPPP..",
    "................",
    "................",
]
TIP_COLORS = {
    "P": (240, 160, 170, 255),
    "E": (40, 30, 30, 255),
    "S": (220, 120, 140, 255),
    "N": (150, 70, 90, 255),
}


def icon():
    im = _wand([])  # just the stick
    for y, row in enumerate(TIP):
        for x, ch in enumerate(row):
            if ch != ".":
                im.putpixel((x, y), TIP_COLORS[ch])
    return im


def generate_morph(verbose: bool = True) -> None:
    _, paths = load_config()
    out = {
        paths.bp / "entities/morph.json": behavior_entity(),
        paths.rp / "entity/morph.entity.json": client_entity(),
        paths.rp / "render_controllers/morph.render_controllers.json": render_controllers(),
    }
    for dest, doc in out.items():
        write_json(dest, doc)
    js = paths.bp / "scripts/morph_forms.js"
    write_text(js, forms_js())
    png = paths.rp / (ICON_TEXTURE + ".png")
    png.parent.mkdir(parents=True, exist_ok=True)
    icon().save(png)
    if verbose:
        print(f"  wrote {', '.join(rel(p) for p in [*out, js, png])}")


if __name__ == "__main__":
    try:
        generate_morph()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
